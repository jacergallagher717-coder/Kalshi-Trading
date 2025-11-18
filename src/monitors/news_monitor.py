"""
Multi-source news monitoring with real-time event detection.
Aggregates news from Twitter, NewsAPI, Alpha Vantage, and other sources.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum
import re

import tweepy
from newsapi import NewsApiClient
import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of market-moving events"""

    ECONOMIC_DATA = "economic_data"
    POLITICAL = "political"
    WEATHER = "weather"
    SPORTS = "sports"
    CORPORATE = "corporate"
    GENERAL = "general"


@dataclass
class NewsEvent:
    """Structured news event with metadata"""

    event_id: str
    timestamp: datetime
    source: str
    event_type: EventType
    headline: str
    content: str
    keywords: List[str]
    entities: List[str]
    related_tickers: List[str]
    reliability_score: float  # 0-1
    url: Optional[str] = None
    raw_data: Optional[Dict] = None

    def __hash__(self):
        return hash(self.event_id)


class NewsClassifier:
    """Classifies news into event types and extracts relevant information"""

    # Keyword mappings for event classification
    ECONOMIC_KEYWORDS = {
        "cpi",
        "inflation",
        "unemployment",
        "jobs report",
        "nonfarm payroll",
        "gdp",
        "federal reserve",
        "fed",
        "interest rate",
        "rate hike",
        "rate cut",
        "fomc",
        "earnings",
        "consumer confidence",
        "pmi",
        "retail sales",
        "housing starts",
        "trade deficit",
    }

    POLITICAL_KEYWORDS = {
        "congress",
        "senate",
        "house",
        "legislation",
        "bill passed",
        "vote",
        "election",
        "president",
        "executive order",
        "supreme court",
        "senate confirmed",
        "veto",
        "impeachment",
    }

    WEATHER_KEYWORDS = {
        "hurricane",
        "tornado",
        "blizzard",
        "winter storm",
        "heat wave",
        "cold snap",
        "temperature record",
        "precipitation",
        "drought",
        "flood",
        "severe weather",
        "noaa",
        "national weather service",
    }

    SPORTS_KEYWORDS = {
        "nfl",
        "nba",
        "mlb",
        "nhl",
        "playoff",
        "championship",
        "super bowl",
        "world series",
        "injury",
        "trade",
        "mvp",
        "draft",
    }

    @classmethod
    def classify_event(cls, text: str) -> EventType:
        """Classify news text into event type"""
        text_lower = text.lower()

        # Count keyword matches for each category
        scores = {
            EventType.ECONOMIC_DATA: sum(
                1 for kw in cls.ECONOMIC_KEYWORDS if kw in text_lower
            ),
            EventType.POLITICAL: sum(
                1 for kw in cls.POLITICAL_KEYWORDS if kw in text_lower
            ),
            EventType.WEATHER: sum(
                1 for kw in cls.WEATHER_KEYWORDS if kw in text_lower
            ),
            EventType.SPORTS: sum(
                1 for kw in cls.SPORTS_KEYWORDS if kw in text_lower
            ),
        }

        # Return category with highest score
        max_category = max(scores.items(), key=lambda x: x[1])
        if max_category[1] > 0:
            return max_category[0]

        return EventType.GENERAL

    @classmethod
    def extract_keywords(cls, text: str, max_keywords: int = 10) -> List[str]:
        """Extract relevant keywords from text"""
        text_lower = text.lower()
        found_keywords = []

        # Find all known keywords
        for keyword_set in [
            cls.ECONOMIC_KEYWORDS,
            cls.POLITICAL_KEYWORDS,
            cls.WEATHER_KEYWORDS,
            cls.SPORTS_KEYWORDS,
        ]:
            for keyword in keyword_set:
                if keyword in text_lower:
                    found_keywords.append(keyword)

        # Extract numbers (potential data points)
        numbers = re.findall(r"\b\d+\.?\d*%?\b", text)
        found_keywords.extend(numbers[:3])  # Add up to 3 numbers

        return found_keywords[:max_keywords]

    @classmethod
    def extract_entities(cls, text: str) -> List[str]:
        """Extract named entities (simplified - would use NLP in production)"""
        # Simple capitalized word extraction (placeholder for real NER)
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        return list(set(entities))[:10]


