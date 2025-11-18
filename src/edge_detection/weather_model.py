"""
Weather Model Strategy
Uses NOAA forecast data to predict weather outcomes and compare to market prices.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import httpx
from scipy import stats
import numpy as np

from src.edge_detection.speed_arbitrage import TradeSignal

logger = logging.getLogger(__name__)


class WeatherDataFetcher:
    """Fetch weather data from NOAA APIs"""

    FORECAST_URL = "https://api.weather.gov/gridpoints"
    STATIONS_URL = "https://api.weather.gov/stations"

    @staticmethod
    async def get_point_data(latitude: float, longitude: float) -> Optional[Dict]:
        """Get grid point data for a location"""
        url = f"https://api.weather.gov/points/{latitude},{longitude}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching point data: {e}")
            return None

    @staticmethod
    async def get_forecast(grid_x: int, grid_y: int, office: str) -> Optional[Dict]:
        """Get forecast for a grid point"""
        url = f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching forecast: {e}")
            return None

    @staticmethod
    async def get_quantitative_forecast(
        grid_x: int, grid_y: int, office: str
    ) -> Optional[Dict]:
        """Get quantitative forecast data (hourly temperatures, etc.)"""
        url = f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching quantitative forecast: {e}")
            return None


class TemperaturePredictor:
    """Predict temperature outcomes for Kalshi temperature markets"""

    MAJOR_CITIES = {
        "NYC": {"lat": 40.7128, "lon": -74.0060, "name": "New York"},
        "LAX": {"lat": 34.0522, "lon": -118.2437, "name": "Los Angeles"},
        "CHI": {"lat": 41.8781, "lon": -87.6298, "name": "Chicago"},
        "MIA": {"lat": 25.7617, "lon": -80.1918, "name": "Miami"},
        "DEN": {"lat": 39.7392, "lon": -104.9903, "name": "Denver"},
    }

    @staticmethod
    async def get_temperature_forecast(
        city_code: str, target_date: datetime
    ) -> Optional[Dict]:
        """
        Get temperature forecast for a city.

        Returns:
            Dict with predicted high, low, and probability distributions
        """
        if city_code not in TemperaturePredictor.MAJOR_CITIES:
            return None

        city = TemperaturePredictor.MAJOR_CITIES[city_code]

        # Get point data
        point_data = await WeatherDataFetcher.get_point_data(city["lat"], city["lon"])

        if not point_data:
            return None

        properties = point_data.get("properties", {})
        grid_x = properties.get("gridX")
        grid_y = properties.get("gridY")
        office = properties.get("gridId")

        if not all([grid_x, grid_y, office]):
            return None

        # Get quantitative forecast
        forecast_data = await WeatherDataFetcher.get_quantitative_forecast(
            grid_x, grid_y, office
        )

        if not forecast_data:
            return None

        # Extract temperature data
        properties = forecast_data.get("properties", {})
        temp_data = properties.get("temperature", {})
        values = temp_data.get("values", [])

        if not values:
            return None

        # Filter to target date
        target_temps = []
        for value in values:
            valid_time = value.get("validTime", "")
            # Parse ISO 8601 duration format
            try:
                time_str = valid_time.split("/")[0]
                forecast_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

                if forecast_time.date() == target_date.date():
                    temp_c = value.get("value")
                    if temp_c is not None:
                        # Convert Celsius to Fahrenheit
                        temp_f = temp_c * 9 / 5 + 32
                        target_temps.append(temp_f)
            except:
                continue

        if not target_temps:
            return None

        # Calculate statistics
        high = max(target_temps)
        low = min(target_temps)
        mean = np.mean(target_temps)
        std = np.std(target_temps) if len(target_temps) > 1 else 3.0  # Default 3°F uncertainty

        return {
            "high": high,
            "low": low,
            "mean": mean,
            "std": std,
            "num_forecasts": len(target_temps),
        }

    @staticmethod
    def calculate_temperature_probability(
        forecast: Dict, threshold: float, direction: str
    ) -> float:
        """
        Calculate probability temperature will be above/below threshold.

        Args:
            forecast: Forecast dict from get_temperature_forecast
            threshold: Temperature threshold in °F
            direction: 'above' or 'below'

        Returns:
            Probability (0-1)
        """
        mean = forecast["mean"]
        std = forecast.get("std", 3.0)

        # Use normal distribution
        if direction == "above":
            # P(X > threshold)
            z_score = (threshold - mean) / std
            probability = 1 - stats.norm.cdf(z_score)
        elif direction == "below":
            # P(X < threshold)
            z_score = (threshold - mean) / std
            probability = stats.norm.cdf(z_score)
        else:
            probability = 0.5

        return np.clip(probability, 0.01, 0.99)


class PrecipitationPredictor:
    """Predict precipitation outcomes"""

    @staticmethod
    async def get_precipitation_forecast(
        city_code: str, target_date: datetime
    ) -> Optional[Dict]:
        """
        Get precipitation forecast for a city.

        Returns:
            Dict with precipitation probability and expected amount
        """
        if city_code not in TemperaturePredictor.MAJOR_CITIES:
            return None

        city = TemperaturePredictor.MAJOR_CITIES[city_code]

        # Get point data
        point_data = await WeatherDataFetcher.get_point_data(city["lat"], city["lon"])

        if not point_data:
            return None

        properties = point_data.get("properties", {})
        grid_x = properties.get("gridX")
        grid_y = properties.get("gridY")
        office = properties.get("gridId")

        if not all([grid_x, grid_y, office]):
            return None

        # Get quantitative forecast
        forecast_data = await WeatherDataFetcher.get_quantitative_forecast(
            grid_x, grid_y, office
        )

        if not forecast_data:
            return None

        # Extract precipitation probability
        properties = forecast_data.get("properties", {})
        precip_prob_data = properties.get("probabilityOfPrecipitation", {})
        precip_values = precip_prob_data.get("values", [])

        target_probs = []
        for value in precip_values:
            valid_time = value.get("validTime", "")
            try:
                time_str = valid_time.split("/")[0]
                forecast_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

                if forecast_time.date() == target_date.date():
                    prob = value.get("value")
                    if prob is not None:
                        target_probs.append(prob)
            except:
                continue

        if not target_probs:
            return None

        # Take max probability for the day
        max_prob = max(target_probs) / 100  # Convert from percent

        return {"probability": max_prob, "num_forecasts": len(target_probs)}


class WeatherModel:
    """
    Weather prediction model that compares NOAA forecasts to market prices.

    Markets to target:
    - TEMP-{CITY}-{DATE}-B{THRESHOLD} (temperature above/below)
    - RAIN-{CITY}-{DATE} (will it rain)
    - SNOW-{CITY}-{DATE} (will it snow)
    """

    def __init__(self, config: Dict):
        self.config = config
        self.min_edge = config.get("min_edge", 0.08)
        self.forecast_horizon_days = config.get("forecast_horizon_days", 14)

        logger.info(
            f"Weather model initialized: min_edge={self.min_edge}, "
            f"horizon={self.forecast_horizon_days} days"
        )

    async def analyze_temperature_market(
        self, ticker: str, current_price: float
    ) -> Optional[TradeSignal]:
        """
        Analyze a temperature market.

        Example ticker: HIGHTEMP-NYC-23DEC15-B050 (NYC high temp above 50°F on Dec 15)
        """
        # Parse ticker
        parts = ticker.split("-")
        if len(parts) < 4:
            return None

        # Extract city, date, threshold
        try:
            city_code = parts[1]
            date_str = parts[2]
            threshold_str = parts[3]

            # Parse date (format: 23DEC15 = Dec 15, 2023)
            year = 2000 + int(date_str[0:2])
            month_str = date_str[2:5]
            day = int(date_str[5:7])

            month_map = {
                "JAN": 1,
                "FEB": 2,
                "MAR": 3,
                "APR": 4,
                "MAY": 5,
                "JUN": 6,
                "JUL": 7,
                "AUG": 8,
                "SEP": 9,
                "OCT": 10,
                "NOV": 11,
                "DEC": 12,
            }
            month = month_map.get(month_str)

            if not month:
                return None

            target_date = datetime(year, month, day)

            # Check if within forecast horizon
            days_ahead = (target_date - datetime.now()).days
            if days_ahead < 0 or days_ahead > self.forecast_horizon_days:
                return None

            # Parse threshold (B050 = above 50°F, L050 = below 50°F)
            direction = "above" if threshold_str.startswith("B") else "below"
            threshold = float(threshold_str[1:])

        except Exception as e:
            logger.error(f"Error parsing temperature ticker {ticker}: {e}")
            return None

        # Get forecast
        forecast = await TemperaturePredictor.get_temperature_forecast(
            city_code, target_date
        )

        if not forecast:
            logger.debug(f"No forecast available for {ticker}")
            return None

        # Calculate model probability
        model_probability = TemperaturePredictor.calculate_temperature_probability(
            forecast, threshold, direction
        )

        # Compare to market price
        market_probability = current_price

        # Calculate edge
        edge = abs(model_probability - market_probability)

        if edge < self.min_edge:
            return None

        # Determine side to trade
        if model_probability > market_probability:
            side = "yes"
            signal_type = "BUY"
        else:
            side = "no"
            signal_type = "BUY"

        # Calculate confidence based on forecast quality
        confidence = 0.7  # Base confidence
        if forecast.get("num_forecasts", 0) > 10:
            confidence += 0.1
        if forecast.get("std", 10) < 5:  # Low uncertainty
            confidence += 0.1

        confidence = min(confidence, 0.95)

        # Create signal
        signal = TradeSignal(
            signal_id=f"weather_{ticker}_{datetime.now().timestamp()}",
            timestamp=datetime.utcnow(),
            source="weather_model",
            ticker=ticker,
            side=side,
            signal_type=signal_type,
            confidence=confidence,
            edge_percentage=edge,
            current_price=market_probability,
            fair_value=model_probability,
            reasoning=f"Weather model: {forecast['mean']:.1f}°F ±{forecast.get('std', 3):.1f}°F. "
            f"Model probability {model_probability:.1%} vs market {market_probability:.1%}. "
            f"Edge: {edge:.1%}",
            event_data=forecast,
        )

        logger.info(f"Generated weather signal: {signal}")
        return signal

    async def analyze_precipitation_market(
        self, ticker: str, current_price: float
    ) -> Optional[TradeSignal]:
        """
        Analyze a precipitation market.

        Example ticker: RAIN-NYC-23DEC15 (will it rain in NYC on Dec 15)
        """
        # Similar logic to temperature
        parts = ticker.split("-")
        if len(parts) < 3:
            return None

        try:
            city_code = parts[1]
            date_str = parts[2]

            # Parse date
            year = 2000 + int(date_str[0:2])
            month_str = date_str[2:5]
            day = int(date_str[5:7])

            month_map = {
                "JAN": 1,
                "FEB": 2,
                "MAR": 3,
                "APR": 4,
                "MAY": 5,
                "JUN": 6,
                "JUL": 7,
                "AUG": 8,
                "SEP": 9,
                "OCT": 10,
                "NOV": 11,
                "DEC": 12,
            }
            month = month_map.get(month_str)

            if not month:
                return None

            target_date = datetime(year, month, day)

            # Check if within forecast horizon
            days_ahead = (target_date - datetime.now()).days
            if days_ahead < 0 or days_ahead > self.forecast_horizon_days:
                return None

        except Exception as e:
            logger.error(f"Error parsing precipitation ticker {ticker}: {e}")
            return None

        # Get forecast
        forecast = await PrecipitationPredictor.get_precipitation_forecast(
            city_code, target_date
        )

        if not forecast:
            return None

        # Model probability is NOAA's precipitation probability
        model_probability = forecast["probability"]
        market_probability = current_price

        # Calculate edge
        edge = abs(model_probability - market_probability)

        if edge < self.min_edge:
            return None

        # Determine side
        if model_probability > market_probability:
            side = "yes"
        else:
            side = "no"

        # Confidence
        confidence = 0.75

        signal = TradeSignal(
            signal_id=f"weather_{ticker}_{datetime.now().timestamp()}",
            timestamp=datetime.utcnow(),
            source="weather_model",
            ticker=ticker,
            side=side,
            signal_type="BUY",
            confidence=confidence,
            edge_percentage=edge,
            current_price=market_probability,
            fair_value=model_probability,
            reasoning=f"NOAA precipitation forecast: {model_probability:.1%} vs "
            f"market {market_probability:.1%}. Edge: {edge:.1%}",
            event_data=forecast,
        )

        logger.info(f"Generated precipitation signal: {signal}")
        return signal

    async def scan_weather_markets(
        self, markets: List[str], market_prices: Dict[str, float]
    ) -> List[TradeSignal]:
        """
        Scan all weather-related markets for opportunities.

        Args:
            markets: List of market tickers
            market_prices: Dict of ticker -> current price

        Returns:
            List of trade signals
        """
        signals = []

        for ticker in markets:
            # Skip if no price data
            if ticker not in market_prices:
                continue

            current_price = market_prices[ticker]

            # Analyze based on market type
            if "TEMP" in ticker or "HIGH" in ticker or "LOW" in ticker:
                signal = await self.analyze_temperature_market(ticker, current_price)
                if signal:
                    signals.append(signal)

            elif "RAIN" in ticker or "PRECIP" in ticker:
                signal = await self.analyze_precipitation_market(ticker, current_price)
                if signal:
                    signals.append(signal)

        logger.info(f"Weather model generated {len(signals)} signals")
        return signals
