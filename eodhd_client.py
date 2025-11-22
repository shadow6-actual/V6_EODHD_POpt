# EODHD API Client
# Handles all API interactions with EODHD service

import time
import logging
import requests
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class EODHDClient:
    """
    Client for EODHD (EOD Historical Data) API
    
    Documentation: https://eodhd.com/financial-apis/
    """
    
    def __init__(self, api_token: str, base_url: str = "https://eodhd.com/api"):
        """
        Initialize EODHD API client
        
        Args:
            api_token: Your EODHD API token
            base_url: Base URL for EODHD API
        """
        self.api_token = api_token
        self.base_url = base_url.rstrip('/')
        
        # API usage tracking
        self.calls_today = 0
        self.max_calls_per_day = 100000
        self.calls_by_endpoint = {}
        
        # Setup requests session with retry logic
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"EODHD API Client initialized")
    
    def _track_api_call(self, endpoint: str):
        """Track API call for rate limiting"""
        self.calls_today += 1
        self.calls_by_endpoint[endpoint] = self.calls_by_endpoint.get(endpoint, 0) + 1
        
        if self.calls_today >= self.max_calls_per_day:
            logger.error(f"❌ API call limit reached: {self.calls_today}/{self.max_calls_per_day}")
            raise Exception("EODHD API daily limit reached")
        
        if self.calls_today % 1000 == 0:
            logger.info(f"📊 API calls today: {self.calls_today:,}")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        Make API request with error handling
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            timeout: Request timeout in seconds
            
        Returns:
            Response data as dictionary
        """
        if params is None:
            params = {}
        
        # Add API token to params
        params['api_token'] = self.api_token
        params['fmt'] = params.get('fmt', 'json')  # Default to JSON
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            logger.debug(f"API Request: {endpoint}")
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            
            self._track_api_call(endpoint)
            
            # Parse response based on format
            if params.get('fmt') == 'csv':
                return response.text
            else:
                return response.json()
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error(f"Rate limit exceeded on {endpoint}")
                raise Exception("Rate limit exceeded. Please wait and try again.")
            elif e.response.status_code == 401:
                logger.error(f"Authentication failed. Check your API token.")
                raise Exception("Invalid API token")
            else:
                logger.error(f"HTTP error on {endpoint}: {e}")
                raise
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout on {endpoint}")
            raise Exception(f"Request timeout after {timeout} seconds")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on {endpoint}: {e}")
            raise
    
    # ========================================================================
    # EXCHANGE AND SYMBOL ENDPOINTS
    # ========================================================================
    
    def get_exchanges_list(self) -> List[Dict]:
        """
        Get list of all supported exchanges
        
        Returns:
            List of exchange dictionaries with name, code, country, currency
            
        Example response:
            [
                {
                    "Name": "USAStocks",
                    "Code": "US",
                    "OperatingMIC": "XNAS,XNYS",
                    "Country": "USA",
                    "Currency": "USD",
                    "CountryISO2": "US",
                    "CountryISO3": "USA"
                },
                ...
            ]
        """
        return self._make_request("exchanges-list")
    
    def get_exchange_symbols(self, exchange_code: str, delisted: bool = False) -> List[Dict]:
        """
        Get all symbols traded on an exchange
        
        Args:
            exchange_code: Exchange code (e.g., 'US', 'LSE', 'XETRA')
            delisted: Include delisted symbols (default: False)
            
        Returns:
            List of symbol dictionaries
            
        Example response:
            [
                {
                    "Code": "AAPL",
                    "Name": "Apple Inc.",
                    "Country": "USA",
                    "Exchange": "US",
                    "Currency": "USD",
                    "Type": "Common Stock",
                    "Isin": "US0378331005"
                },
                ...
            ]
        """
        endpoint = f"exchange-symbol-list/{exchange_code}"
        params = {'delisted': '1' if delisted else '0'}
        return self._make_request(endpoint, params)
    
    def search_ticker(self, query: str) -> List[Dict]:
        """
        Search for tickers by name or symbol
        
        Args:
            query: Search query (ticker symbol or company name)
            
        Returns:
            List of matching tickers
        """
        return self._make_request("search", {'s': query})
    
    # ========================================================================
    # END-OF-DAY HISTORICAL DATA
    # ========================================================================
    
    def get_eod_historical(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        period: str = 'd'
    ) -> List[Dict]:
        """
        Get historical EOD prices for a single ticker
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL.US')
            from_date: Start date YYYY-MM-DD (optional)
            to_date: End date YYYY-MM-DD (optional)
            period: 'd' for daily, 'w' for weekly, 'm' for monthly
            
        Returns:
            List of price dictionaries with date, open, high, low, close, adjusted_close, volume
            
        Example response:
            [
                {
                    "date": "2023-01-03",
                    "open": 130.28,
                    "high": 130.90,
                    "low": 124.17,
                    "close": 125.07,
                    "adjusted_close": 124.29,
                    "volume": 112117471
                },
                ...
            ]
        """
        endpoint = f"eod/{symbol}"
        params = {'period': period}
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        return self._make_request(endpoint, params)
    
    def get_eod_bulk(
        self,
        exchange: str,
        date: Optional[str] = None,
        symbols: Optional[str] = None,
        filter_extended: bool = False
    ) -> List[Dict]:
        """
        Download EOD data for entire exchange in one call (BULK API)
        
        This is MUCH more efficient than individual calls - downloads 50K+ tickers in seconds!
        Uses 100 API calls per exchange.
        
        Args:
            exchange: Exchange code (e.g., 'US', 'LSE')
            date: Specific date YYYY-MM-DD (default: last trading day)
            symbols: Comma-separated list of specific symbols (optional)
            filter_extended: Include extended technical data (default: False)
            
        Returns:
            List of price dictionaries for all symbols on exchange
        """
        endpoint = f"eod-bulk-last-day/{exchange}"
        params = {}
        
        if date:
            params['date'] = date
        if symbols:
            params['symbols'] = symbols
        if filter_extended:
            params['filter'] = 'extended'
        
        return self._make_request(endpoint, params)
    
    # ========================================================================
    # SPLITS AND DIVIDENDS
    # ========================================================================
    
    def get_splits(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Get stock splits for a ticker
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL.US')
            from_date: Start date YYYY-MM-DD (optional)
            to_date: End date YYYY-MM-DD (optional)
            
        Returns:
            List of split dictionaries
            
        Example response:
            [
                {
                    "date": "2020-08-31",
                    "split": "4/1"
                },
                ...
            ]
        """
        endpoint = f"splits/{symbol}"
        params = {}
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        return self._make_request(endpoint, params)
    
    def get_dividends(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Get dividend history for a ticker
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL.US')
            from_date: Start date YYYY-MM-DD (optional)
            to_date: End date YYYY-MM-DD (optional)
            
        Returns:
            List of dividend dictionaries
            
        Example response (extended format for US stocks):
            [
                {
                    "date": "2023-02-10",
                    "declarationDate": "2023-01-26",
                    "recordDate": "2023-02-13",
                    "paymentDate": "2023-02-16",
                    "value": 0.23,
                    "unadjustedValue": 0.23,
                    "currency": "USD"
                },
                ...
            ]
        """
        endpoint = f"div/{symbol}"
        params = {}
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        return self._make_request(endpoint, params)
    
    def get_bulk_splits(self, exchange: str, date: Optional[str] = None) -> List[Dict]:
        """
        Download all splits for an exchange on a specific day (BULK API)
        
        Args:
            exchange: Exchange code (e.g., 'US')
            date: Specific date YYYY-MM-DD (default: last trading day)
            
        Returns:
            List of split dictionaries for the entire exchange
        """
        endpoint = f"eod-bulk-last-day/{exchange}"
        params = {'type': 'splits'}
        
        if date:
            params['date'] = date
        
        return self._make_request(endpoint, params)
    
    def get_bulk_dividends(self, exchange: str, date: Optional[str] = None) -> List[Dict]:
        """
        Download all dividends for an exchange on a specific day (BULK API)
        
        Args:
            exchange: Exchange code (e.g., 'US')
            date: Specific date YYYY-MM-DD (default: last trading day)
            
        Returns:
            List of dividend dictionaries for the entire exchange
        """
        endpoint = f"eod-bulk-last-day/{exchange}"
        params = {'type': 'dividends'}
        
        if date:
            params['date'] = date
        
        return self._make_request(endpoint, params)
    
    # ========================================================================
    # LIVE PRICES (DELAYED)
    # ========================================================================
    
    def get_live_prices(self, symbols: str, filter_field: Optional[str] = None) -> Dict:
        """
        Get live (delayed 15-20 min) prices for one or more symbols
        
        Args:
            symbols: Single symbol or comma-separated list (e.g., 'AAPL.US,MSFT.US')
            filter_field: Return only specific field (e.g., 'close', 'volume')
            
        Returns:
            Dictionary with current price data
        """
        params = {'s': symbols}
        if filter_field:
            params['filter'] = filter_field
        
        return self._make_request("real-time", params)
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_api_usage_today(self) -> Dict[str, int]:
        """
        Get API usage statistics for today
        
        Returns:
            Dictionary with call counts by endpoint
        """
        return {
            'total_calls': self.calls_today,
            'remaining_calls': self.max_calls_per_day - self.calls_today,
            'by_endpoint': self.calls_by_endpoint
        }
    
    def reset_daily_counter(self):
        """Reset API call counter (call at start of each day)"""
        self.calls_today = 0
        self.calls_by_endpoint = {}
        logger.info("API usage counter reset")
    
    def to_dataframe(self, data: List[Dict], date_column: str = 'date') -> pd.DataFrame:
        """
        Convert API response to pandas DataFrame
        
        Args:
            data: List of dictionaries from API
            date_column: Name of date column to parse
            
        Returns:
            pandas DataFrame with parsed dates
        """
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column])
            df = df.set_index(date_column)
        
        return df
    
    def validate_symbol_format(self, symbol: str) -> bool:
        """
        Validate EODHD symbol format (should be TICKER.EXCHANGE)
        
        Args:
            symbol: Symbol to validate (e.g., 'AAPL.US')
            
        Returns:
            True if valid format, False otherwise
        """
        parts = symbol.split('.')
        return len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0
    
    def construct_symbol(self, ticker: str, exchange: str) -> str:
        """
        Construct EODHD symbol format
        
        Args:
            ticker: Ticker code (e.g., 'AAPL')
            exchange: Exchange code (e.g., 'US')
            
        Returns:
            Formatted symbol (e.g., 'AAPL.US')
        """
        return f"{ticker}.{exchange}"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_eodhd_client(api_token: str) -> EODHDClient:
    """
    Create and return an EODHD API client
    
    Args:
        api_token: Your EODHD API token
        
    Returns:
        Initialized EODHDClient instance
    """
    return EODHDClient(api_token)


def get_last_n_trading_days(n: int, end_date: Optional[date] = None) -> List[str]:
    """
    Get list of last N trading days (approximate - excludes weekends only)
    
    Args:
        n: Number of trading days to return
        end_date: End date (default: today)
        
    Returns:
        List of date strings in YYYY-MM-DD format
    """
    if end_date is None:
        end_date = date.today()
    
    dates = []
    current_date = end_date
    
    while len(dates) < n:
        # Skip weekends
        if current_date.weekday() < 5:  # Monday=0, Sunday=6
            dates.append(current_date.strftime('%Y-%m-%d'))
        current_date -= timedelta(days=1)
    
    return list(reversed(dates))


if __name__ == "__main__":
    # Example usage
    print("EODHD API Client loaded successfully")
    print("\nExample usage:")
    print("  client = EODHDClient('your_api_token_here')")
    print("  exchanges = client.get_exchanges_list()")
    print("  symbols = client.get_exchange_symbols('US')")
    print("  prices = client.get_eod_historical('AAPL.US', from_date='2023-01-01')")
