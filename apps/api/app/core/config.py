from decimal import Decimal
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "Tetrova Optical POS"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = Field(default="local-development-secret-change-me", min_length=32)
    access_token_expire_minutes: int = 30
    database_url: str = "sqlite:///./tetrova_pos.db"
    cors_origins: list[str] | str = ["http://localhost:5173"]
    cors_origin_regex: str | None = None
    initial_tenant_name: str = "Weerasekara Optics"
    initial_tenant_slug: str = "weerasekara-optics"
    initial_admin_email: str = "owner@weerasekara.local"
    initial_admin_password: str = ""
    allow_initial_admin_bootstrap: bool = False
    optical_power_min: Decimal = Decimal("-30.00")
    optical_power_max: Decimal = Decimal("30.00")
    optical_add_min: Decimal = Decimal("0.00")
    optical_add_max: Decimal = Decimal("6.00")
    optical_pd_min: Decimal = Decimal("20.00")
    optical_pd_max: Decimal = Decimal("90.00")
    require_quarter_diopter_steps: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def validate_production(self) -> None:
        if self.app_env == "production" and "change-me" in self.secret_key.lower():
            raise RuntimeError("A secure SECRET_KEY is required in production")

    @property
    def effective_cors_origin_regex(self) -> str | None:
        if self.cors_origin_regex:
            return self.cors_origin_regex
        if self.app_env == "development":
            return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        return None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
