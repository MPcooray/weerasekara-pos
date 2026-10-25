import pytest

from app.core.config import Settings


def production_settings(**overrides):
    values = {
        "app_env": "production",
        "secret_key": "x" * 64,
        "database_url": "postgresql+psycopg://tetrova_app:long-random-password-value@db/pos",
        "cors_origins": ["https://pos.example.test"],
        "trusted_hosts": ["pos.example.test"],
        "allow_initial_admin_bootstrap": False,
        "initial_admin_password": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_secure_production_configuration_is_accepted():
    production_settings().validate_production()


@pytest.mark.parametrize(
    "override",
    [
        {"secret_key": "local-development-secret-change-me"},
        {"database_url": "sqlite:///unsafe.db"},
        {"database_url": "postgresql+psycopg://postgres:long-random-password-value@db/pos"},
        {"database_url": "postgresql+psycopg://tetrova_app:short@db/pos"},
        {"cors_origins": ["http://pos.example.test"]},
        {"trusted_hosts": ["*"]},
        {"allow_initial_admin_bootstrap": True},
        {"initial_admin_password": "AccidentalProductionPassword123!"},
        {"cors_origin_regex": ".*"},
        {"access_token_expire_minutes": 120},
    ],
)
def test_insecure_production_configuration_is_rejected(override):
    with pytest.raises(RuntimeError):
        production_settings(**override).validate_production()
