"""API Configuration"""

# CORS Settings
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

# API Settings
API_TITLE = "Portfolio Optimizer API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "REST API for portfolio optimization and risk analysis"

# Rate Limiting
MAX_ASSETS_PER_REQUEST = 50
MAX_FRONTIER_POINTS = 200

# Default Values
DEFAULT_RISK_FREE_RATE = 0.02
DEFAULT_RETURN_FREQUENCY = "M"
DEFAULT_FRONTIER_POINTS = 50
