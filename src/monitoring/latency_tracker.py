"""
Latency Tracking
Measures end-to-end latency from news event to trade execution.
Critical for speed arbitrage - every millisecond counts!
"""

import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime

logger = logging.getLogger(__name__)


class LatencyTracker:
    """
    Track latency across different stages of trade execution.

    Stages:
    1. News receipt → parsing
    2. Parsing → market matching
    3. Market matching → signal generation
    4. Signal generation → order placement
    5. Order placement → fill confirmation
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.current_traces = {}  # Active traces by trace_id
        self.completed_traces = deque(maxlen=max_history)  # Recent completed traces
        self.stage_latencies = defaultdict(list)  # Latencies by stage

    def start_trace(self, trace_id: str, metadata: Optional[Dict] = None):
        """Start a new latency trace"""
        self.current_traces[trace_id] = {
            'trace_id': trace_id,
            'start_time': time.time(),
            'stages': {},
            'metadata': metadata or {},
            'total_latency_ms': None
        }
        logger.debug(f"[LATENCY] Started trace: {trace_id}")

    def mark_stage(self, trace_id: str, stage_name: str):
        """Mark completion of a stage"""
        if trace_id not in self.current_traces:
            logger.warning(f"[LATENCY] Trace not found: {trace_id}")
            return

        trace = self.current_traces[trace_id]
        current_time = time.time()
        elapsed_ms = (current_time - trace['start_time']) * 1000

        trace['stages'][stage_name] = {
            'timestamp': current_time,
            'elapsed_ms': elapsed_ms
        }

        logger.debug(f"[LATENCY] {trace_id} | {stage_name}: {elapsed_ms:.1f}ms")

    def end_trace(self, trace_id: str, success: bool = True):
        """End a trace and calculate total latency"""
        if trace_id not in self.current_traces:
            logger.warning(f"[LATENCY] Trace not found: {trace_id}")
            return

        trace = self.current_traces[trace_id]
        total_latency_ms = (time.time() - trace['start_time']) * 1000
        trace['total_latency_ms'] = total_latency_ms
        trace['success'] = success
        trace['end_time'] = time.time()

        # Calculate stage-by-stage latencies
        stages = sorted(trace['stages'].items(), key=lambda x: x[1]['elapsed_ms'])
        prev_elapsed = 0

        for stage_name, stage_data in stages:
            stage_latency = stage_data['elapsed_ms'] - prev_elapsed
            stage_data['stage_latency_ms'] = stage_latency
            self.stage_latencies[stage_name].append(stage_latency)
            prev_elapsed = stage_data['elapsed_ms']

        # Log summary
        logger.info(
            f"[LATENCY] {trace_id} | TOTAL: {total_latency_ms:.1f}ms | "
            f"Success: {success}"
        )

        for stage_name, stage_data in stages:
            logger.debug(
                f"[LATENCY]   └─ {stage_name}: {stage_data['stage_latency_ms']:.1f}ms"
            )

        # Move to completed
        self.completed_traces.append(trace)
        del self.current_traces[trace_id]

        # Alert if latency exceeds target (1000ms for speed arbitrage)
        if success and total_latency_ms > 1000:
            logger.warning(
                f"⚠️ SLOW EXECUTION: {trace_id} took {total_latency_ms:.0f}ms "
                f"(target: <1000ms)"
            )

    def get_statistics(self) -> Dict:
        """Get latency statistics"""
        if not self.completed_traces:
            return {
                'total_traces': 0,
                'avg_latency_ms': None,
                'p50_latency_ms': None,
                'p95_latency_ms': None,
                'p99_latency_ms': None,
            }

        latencies = [t['total_latency_ms'] for t in self.completed_traces if t.get('success')]

        if not latencies:
            return {'total_traces': 0}

        latencies.sort()
        count = len(latencies)

        return {
            'total_traces': count,
            'successful_traces': len([t for t in self.completed_traces if t.get('success')]),
            'avg_latency_ms': sum(latencies) / count,
            'min_latency_ms': latencies[0],
            'max_latency_ms': latencies[-1],
            'p50_latency_ms': latencies[int(count * 0.5)],
            'p95_latency_ms': latencies[int(count * 0.95)],
            'p99_latency_ms': latencies[int(count * 0.99)],
        }

    def print_summary(self):
        """Print latency summary"""
        stats = self.get_statistics()

        if stats['total_traces'] == 0:
            logger.info("No latency data available yet")
            return

        logger.info("=" * 60)
        logger.info("⏱️  LATENCY SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Traces: {stats['total_traces']}")
        logger.info(f"Successful: {stats['successful_traces']}")
        logger.info(f"Average Latency: {stats['avg_latency_ms']:.1f}ms")
        logger.info(f"Min: {stats['min_latency_ms']:.1f}ms | Max: {stats['max_latency_ms']:.1f}ms")
        logger.info(f"P50: {stats['p50_latency_ms']:.1f}ms")
        logger.info(f"P95: {stats['p95_latency_ms']:.1f}ms")
        logger.info(f"P99: {stats['p99_latency_ms']:.1f}ms")
        logger.info("")
        logger.info("Stage Breakdown:")

        for stage, latencies in self.stage_latencies.items():
            if latencies:
                avg = sum(latencies) / len(latencies)
                logger.info(f"  {stage:25} {avg:.1f}ms avg")

        logger.info("=" * 60)

        # Performance assessment
        if stats['p95_latency_ms'] < 500:
            logger.info("✅ EXCELLENT: P95 < 500ms - very competitive")
        elif stats['p95_latency_ms'] < 1000:
            logger.info("✅ GOOD: P95 < 1000ms - competitive for speed arbitrage")
        elif stats['p95_latency_ms'] < 2000:
            logger.warning("⚠️ SLOW: P95 < 2000ms - may lose edge to faster bots")
        else:
            logger.error("❌ TOO SLOW: P95 > 2000ms - need optimization")

        logger.info("=" * 60)


# Singleton instance
_latency_tracker = None


def get_latency_tracker() -> LatencyTracker:
    """Get singleton instance of latency tracker"""
    global _latency_tracker
    if _latency_tracker is None:
        _latency_tracker = LatencyTracker()
    return _latency_tracker
