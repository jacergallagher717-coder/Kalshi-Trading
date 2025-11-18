"""
Unit tests for Kalshi API client
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.api.kalshi_client import KalshiClient, Market, Order, Position


class TestKalshiClient:
    """Test Kalshi API client functionality"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Kalshi client"""
        with patch('httpx.Client'):
            client = KalshiClient(
                api_key="test_key",
                api_secret="test_secret",
                base_url="https://demo-api.kalshi.co/trade-api/v2"
            )
            return client

    def test_authentication(self, mock_client):
        """Test authentication flow"""
        # Mock successful auth response
        mock_response = Mock()
        mock_response.json.return_value = {
            "token": "test_token_12345"
        }
        mock_response.raise_for_status = Mock()

        with patch.object(mock_client.client, 'post', return_value=mock_response):
            token = mock_client.authenticate()

            assert token == "test_token_12345"
            assert mock_client.token == "test_token_12345"
            assert mock_client.token_expiry is not None

    def test_get_markets(self, mock_client):
        """Test fetching markets"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "markets": [
                {
                    "ticker": "INX-23DEC29-T4700",
                    "title": "S&P 500 above 4700",
                    "status": "open",
                    "last_price": 0.65,
                }
            ]
        }
        mock_response.raise_for_status = Mock()

        mock_client.token = "test_token"
        mock_client.token_expiry = datetime(2099, 1, 1)

        with patch.object(mock_client.client, 'request', return_value=mock_response):
            markets = mock_client.get_markets(status="open")

            assert len(markets) == 1
            assert markets[0].ticker == "INX-23DEC29-T4700"
            assert markets[0].last_price == 0.65

    def test_place_order_validation(self, mock_client):
        """Test order validation"""
        # Invalid side
        with pytest.raises(ValueError, match="Invalid side"):
            mock_client.place_order("TEST", "maybe", 10, 50)

        # Invalid price
        with pytest.raises(ValueError, match="Invalid price"):
            mock_client.place_order("TEST", "yes", 10, 100)

        # Invalid quantity
        with pytest.raises(ValueError, match="Invalid quantity"):
            mock_client.place_order("TEST", "yes", -5, 50)

    def test_place_order_success(self, mock_client):
        """Test successful order placement"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "order": {
                "order_id": "order_123",
                "ticker": "TEST",
                "side": "yes",
                "count": 10,
                "price": 50,
                "status": "resting"
            }
        }
        mock_response.raise_for_status = Mock()

        mock_client.token = "test_token"
        mock_client.token_expiry = datetime(2099, 1, 1)

        with patch.object(mock_client.client, 'request', return_value=mock_response):
            order = mock_client.place_order("TEST", "yes", 10, 50)

            assert order is not None
            assert order.order_id == "order_123"
            assert order.ticker == "TEST"
            assert order.quantity == 10

    def test_rate_limiting(self, mock_client):
        """Test rate limiting functionality"""
        import time

        start_time = time.time()

        # Make two requests back-to-back
        mock_client._rate_limit()
        mock_client._rate_limit()

        elapsed = time.time() - start_time

        # Should have waited at least min_request_interval
        assert elapsed >= mock_client.min_request_interval


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
