import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
try:
    load_dotenv(BASE_DIR / ".env")
except OSError:
    # 生产由 systemd EnvironmentFile 注入环境变量；.env 权限受限时静默跳过，
    # 避免应用因无法读取环境文件而崩溃。
    pass


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def normalize_database_url(value):
    if not value:
        return value
    if value.startswith("postgres://"):
        value = "postgresql://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def production_base_url():
    return (os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")


class Config:
    APP_ENV = "base"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024
    UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", BASE_DIR / "app" / "static" / "uploads"))
    ID_PHOTO_FOLDER = Path(os.getenv("ID_PHOTO_FOLDER", BASE_DIR / "instance" / "id_photos"))
    WTF_CSRF_TIME_LIMIT = None
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    FEATURE_SURVEYS_PUBLIC = env_bool("FEATURE_SURVEYS_PUBLIC", True)
    FEATURE_TUTORING_PUBLIC = env_bool("FEATURE_TUTORING_PUBLIC", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    TRUST_PROXY = env_bool("TRUST_PROXY", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_REQUESTS = env_bool("LOG_REQUESTS", True)
    PREFERRED_URL_SCHEME = "http"
    # AI 助手（DeepSeek，OpenAI 兼容接口）
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "60"))
    # 价格单位：元/百万 tokens（deepseek-v4-flash 官方平时价，可在 .env 中覆盖）
    DEEPSEEK_INPUT_PRICE_PER_1M = float(os.getenv("DEEPSEEK_INPUT_PRICE_PER_1M", "1"))
    DEEPSEEK_INPUT_CACHE_HIT_PRICE_PER_1M = float(os.getenv("DEEPSEEK_INPUT_CACHE_HIT_PRICE_PER_1M", "0.02"))
    DEEPSEEK_OUTPUT_PRICE_PER_1M = float(os.getenv("DEEPSEEK_OUTPUT_PRICE_PER_1M", "2"))


class DevelopmentConfig(Config):
    APP_ENV = "development"
    DEBUG = env_bool("FLASK_DEBUG", True)
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'campus_hub.db').as_posix()}"
    ))


class ProductionConfig(Config):
    APP_ENV = "production"
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.getenv("DATABASE_URL"))
    APP_BASE_URL = production_base_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
    }
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    TRUST_PROXY = env_bool("TRUST_PROXY", True)


class TestConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-only"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"
    TRUST_PROXY = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestConfig,
}


def config_from_env():
    return CONFIG_MAP.get(os.getenv("APP_ENV", "development").lower(), DevelopmentConfig)