class TwitterMonitor:
    """Monitor Twitter for real-time news using Twitter API v2"""

    def __init__(self, bearer_token: str, accounts: List[str]):
        self.bearer_token = bearer_token
        self.accounts = accounts
        self.client = None
        self.seen_tweets: Set[str] = set()

        # Initialize Tweepy client
        if bearer_token:
            try:
                self.client = tweepy.Client(bearer_token=bearer_token)
                logger.info("Twitter client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter client: {e}")

    async def fetch_recent_tweets(self) -> List[NewsEvent]:
        """Fetch recent tweets from monitored accounts"""
        if not self.client:
            return []

        events = []
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)

        try:
            for account in self.accounts:
                # Get user ID
                user = self.client.get_user(username=account)
                if not user.data:
                    continue

                # Get recent tweets
                tweets = self.client.get_users_tweets(
                    id=user.data.id,
                    max_results=10,
                    tweet_fields=["created_at", "text"],
                )

                if not tweets.data:
                    continue

                for tweet in tweets.data:
                    tweet_id = str(tweet.id)

                    # Skip if already seen
                    if tweet_id in self.seen_tweets:
                        continue

                    # Skip if too old
                    if tweet.created_at < cutoff_time:
                        continue

                    # Mark as seen
                    self.seen_tweets.add(tweet_id)

                    # Create event
                    event = NewsEvent(
                        event_id=f"twitter_{tweet_id}",
                        timestamp=tweet.created_at,
                        source=f"twitter_@{account}",
                        event_type=NewsClassifier.classify_event(tweet.text),
                        headline=tweet.text[:100],
                        content=tweet.text,
                        keywords=NewsClassifier.extract_keywords(tweet.text),
                        entities=NewsClassifier.extract_entities(tweet.text),
                        related_tickers=[],
                        reliability_score=0.8,  # High for verified news accounts
                        url=f"https://twitter.com/{account}/status/{tweet_id}",
                        raw_data={"tweet_id": tweet_id, "author": account},
                    )
                    events.append(event)

            logger.debug(f"Fetched {len(events)} new tweets")
            return events

        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            return []


