"""
Prometheus metrics collection for the trading system.
"""

import logging
from prometheus_client import Counter, Histogram, Gauge, start_http_server

logger = logging.getLogger(__name__)


# Trade metrics
trades_total = Counter(
    "kalshi_trades_total",
    "Total number of trades executed",
    ["side", "ticker", "status"],
)

trade_pnl = Histogram(
    "kalshi_trade_pnl_dollars",
    "Trade P&L in dollars",
    buckets=[-500, -200, -100, -50, -20, 0, 20, 50, 100, 200, 500, 1000],
)

# Signal metrics
signals_total = Counter(
    "kalshi_signals_total",
    "Total number of signals generated",
    ["source", "executed"],
)

signal_latency_seconds = Histogram(
    "kalshi_signal_latency_seconds",
    "Time from news event to signal generation",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

# Position metrics
open_positions = Gauge(
    "kalshi_open_positions",
    "Number of currently open positions",
)

portfolio_value = Gauge(
    "kalshi_portfolio_value_dollars",
    "Total portfolio value in dollars",
)

unrealized_pnl = Gauge(
    "kalshi_unrealized_pnl_dollars",
    "Total unrealized P&L across all positions",
)

# API metrics
api_request_duration_seconds = Histogram(
    "kalshi_api_request_duration_seconds",
    "Kalshi API request duration",
    ["endpoint", "method"],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

api_errors_total = Counter(
    "kalshi_api_errors_total",
    "Total number of API errors",
    ["endpoint", "error_type"],
)

# News monitoring metrics
news_events_total = Counter(
    "kalshi_news_events_total",
    "Total number of news events detected",
    ["source", "event_type"],
)

# System metrics
system_errors_total = Counter(
    "kalshi_system_errors_total",
    "Total number of system errors",
    ["component", "error_type"],
)

circuit_breaker_trips = Counter(
    "kalshi_circuit_breaker_trips_total",
    "Number of times circuit breaker has tripped",
)


class MetricsCollector:
    """Centralized metrics collection"""

    @staticmethod
    def record_trade(side: str, ticker: str, status: str, pnl: float = None):
        """Record a trade execution"""
        trades_total.labels(side=side, ticker=ticker, status=status).inc()
        if pnl is not None:
            trade_pnl.observe(pnl)

    @staticmethod
    def record_signal(source: str, executed: bool):
        """Record a signal generation"""
        signals_total.labels(
            source=source,
            executed="yes" if executed else "no"
        ).inc()

    @staticmethod
    def record_signal_latency(seconds: float):
        """Record time from news to signal"""
        signal_latency_seconds.observe(seconds)

    @staticmethod
    def update_positions(num_positions: int, total_value: float, total_unrealized_pnl: float):
        """Update position metrics"""
        open_positions.set(num_positions)
        portfolio_value.set(total_value)
        unrealized_pnl.set(total_unrealized_pnl)

    @staticmethod
    def record_api_request(endpoint: str, method: str, duration: float):
        """Record API request duration"""
        api_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)

    @staticmethod
    def record_api_error(endpoint: str, error_type: str):
        """Record API error"""
        api_errors_total.labels(
            endpoint=endpoint,
            error_type=error_type
        ).inc()

    @staticmethod
    def record_news_event(source: str, event_type: str):
        """Record news event detection"""
        news_events_total.labels(
            source=source,
            event_type=event_type
        ).inc()

    @staticmethod
    def record_system_error(component: str, error_type: str):
        """Record system error"""
        system_errors_total.labels(
            component=component,
            error_type=error_type
        ).inc()

    @staticmethod
    def record_circuit_breaker_trip():
        """Record circuit breaker trip"""
        circuit_breaker_trips.inc()


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics HTTP server"""
    try:
        start_http_server(port)
        logger.info(f"Metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
