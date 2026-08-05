import pytest
from flask import request

from app import create_app
from app.extensions import db
from app.models import Guide
from config import ProductionConfig, TestConfig, normalize_database_url, production_base_url


PROTECTED_ROUTES = ["/posts", "/guides", "/guides/faq", "/guides/campus-map", "/english-hub"]


def test_anonymous_users_are_redirected_from_campus_content(client):
    for path in PROTECTED_ROUTES:
        response = client.get(path)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]


def test_pending_student_cannot_read_campus_content(client, login):
    login("pending@example.com")
    for path in PROTECTED_ROUTES:
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")


def test_verified_student_can_read_campus_content(client, login):
    login("verified@example.com")
    for path in PROTECTED_ROUTES:
        response = client.get(path)
        assert response.status_code == 200


def test_public_home_does_not_leak_latest_campus_content(client, app):
    with app.app_context():
        db.session.add(Guide(title="仅认证可见指南", slug="protected-guide", summary="校内摘要",
                             content="校内详细内容", category="报到指南", status="published"))
        db.session.commit()
    response = client.get("/")
    assert response.status_code == 200
    assert "演示信息：学习搭子" not in response.text
    assert "仅认证可见指南" not in response.text
    assert "公开网址不代表校内内容公开" in response.text


def test_health_check_reports_database_status(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "reachable"}


def test_security_headers_are_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert len(response.headers["X-Request-ID"]) == 32


def test_request_id_accepts_safe_value_and_rejects_header_injection(client):
    safe = client.get("/", headers={"X-Request-ID": "mobile-check-001"})
    assert safe.headers["X-Request-ID"] == "mobile-check-001"
    unsafe = client.get("/", headers={"X-Request-ID": "not allowed spaces"})
    assert unsafe.headers["X-Request-ID"] != "not allowed spaces"
    assert len(unsafe.headers["X-Request-ID"]) == 32


def test_proxy_fix_honors_one_trusted_forwarded_layer():
    class ProxyTestConfig(TestConfig):
        TRUST_PROXY = True

    app = create_app(ProxyTestConfig)

    @app.get("/_test_scheme")
    def test_scheme():
        return request.scheme

    response = app.test_client().get("/_test_scheme", headers={"X-Forwarded-Proto": "https"})
    assert response.text == "https"


def test_postgres_urls_are_normalized_for_psycopg3():
    assert normalize_database_url("postgres://user:pass@db/app") == "postgresql+psycopg://user:pass@db/app"
    assert normalize_database_url("postgresql://user:pass@db/app") == "postgresql+psycopg://user:pass@db/app"
    assert normalize_database_url("postgresql+psycopg://user:pass@db/app") == "postgresql+psycopg://user:pass@db/app"


def test_production_rejects_short_secret_before_startup():
    class UnsafeProductionConfig(TestConfig):
        APP_ENV = "production"
        SECRET_KEY = "short"
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://user:pass@db/app"
        APP_BASE_URL = "https://campus.example.com"

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(UnsafeProductionConfig)


def test_production_rejects_sqlite_database():
    class UnsafeProductionConfig(TestConfig):
        APP_ENV = "production"
        SECRET_KEY = "x" * 64
        SQLALCHEMY_DATABASE_URI = "sqlite:///production.db"
        APP_BASE_URL = "https://campus.example.com"

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        create_app(UnsafeProductionConfig)


def test_production_rejects_non_https_base_url():
    class UnsafeProductionConfig(TestConfig):
        APP_ENV = "production"
        SECRET_KEY = "x" * 64
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://user:pass@db/app"
        APP_BASE_URL = "http://campus.example.com"

    with pytest.raises(RuntimeError, match="https"):
        create_app(UnsafeProductionConfig)


def test_safe_production_config_builds_postgres_engine_and_hsts_headers():
    class SafeProductionConfig(ProductionConfig):
        TESTING = True
        SECRET_KEY = "x" * 64
        SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://user:pass@127.0.0.1/campus_hub"
        APP_BASE_URL = "https://campus.example.com"
        TRUST_PROXY = True

    app = create_app(SafeProductionConfig)
    response = app.test_client().get("/about", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert app.config["SESSION_COOKIE_SECURE"] is True
    with app.app_context():
        assert db.engine.url.drivername == "postgresql+psycopg"


def test_render_external_url_can_supply_production_base_url(monkeypatch):
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://campus-hub.onrender.com")
    assert production_base_url() == "https://campus-hub.onrender.com"