class NewsAPIMonitor:
    """Monitor NewsAPI.org for breaking news"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
        self.seen_articles: Set[str] = set()

        if api_key:
            try:
                self.client = NewsApiClient(api_key=api_key)
                logger.info("NewsAPI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize NewsAPI client: {e}")

    async def fetch_top_headlines(
        self, category: str = "business", country: str = "us"
    ) -> List[NewsEvent]:
        """Fetch top headlines from NewsAPI"""
        if not self.client:
            return []

        events = []

        try:
            # Get top headlines
            response = self.client.get_top_headlines(
                category=category, country=country, page_size=20
            )

            articles = response.get("articles", [])

            for article in articles:
                article_url = article.get("url", "")

                # Create unique ID from URL
                article_id = hashlib.md5(article_url.encode()).hexdigest()

                # Skip if already seen
                if article_id in self.seen_articles:
                    continue

                self.seen_articles.add(article_id)

                # Parse published date
                published_at = article.get("publishedAt")
                if published_at:
                    timestamp = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                else:
                    timestamp = datetime.utcnow()

                # Create event
                title = article.get("title", "")
                description = article.get("description", "")
                content = f"{title}. {description}"

                event = NewsEvent(
                    event_id=f"newsapi_{article_id}",
                    timestamp=timestamp,
                    source=f"newsapi_{article.get('source', {}).get('name', 'unknown')}",
                    event_type=NewsClassifier.classify_event(content),
                    headline=title,
                    content=content,
                    keywords=NewsClassifier.extract_keywords(content),
                    entities=NewsClassifier.extract_entities(content),
                    related_tickers=[],
                    reliability_score=0.7,
                    url=article_url,
                    raw_data=article,
                )
                events.append(event)

            logger.debug(f"Fetched {len(events)} new articles from NewsAPI")
            return events

        except Exception as e:
            logger.error(f"Error fetching NewsAPI headlines: {e}")
            return []


class AlphaVantageMonitor:
    """Monitor Alpha Vantage news sentiment"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.seen_articles: Set[str] = set()
        self.base_url = "https://www.alphavantage.co/query"

    async def fetch_news_sentiment(
        self, topics: List[str] = None
    ) -> List[NewsEvent]:
        """Fetch news sentiment from Alpha Vantage"""
        if not self.api_key:
            return []

        if topics is None:
            topics = ["financial_markets", "economy_macro"]

        events = []

        try:
            async with httpx.AsyncClient() as client:
                for topic in topics:
                    params = {
                        "function": "NEWS_SENTIMENT",
                        "topics": topic,
                        "apikey": self.api_key,
                    }

                    response = await client.get(self.base_url, params=params)
                    data = response.json()

                    feed = data.get("feed", [])

                    for article in feed[:10]:  # Limit to 10 per topic
                        article_url = article.get("url", "")
                        article_id = hashlib.md5(article_url.encode()).hexdigest()

                        if article_id in self.seen_articles:
                            continue

                        self.seen_articles.add(article_id)

                        # Parse timestamp
                        time_published = article.get("time_published", "")
                        try:
                            timestamp = datetime.strptime(
                                time_published, "%Y%m%dT%H%M%S"
                            )
                        except:
                            timestamp = datetime.utcnow()

                        title = article.get("title", "")
                        summary = article.get("summary", "")
                        content = f"{title}. {summary}"

                        # Get sentiment score
                        sentiment_score = float(
                            article.get("overall_sentiment_score", 0)
                        )
                        reliability = 0.6 + abs(sentiment_score) * 0.3  # 0.6-0.9

                        event = NewsEvent(
                            event_id=f"alphavantage_{article_id}",
                            timestamp=timestamp,
                            source="alphavantage",
                            event_type=NewsClassifier.classify_event(content),
                            headline=title,
                            content=content,
                            keywords=NewsClassifier.extract_keywords(content),
                            entities=NewsClassifier.extract_entities(content),
                            related_tickers=[],
                            reliability_score=reliability,
                            url=article_url,
                            raw_data=article,
                        )
                        events.append(event)

            logger.debug(f"Fetched {len(events)} new articles from Alpha Vantage")
            return events

        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage news: {e}")
            return []


class WeatherAlertMonitor:
    """Monitor NOAA weather alerts"""

    def __init__(self):
        self.base_url = "https://api.weather.gov/alerts/active"
        self.seen_alerts: Set[str] = set()

    async def fetch_active_alerts(self) -> List[NewsEvent]:
        """Fetch active weather alerts from NOAA"""
        events = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    params={"status": "actual", "message_type": "alert"},
                )
                data = response.json()

                features = data.get("features", [])

                for feature in features:
                    properties = feature.get("properties", {})

                    alert_id = properties.get("id", "")
                    if alert_id in self.seen_alerts:
                        continue

                    self.seen_alerts.add(alert_id)

                    # Parse sent time
                    sent = properties.get("sent", "")
                    try:
                        timestamp = datetime.fromisoformat(sent.replace("Z", "+00:00"))
                    except:
                        timestamp = datetime.utcnow()

                    event_name = properties.get("event", "")
                    headline = properties.get("headline", "")
                    description = properties.get("description", "")

                    content = f"{event_name}: {headline}"

                    event = NewsEvent(
                        event_id=f"weather_{alert_id}",
                        timestamp=timestamp,
                        source="noaa",
                        event_type=EventType.WEATHER,
                        headline=headline,
                        content=content,
                        keywords=[event_name.lower()],
                        entities=[properties.get("areaDesc", "")],
                        related_tickers=[],
                        reliability_score=0.95,  # NOAA is highly reliable
                        raw_data=properties,
                    )
                    events.append(event)

            logger.debug(f"Fetched {len(events)} new weather alerts")
            return events

        except Exception as e:
            logger.error(f"Error fetching weather alerts: {e}")
            return []


