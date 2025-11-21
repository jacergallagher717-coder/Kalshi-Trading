"""
Kalshi Exchange API Client
Documentation: https://trading-api.readme.io/reference/getting-started
"""

import time
import base64
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class Market:
    """Represents a Kalshi market"""

    def __init__(self, data: Dict[str, Any]):
        self.ticker = data.get("ticker")
        self.title = data.get("title")
        self.category = data.get("category")
        self.close_time = data.get("close_time")
        self.expiration_time = data.get("expiration_time")
        self.status = data.get("status")
        self.yes_bid = data.get("yes_bid", 0)
        self.yes_ask = data.get("yes_ask", 0)
        self.no_bid = data.get("no_bid", 0)
        self.no_ask = data.get("no_ask", 0)
        self.volume = data.get("volume", 0)
        self.open_interest = data.get("open_interest", 0)
        self.last_price = data.get("last_price")
        self.raw_data = data

    def __repr__(self):
        return f"Market({self.ticker}, {self.title[:50]}...)"


class OrderBook:
    """Represents orderbook for a market"""

    def __init__(self, data: Dict[str, Any]):
        self.yes_bids = data.get("yes", {}).get("bids", [])
        self.yes_asks = data.get("yes", {}).get("asks", [])
        self.no_bids = data.get("no", {}).get("bids", [])
        self.no_asks = data.get("no", {}).get("asks", [])

    def get_best_bid(self, side: str = "yes") -> Optional[Dict]:
        """Get best bid price"""
        bids = self.yes_bids if side == "yes" else self.no_bids
        return bids[0] if bids else None

    def get_best_ask(self, side: str = "yes") -> Optional[Dict]:
        """Get best ask price"""
        asks = self.yes_asks if side == "yes" else self.no_asks
        return asks[0] if asks else None

    def get_spread(self, side: str = "yes") -> float:
        """Calculate bid-ask spread"""
        bid = self.get_best_bid(side)
        ask = self.get_best_ask(side)
        if bid and ask:
            return ask["price"] - bid["price"]
        return float("inf")


class Order:
    """Represents a trade order"""

    def __init__(self, data: Dict[str, Any]):
        self.order_id = data.get("order_id")
        self.ticker = data.get("ticker")
        self.side = data.get("side")
        self.quantity = data.get("count")
        self.price = data.get("price")
        self.status = data.get("status")
        self.created_at = data.get("created_time")
        self.filled_quantity = data.get("filled_count", 0)
        self.raw_data = data

    def __repr__(self):
        return f"Order({self.order_id}, {self.ticker}, {self.side}, {self.quantity}@{self.price})"


class Position:
    """Represents an open position"""

    def __init__(self, data: Dict[str, Any]):
        self.ticker = data.get("ticker")
        self.position = data.get("position")
        self.total_cost = data.get("total_traded", 0)
        self.raw_data = data

    def __repr__(self):
        return f"Position({self.ticker}, qty={self.position}, cost={self.total_cost})"


class Trade:
    """Represents a completed trade"""

    def __init__(self, data: Dict[str, Any]):
        self.trade_id = data.get("trade_id")
        self.ticker = data.get("ticker")
        self.side = data.get("side")
        self.quantity = data.get("count")
        self.price = data.get("price")
        self.created_at = data.get("created_time")
        self.raw_data = data

    def __repr__(self):
        return f"Trade({self.ticker}, {self.side}, {self.quantity}@{self.price})"


