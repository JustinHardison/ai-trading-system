"""
Configuration management for the AI trading system
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # LLM API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    # Interactive Brokers
    ib_account: str = Field(default="", alias="IB_ACCOUNT")
    ib_host: str = Field(default="127.0.0.1", alias="IB_HOST")
    ib_port: int = Field(default=7497, alias="IB_PORT")
    ib_client_id: int = Field(default=1, alias="IB_CLIENT_ID")

    # MetaTrader
    mt5_login: str = Field(default="", alias="MT5_LOGIN")
    mt5_password: str = Field(default="", alias="MT5_PASSWORD")
    mt5_server: str = Field(default="", alias="MT5_SERVER")

    # Alpaca
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(default="https://paper-api.alpaca.markets", alias="ALPACA_BASE_URL")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="trading_system", alias="POSTGRES_DB")
    postgres_user: str = Field(default="trader", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # TimescaleDB
    timescale_host: str = Field(default="localhost", alias="TIMESCALE_HOST")
    timescale_port: int = Field(default=5432, alias="TIMESCALE_PORT")
    timescale_db: str = Field(default="trading_timeseries", alias="TIMESCALE_DB")
    timescale_user: str = Field(default="trader", alias="TIMESCALE_USER")
    timescale_password: str = Field(default="", alias="TIMESCALE_PASSWORD")

    # Trading Configuration
    trading_mode: Literal["paper", "live"] = Field(default="paper", alias="TRADING_MODE")
    max_position_size: float = Field(default=100000.0, alias="MAX_POSITION_SIZE")
    max_daily_loss_pct: float = Field(default=0.04, alias="MAX_DAILY_LOSS_PCT")
    max_overall_loss_pct: float = Field(default=0.08, alias="MAX_OVERALL_LOSS_PCT")
    risk_per_trade_pct: float = Field(default=0.02, alias="RISK_PER_TRADE_PCT")

    # Prop Firm Configuration
    prop_firm: Literal["FTMO", "TopStep", "FundedNext", "Custom"] = Field(default="FTMO", alias="PROP_FIRM")
    account_size: float = Field(default=100000.0, alias="ACCOUNT_SIZE")
    account_type: Literal["challenge", "verification", "funded"] = Field(default="challenge", alias="ACCOUNT_TYPE")

    # Strategy Configuration
    strategy_mode: Literal["rl", "traditional", "hybrid"] = Field(default="hybrid", alias="STRATEGY_MODE")
    primary_rl_algorithm: Literal["PPO", "DQN", "A2C", "DDPG"] = Field(default="PPO", alias="PRIMARY_RL_ALGORITHM")
    enable_llm_analysis: bool = Field(default=True, alias="ENABLE_LLM_ANALYSIS")
    llm_provider: Literal["anthropic", "openai", "groq", "ollama"] = Field(default="anthropic", alias="LLM_PROVIDER")

    # Monitoring
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    prometheus_port: int = Field(default=9090, alias="PROMETHEUS_PORT")

    # Alerts
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")
    alert_email: str = Field(default="", alias="ALERT_EMAIL")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", alias="LOG_LEVEL")
    log_to_file: bool = Field(default=True, alias="LOG_TO_FILE")
    log_dir: str = Field(default="./logs", alias="LOG_DIR")

    # Feature Flags
    enable_backtesting: bool = Field(default=True, alias="ENABLE_BACKTESTING")
    enable_paper_trading: bool = Field(default=True, alias="ENABLE_PAPER_TRADING")
    enable_live_trading: bool = Field(default=False, alias="ENABLE_LIVE_TRADING")
    enable_automated_retraining: bool = Field(default=True, alias="ENABLE_AUTOMATED_RETRAINING")
    enable_sentiment_analysis: bool = Field(default=True, alias="ENABLE_SENTIMENT_ANALYSIS")

    # Trading Symbols
    trading_symbols: str = Field(default="SPY,QQQ,AAPL", alias="TRADING_SYMBOLS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def timescale_url(self) -> str:
        """Get TimescaleDB connection URL"""
        return f"postgresql://{self.timescale_user}:{self.timescale_password}@{self.timescale_host}:{self.timescale_port}/{self.timescale_db}"

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Prop firm rule configurations
PROP_FIRM_RULES = {
    "FTMO": {
        "max_daily_loss_pct": 0.05,
        "max_overall_loss_pct": 0.10,
        "min_trading_days": 4,
        "max_simultaneous_orders": 200,
        "max_daily_positions": 2000,
        "profit_target_challenge_pct": 0.10,
        "profit_target_verification_pct": 0.05,
        "challenge_days": 30,
        "verification_days": 60,
        "forbidden_strategies": ["martingale", "grid_trading"],
        "trading_hours": "24/5",
        "allow_weekend_trading": False,
        "allow_news_trading": True,
    },
    "TopStep": {
        "max_daily_loss": {
            50000: 2000,
            100000: 3000,
            150000: 4500,
        },
        "profit_target": {
            50000: 3000,
            100000: 6000,
            150000: 9000,
        },
        "consistency_rule": True,
        "max_single_day_profit_pct": 0.50,
        "automated_trading_allowed": False,
        "max_contracts": {
            50000: 10,
            100000: 20,
            150000: 30,
        },
        "trading_hours": "futures_market_hours",
        "allow_overnight_positions": True,
    },
    "FundedNext": {
        "max_daily_loss_pct": 0.05,
        "max_overall_loss_pct": 0.10,
        "profit_target_pct": 0.10,
        "min_trading_days": 3,
        "trading_hours": "24/5",
        "allow_weekend_trading": False,
        "allow_ea_trading": True,
        "allow_news_trading": True,
        "allow_copy_trading": True,
    }
}
