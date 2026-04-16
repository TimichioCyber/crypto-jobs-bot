from __future__ import annotations

ROLE_LABELS: dict[str, str] = {
    "developer": "Developer 👨‍💻",
    "product": "Product 📦",
    "marketing": "Marketing 📣",
    "community": "Community 🌍",
    "research": "Research / Trading 📈",
    "design": "Design 🎨",
}

DATE_LABELS: dict[str, str] = {
    "1": "Today",
    "3": "Last 3 days",
    "7": "Last 7 days",
    "30": "Last 30 days",
}

GREENHOUSE_BOARDS: dict[str, str] = {
    "coinbase": "Coinbase",
    "kraken": "Kraken",
    "chainalysis": "Chainalysis",
    "alchemy": "Alchemy",
    "consensys": "Consensys",
    "aave": "Aave",
    "opensea": "OpenSea",
    "figure": "Figure",
}

DEFAULT_ROLE = "developer"
DEFAULT_DATE_RANGE = "7"

MAX_RESULTS_PER_SEARCH = 15
HTTP_TIMEOUT_SECONDS = 20
USER_AGENT = "CryptoJobsBot/1.0"