class KalshiClient:
    """
    Kalshi API client with authentication, rate limiting, and error handling.

    Example usage:
        client = KalshiClient(api_key="xxx", api_secret="yyy")
        markets = client.get_markets(status="open")
        order = client.place_order("INXD-23DEC29-T4700", "yes", 10, 50)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://demo-api.kalshi.co/trade-api/v2",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)

        # Parse RSA private key for request signing
        # Handle case where .env strips newlines - restore PEM format
        try:
            # If key doesn't have newlines, it needs to be reformatted
            if '\\n' in api_secret:
                # Handle escaped newlines
                key_data = api_secret.replace('\\n', '\n')
            elif '\n' not in api_secret and '-----BEGIN' in api_secret:
                # Key is on one line, need to add newlines
                # Extract the base64 content between headers
                key_data = api_secret.replace('-----BEGIN RSA PRIVATE KEY-----', '-----BEGIN RSA PRIVATE KEY-----\n')
                key_data = key_data.replace('-----END RSA PRIVATE KEY-----', '\n-----END RSA PRIVATE KEY-----')
                # Add newlines every 64 characters in the base64 content
                lines = key_data.split('\n')
                if len(lines) == 3:  # header, content, footer
                    content = lines[1]
                    formatted_content = '\n'.join([content[i:i+64] for i in range(0, len(content), 64)])
                    key_data = f"{lines[0]}\n{formatted_content}\n{lines[2]}"
            else:
                # Key already has proper format
                key_data = api_secret

            self.private_key = serialization.load_pem_private_key(
                key_data.encode('utf-8'),
                password=None,
                backend=default_backend()
            )
            logger.info("Successfully loaded RSA private key")
        except Exception as e:
            logger.error(f"Failed to load RSA private key: {e}")
            escaped_newline = '\\n'
            has_newlines = '\n' in api_secret
            has_escaped = escaped_newline in api_secret
            logger.error(f"Key format check - has newlines: {has_newlines}, has escaped newlines: {has_escaped}")
            raise

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests

        logger.info(f"Initialized Kalshi client for {base_url}")

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _sign_request(self, method: str, path: str, timestamp_ms: int, body: str = "") -> str:
        """
        Sign API request using RSA-PSS with SHA-256.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., /trade-api/v2/markets)
            timestamp_ms: Current timestamp in milliseconds
            body: Request body as string (empty for GET requests)

        Returns:
            Base64-encoded signature
        """
        # Create the message to sign: timestamp + method + path + body
        message = f"{timestamp_ms}{method}{path}{body}"

        # Sign with RSA-PSS padding and SHA-256
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        # Return base64-encoded signature
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Get headers with Kalshi API key authentication.

        Each request is signed with RSA private key using these headers:
        - KALSHI-ACCESS-KEY: API key ID
        - KALSHI-ACCESS-TIMESTAMP: Request timestamp in milliseconds
        - KALSHI-ACCESS-SIGNATURE: RSA-PSS signature of request
        """
        timestamp_ms = int(time.time() * 1000)
        signature = self._sign_request(method, path, timestamp_ms, body)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Kalshi API with retry logic"""
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"

        # Prepare body for signature (empty string for GET requests)
        import json as json_module
        body_str = json_module.dumps(json) if json else ""

        # Get signed headers
        headers = self._get_headers(method.upper(), endpoint, body_str)

        try:
            response = self.client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Request failed: {e}")
            raise

    def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        category: Optional[str] = None,
    ) -> List[Market]:
        """
        Fetch markets from Kalshi.

        Args:
            status: Market status (open, closed, settled)
            limit: Max number of markets to return
            category: Filter by category (e.g., 'economics', 'weather')

        Returns:
            List of Market objects
        """
        params = {"status": status, "limit": limit}
        if category:
            params["category"] = category

        try:
            data = self._make_request("GET", "/markets", params=params)
            markets = [Market(m) for m in data.get("markets", [])]
            logger.debug(f"Fetched {len(markets)} markets")
            return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    def get_market(self, ticker: str) -> Optional[Market]:
        """Get specific market by ticker"""
        try:
            data = self._make_request("GET", f"/markets/{ticker}")
            market = data.get("market")
            return Market(market) if market else None
        except Exception as e:
            logger.error(f"Failed to fetch market {ticker}: {e}")
            return None

    def get_orderbook(self, ticker: str, depth: int = 5) -> Optional[OrderBook]:
        """
        Get orderbook for a specific market.

        Args:
            ticker: Market ticker
            depth: Number of price levels to return

        Returns:
            OrderBook object with bids/asks
        """
        try:
            data = self._make_request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
            orderbook_data = data.get("orderbook", {})
            return OrderBook(orderbook_data)
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {ticker}: {e}")
            return None

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: int,
        order_type: str = "limit",
    ) -> Optional[Order]:
        """
        Place an order on Kalshi.

        Args:
            ticker: Market ticker (e.g., "INXD-23DEC29-T4700")
            side: "yes" or "no"
            quantity: Number of contracts
            limit_price: Price in cents (1-99)
            order_type: "limit" or "market"

        Returns:
            Order object if successful
        """
        # Validate inputs
        if side not in ["yes", "no"]:
            raise ValueError(f"Invalid side: {side}. Must be 'yes' or 'no'")

        if not 1 <= limit_price <= 99:
            raise ValueError(f"Invalid price: {limit_price}. Must be 1-99 cents")

        if quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity}. Must be positive")

        payload = {
            "ticker": ticker,
            "action": "buy",  # Always buy (yes or no side)
            "side": side,
            "count": quantity,
            "type": order_type,
        }

        if order_type == "limit":
            payload["yes_price"] = limit_price if side == "yes" else None
            payload["no_price"] = limit_price if side == "no" else None

        try:
            logger.info(f"Placing order: {quantity} {side} @ {limit_price} on {ticker}")
            data = self._make_request("POST", "/portfolio/orders", json=payload)
            order = data.get("order")
            return Order(order) if order else None

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order"""
        try:
            self._make_request("DELETE", f"/portfolio/orders/{order_id}")
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Position]:
        """Get all current positions"""
        try:
            data = self._make_request("GET", "/portfolio/positions")
            positions = [Position(p) for p in data.get("positions", [])]
            logger.debug(f"Fetched {len(positions)} positions")
            return positions
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    def get_orders(self, status: Optional[str] = None) -> List[Order]:
        """
        Get orders (all or filtered by status).

        Args:
            status: Filter by status (resting, canceled, executed)
        """
        params = {}
        if status:
            params["status"] = status

        try:
            data = self._make_request("GET", "/portfolio/orders", params=params)
            orders = [Order(o) for o in data.get("orders", [])]
            logger.debug(f"Fetched {len(orders)} orders")
            return orders
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            return []

    def get_fills(self, ticker: Optional[str] = None) -> List[Trade]:
        """Get trade fills (executed orders)"""
        params = {}
        if ticker:
            params["ticker"] = ticker

        try:
            data = self._make_request("GET", "/portfolio/fills", params=params)
            fills = [Trade(f) for f in data.get("fills", [])]
            logger.debug(f"Fetched {len(fills)} fills")
            return fills
        except Exception as e:
            logger.error(f"Failed to fetch fills: {e}")
            return []

    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        try:
            data = self._make_request("GET", "/portfolio/balance")
            balance = data.get("balance", {})
            return {
                "balance": balance.get("balance", 0) / 100,  # Convert cents to dollars
                "payout": balance.get("payout", 0) / 100,
            }
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {"balance": 0, "payout": 0}

    def get_market_history(
        self, ticker: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical price data for a market"""
        try:
            data = self._make_request(
                "GET", f"/markets/{ticker}/history", params={"limit": limit}
            )
            history = data.get("history", [])
            logger.debug(f"Fetched {len(history)} historical points for {ticker}")
            return history
        except Exception as e:
            logger.error(f"Failed to fetch history for {ticker}: {e}")
            return []

    def close(self):
        """Close the HTTP client"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
