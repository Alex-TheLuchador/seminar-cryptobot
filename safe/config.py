import os
from dataclasses import dataclass

from dotenv import load_dotenv
from hyperliquid.utils import constants

MODEL = "claude-sonnet-4-6"
TESTNET_URL = constants.TESTNET_API_URL

_REQUIRED = [
    "HYPERLIQUID_API_PRIVATE_KEY",
    "HYPERLIQUID_API_WALLET_ADDRESS",
    "HYPERLIQUID_MAIN_WALLET_ADDRESS",
    "CLAUDE_API_KEY",
]


@dataclass(frozen=True)
class Config:
    api_private_key: str
    api_wallet_address: str
    main_wallet_address: str
    claude_api_key: str
    dry_run: bool  # True = log intent only, never call exchange.market_open

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        missing = [k for k in _REQUIRED if not os.getenv(k)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
        # DRY_RUN defaults to true — must explicitly set DRY_RUN=false to trade.
        dry_run = os.getenv("DRY_RUN", "true").strip().lower() != "false"
        return cls(
            api_private_key=os.environ["HYPERLIQUID_API_PRIVATE_KEY"],
            api_wallet_address=os.environ["HYPERLIQUID_API_WALLET_ADDRESS"],
            main_wallet_address=os.environ["HYPERLIQUID_MAIN_WALLET_ADDRESS"],
            claude_api_key=os.environ["CLAUDE_API_KEY"],
            dry_run=dry_run,
        )
