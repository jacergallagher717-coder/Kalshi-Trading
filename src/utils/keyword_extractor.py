"""
Keyword Extractor for News Messages
Extracts relevant keywords from news text for Kalshi market matching.
"""

import re
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """Extract relevant keywords from news text for market matching"""

    # Common words to ignore
    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'down', 'out', 'off', 'over', 'under',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might',
        'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'than', 'too', 'very', 'just', 'now', 'then', 'than', 'so',
        'about', 'after', 'also', 'any', 'as', 'because', 'before', 'between',
    }

    # Important finance/market/political keywords
    IMPORTANT_KEYWORDS = {
        # Economic
        'cpi', 'inflation', 'unemployment', 'gdp', 'jobs', 'payroll', 'nfp',
        'claims', 'jobless', 'fed', 'federal', 'reserve', 'fomc', 'powell',
        'rate', 'rates', 'hike', 'cut', 'basis', 'points', 'bps',
        'retail', 'sales', 'housing', 'starts', 'pmi', 'ism', 'manufacturing',
        'services', 'confidence', 'sentiment', 'ppi', 'producer',

        # Political
        'congress', 'senate', 'house', 'vote', 'bill', 'legislation',
        'president', 'trump', 'biden', 'democrats', 'republicans',
        'election', 'primary', 'midterm', 'senate', 'governor',
        'supreme', 'court', 'scotus', 'ruling', 'decision',

        # Weather
        'hurricane', 'storm', 'tornado', 'temperature', 'heat', 'cold',
        'snow', 'rain', 'drought', 'flood', 'forecast', 'noaa',

        # Sports
        'nfl', 'nba', 'mlb', 'nhl', 'playoff', 'championship', 'superbowl',
        'injury', 'mvp', 'trade', 'draft',

        # Corporate
        'earnings', 'revenue', 'profit', 'beat', 'miss', 'guidance',
        'merger', 'acquisition', 'deal', 'buyout', 'ipo',

        # Crypto/Markets
        'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'stock', 'market',
        'sp500', 's&p', 'dow', 'nasdaq', 'vix', 'volatility',
    }

    # Stock tickers and common abbreviations
    TICKER_PATTERN = re.compile(r'\b[A-Z]{1,5}\b')

    @classmethod
    def extract_keywords(cls, text: str, max_keywords: int = 20) -> List[str]:
        """
        Extract relevant keywords from text for Kalshi market matching.

        Args:
            text: News text to extract keywords from
            max_keywords: Maximum number of keywords to return

        Returns:
            List of relevant keywords sorted by importance
        """
        if not text:
            return []

        keywords: Set[str] = set()
        text_lower = text.lower()

        # 1. Extract important predefined keywords
        for keyword in cls.IMPORTANT_KEYWORDS:
            if keyword in text_lower:
                keywords.add(keyword)

        # 2. Extract stock tickers (all caps words)
        tickers = cls.TICKER_PATTERN.findall(text)
        for ticker in tickers:
            if len(ticker) >= 2 and ticker.lower() not in cls.STOPWORDS:
                keywords.add(ticker.upper())

        # 3. Extract numbers with context (percentages, thousands, etc.)
        number_patterns = [
            r'(\d+\.?\d*)\s*%',  # Percentages: 2.4%
            r'(\d+\.?\d*)\s*percent',  # Percent: 2.4 percent
            r'(\d+[,\d]*)\s*(?:k|thousand)',  # Thousands: 235k, 235 thousand
            r'(\d+\.?\d*)\s*(?:billion|million|trillion)',  # Large numbers
        ]

        for pattern in number_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                # Get surrounding context (3 words before)
                start = max(0, match.start() - 30)
                context = text_lower[start:match.start()].split()[-3:]

                # Add context words as keywords
                for word in context:
                    word = word.strip('.,!?;:()[]{}')
                    if word and word not in cls.STOPWORDS and len(word) > 2:
                        keywords.add(word)

        # 4. Extract capitalized words (proper nouns, names, places)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for word in capitalized_words:
            # Skip common words that are often capitalized
            word_lower = word.lower()
            if word_lower not in cls.STOPWORDS and len(word) > 2:
                keywords.add(word_lower)

        # 5. Extract all meaningful words (nouns, adjectives)
        # Simple approach: words longer than 3 chars, not in stopwords
        words = re.findall(r'\b[a-z]{4,}\b', text_lower)
        for word in words:
            if word not in cls.STOPWORDS:
                keywords.add(word)

        # Convert to list and prioritize important keywords
        keyword_list = list(keywords)

        # Sort: important keywords first, then alphabetically
        def keyword_priority(kw):
            if kw.lower() in cls.IMPORTANT_KEYWORDS:
                return (0, kw)  # Highest priority
            elif kw.isupper():
                return (1, kw)  # Tickers second
            else:
                return (2, kw)  # Rest last

        keyword_list.sort(key=keyword_priority)

        # Limit to max keywords
        result = keyword_list[:max_keywords]

        logger.debug(f"Extracted {len(result)} keywords from text: {result}")
        return result

    @classmethod
    def extract_entities(cls, text: str) -> dict:
        """
        Extract named entities and structured data from text.

        Returns:
            Dict with extracted entities: {
                'keywords': [...],
                'numbers': [...],
                'tickers': [...],
                'names': [...],
            }
        """
        entities = {
            'keywords': cls.extract_keywords(text),
            'numbers': [],
            'tickers': [],
            'names': [],
        }

        # Extract numbers with units
        number_patterns = [
            (r'(\d+\.?\d*)\s*%', 'percent'),
            (r'(\d+[,\d]*)\s*k', 'thousands'),
            (r'(\d+\.?\d*)\s*(?:billion|bn)', 'billion'),
            (r'(\d+\.?\d*)\s*(?:million|mn|m)', 'million'),
        ]

        for pattern, unit in number_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                entities['numbers'].append({
                    'value': match.group(1),
                    'unit': unit,
                    'text': match.group(0)
                })

        # Extract tickers
        tickers = cls.TICKER_PATTERN.findall(text)
        entities['tickers'] = [t for t in tickers if len(t) >= 2 and t.lower() not in cls.STOPWORDS]

        # Extract names (capitalized words)
        names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        entities['names'] = [n for n in names if n.lower() not in cls.STOPWORDS]

        return entities
