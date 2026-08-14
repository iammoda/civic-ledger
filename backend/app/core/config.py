from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Civic Accountability Platform"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/civic_platform",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")
    anthropic_fast_model: str = Field(default="claude-haiku-4-5", alias="ANTHROPIC_FAST_MODEL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_monthly_budget_usd: float = Field(default=200.0, alias="LLM_MONTHLY_BUDGET_USD")
    # Inbound per-IP rate limiting (LLM-backed + public-write endpoints).
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    # Cached Ask answers: identical questions are answered for free. 0 = off.
    ask_cache_ttl_seconds: int = Field(default=86400, alias="ASK_CACHE_TTL_SECONDS")
    # Site-wide cap on freshly *generated* Ask answers per day; past it, Ask
    # degrades to search-only (cached answers keep working).
    ask_daily_generate_limit: int = Field(default=300, alias="ASK_DAILY_GENERATE_LIMIT")
    # Static admin token (review queue, corrections). Unset = admin disabled.
    admin_api_token: str = Field(default="", alias="ADMIN_API_TOKEN")
    # Members' Office Budget (annual, CAD). Published by the Board of Internal
    # Economy; set it from the current Members' Allowances and Services Manual.
    # 0 = budget context hidden in the UI (no invented numbers).
    mob_annual_budget: float = Field(default=0.0, alias="MOB_ANNUAL_BUDGET")
    # MP base sessional allowance (annual salary, CAD). 0 = hidden.
    mp_annual_salary: float = Field(default=0.0, alias="MP_ANNUAL_SALARY")
    # Registry of Lobbyists communications export (CSV or ZIP of CSV).
    lobby_export_url: str = Field(
        default="https://lobbycanada.gc.ca/media/exports/communications_ocl_cal.zip",
        alias="LOBBY_EXPORT_URL",
    )
    # Elections Canada contributions export (CSV or ZIP of CSV).
    contributions_export_url: str = Field(default="", alias="CONTRIBUTIONS_EXPORT_URL")
    # Local dir checked first for manually-downloaded exports (Cloudflare).
    imports_dir: str = Field(default="/Volumes/CivicLedgerData/imports", alias="IMPORTS_DIR")
    # Ignore influence records older than this year.
    influence_since_year: int = Field(default=2019, alias="INFLUENCE_SINCE_YEAR")
    # Expense flag thresholds (big-ticket per single item, by category).
    expense_big_contract: float = Field(default=25000.0, alias="EXPENSE_BIG_CONTRACT")
    expense_big_hospitality: float = Field(default=5000.0, alias="EXPENSE_BIG_HOSPITALITY")
    expense_big_travel: float = Field(default=15000.0, alias="EXPENSE_BIG_TRAVEL")
    # Quarterly category total vs caucus median.
    expense_outlier_multiplier: float = Field(default=2.5, alias="EXPENSE_OUTLIER_MULTIPLIER")
    expense_outlier_floor: float = Field(default=10000.0, alias="EXPENSE_OUTLIER_FLOOR")
    backend_cors_origins: str = Field(
        default="http://localhost:3000",
        alias="BACKEND_CORS_ORIGINS",
    )
    ingestion_user_agent: str = Field(
        default="civic-platform/0.1 (+https://example.com)",
        alias="INGESTION_USER_AGENT",
    )
    default_jurisdiction: str = Field(default="ca", alias="DEFAULT_JURISDICTION")
    default_chamber: str = Field(default="house", alias="DEFAULT_CHAMBER")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