class NewsMonitor:
    """
    Centralized news monitoring system that aggregates from multiple sources.

    Usage:
        monitor = NewsMonitor(config)
        await monitor.start()
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.running = False

        # Initialize monitors
        self.twitter_monitor = None
        self.newsapi_monitor = None
        self.alphavantage_monitor = None
        self.weather_monitor = None

        # Event deduplication cache (keep for 24 hours)
        self.event_cache: TTLCache = TTLCache(maxsize=10000, ttl=86400)

        # Event callbacks
        self.event_callbacks = []

        self._setup_monitors()

    def _setup_monitors(self):
        """Initialize all enabled monitors"""
        # Twitter
        if self.config.get("twitter", {}).get("enabled"):
            token = self.config["twitter"].get("bearer_token")
            accounts = self.config["twitter"].get("accounts", [])
            if token:
                self.twitter_monitor = TwitterMonitor(token, accounts)

        # NewsAPI
        if self.config.get("newsapi", {}).get("enabled"):
            api_key = self.config["newsapi"].get("api_key")
            if api_key:
                self.newsapi_monitor = NewsAPIMonitor(api_key)

        # Alpha Vantage
        if self.config.get("alphavantage", {}).get("enabled"):
            api_key = self.config["alphavantage"].get("api_key")
            if api_key:
                self.alphavantage_monitor = AlphaVantageMonitor(api_key)

        # Weather
        if self.config.get("weather", {}).get("enabled"):
            self.weather_monitor = WeatherAlertMonitor()

    def register_callback(self, callback):
        """Register a callback to be called for each new event"""
        self.event_callbacks.append(callback)

    async def _process_event(self, event: NewsEvent):
        """Process a new event and call callbacks"""
        # Skip if already seen
        if event.event_id in self.event_cache:
            return

        # Add to cache
        self.event_cache[event.event_id] = True

        # Log event
        logger.info(
            f"New {event.event_type.value} event: {event.headline[:100]} "
            f"(source: {event.source}, reliability: {event.reliability_score:.2f})"
        )

        # Call all registered callbacks
        for callback in self.event_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    async def _poll_twitter(self):
        """Poll Twitter feed"""
        if not self.twitter_monitor:
            return

        interval = self.config.get("twitter", {}).get("poll_interval_seconds", 2)

        while self.running:
            try:
                events = await self.twitter_monitor.fetch_recent_tweets()
                for event in events:
                    await self._process_event(event)
            except Exception as e:
                logger.error(f"Error polling Twitter: {e}")

            await asyncio.sleep(interval)

    async def _poll_newsapi(self):
        """Poll NewsAPI"""
        if not self.newsapi_monitor:
            return

        interval = self.config.get("newsapi", {}).get("poll_interval_seconds", 10)

        while self.running:
            try:
                events = await self.newsapi_monitor.fetch_top_headlines()
                for event in events:
                    await self._process_event(event)
            except Exception as e:
                logger.error(f"Error polling NewsAPI: {e}")

            await asyncio.sleep(interval)

    async def _poll_alphavantage(self):
        """Poll Alpha Vantage"""
        if not self.alphavantage_monitor:
            return

        interval = self.config.get("alphavantage", {}).get(
            "poll_interval_seconds", 30
        )

        while self.running:
            try:
                events = await self.alphavantage_monitor.fetch_news_sentiment()
                for event in events:
                    await self._process_event(event)
            except Exception as e:
                logger.error(f"Error polling Alpha Vantage: {e}")

            await asyncio.sleep(interval)

    async def _poll_weather(self):
        """Poll weather alerts"""
        if not self.weather_monitor:
            return

        interval = self.config.get("weather", {}).get("poll_interval_seconds", 300)

        while self.running:
            try:
                events = await self.weather_monitor.fetch_active_alerts()
                for event in events:
                    await self._process_event(event)
            except Exception as e:
                logger.error(f"Error polling weather: {e}")

            await asyncio.sleep(interval)

    async def start(self):
        """Start monitoring all sources"""
        self.running = True
        logger.info("Starting news monitoring...")

        # Start all polling tasks
        tasks = [
            asyncio.create_task(self._poll_twitter()),
            asyncio.create_task(self._poll_newsapi()),
            asyncio.create_task(self._poll_alphavantage()),
            asyncio.create_task(self._poll_weather()),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in news monitor: {e}")
        finally:
            self.running = False

    async def stop(self):
        """Stop monitoring"""
        logger.info("Stopping news monitoring...")
        self.running = False
