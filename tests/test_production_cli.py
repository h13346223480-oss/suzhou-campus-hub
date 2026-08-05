from app.extensions import db
from app.models import User


def test_bootstrap_admin_requires_environment_on_empty_database(app, monkeypatch):
    with app.app_context():
        User.query.delete()
        db.session.commit()
    for name in ("ADMIN_EMAIL", "ADMIN_NICKNAME", "ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    result = app.test_cli_runner().invoke(args=["bootstrap-admin"])
    assert result.exit_code != 0
    assert "ADMIN_EMAIL" in result.output


def test_bootstrap_admin_is_idempotent(app, monkeypatch):
    with app.app_context():
        User.query.delete()
        db.session.commit()
    monkeypatch.setenv("ADMIN_EMAIL", "ops@example.com")
    monkeypatch.setenv("ADMIN_NICKNAME", "运维管理员")
    monkeypatch.setenv("ADMIN_PASSWORD", "A-strong-password-2026")

    runner = app.test_cli_runner()
    first = runner.invoke(args=["bootstrap-admin"])
    second = runner.invoke(args=["bootstrap-admin"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "无需重复创建" in second.output
    assert "ops@example.com" not in first.output
    assert "ops@example.com" not in second.output
    with app.app_context():
        admin = User.query.filter_by(email="ops@example.com").one()
        assert admin.role == "admin"
        assert admin.verification_status == "verified"
        assert admin.check_password("A-strong-password-2026")


def test_reset_admin_password_uses_one_time_environment_variable(app, monkeypatch):
    new_password = "A-new-strong-password-2026"
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_RESET_PASSWORD", new_password)

    result = app.test_cli_runner().invoke(args=["reset-admin-password"])

    assert result.exit_code == 0
    assert "已安全重置" in result.output
    assert new_password not in result.output
    assert "admin@example.com" not in result.output
    with app.app_context():
        admin = User.query.filter_by(email="admin@example.com").one()
        student = User.query.filter_by(email="verified@example.com").one()
        assert admin.check_password(new_password)
        assert not admin.check_password("Password123!")
        assert student.check_password("Password123!")


def test_reset_admin_password_requires_one_time_variable(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.delenv("ADMIN_RESET_PASSWORD", raising=False)

    result = app.test_cli_runner().invoke(args=["reset-admin-password"])

    assert result.exit_code != 0
    assert "ADMIN_RESET_PASSWORD" in result.output
