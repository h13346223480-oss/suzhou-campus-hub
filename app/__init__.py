from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config_from_env
from .extensions import csrf, db, login_manager, migrate
from .utils.logging import configure_logging, register_request_logging


STATUS_LABELS = {
    "pending": "待处理",
    "approved": "已通过",
    "hidden": "已隐藏",
    "resolved": "已处理",
    "verified": "已认证",
    "revoked": "社区权限已撤销",
    "rejected": "已拒绝",
    "matched": "已匹配",
    "published": "已发布",
    "draft": "草稿",
    "paused": "已暂停",
    "closed": "已关闭",
}


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or config_from_env())
    validate_runtime_config(app)
    configure_logging(app)
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["ID_PHOTO_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录后再继续。"
    login_manager.login_message_category = "warning"

    from .models import SiteStat, User

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user and user.is_active else None

    from .routes import register_blueprints
    register_blueprints(app)

    from .seed import register_commands
    register_commands(app)
    register_request_logging(app)

    from .services.surveys import rules_for
    from .majors import (RESOURCE_MAJOR_CHOICES, STUDENT_MAJOR_CHOICES, PENDING_CONFIRMATION,
                         major_label)

    @app.before_request
    def count_visits():
        if request.endpoint is None or request.endpoint in ("static", "healthz"):
            return
        if session.get("_site_visited"):
            return
        session["_site_visited"] = True
        try:
            stat = db.session.get(SiteStat, 1)
            if stat is None:
                stat = SiteStat(id=1, total_visits=1)
                db.session.add(stat)
            else:
                stat.total_visits += 1
            db.session.commit()
        except Exception:
            db.session.rollback()

    @app.context_processor
    def template_helpers():
        try:
            site_stat = db.session.get(SiteStat, 1)
            site_total_visits = site_stat.total_visits if site_stat else 0
        except Exception:
            db.session.rollback()
            site_total_visits = 0
        return {
            "survey_rules": rules_for,
            "status_label": lambda value: STATUS_LABELS.get(value, value),
            "student_major_choices": STUDENT_MAJOR_CHOICES,
            "resource_major_choices": RESOURCE_MAJOR_CHOICES,
            "pending_major_code": PENDING_CONFIRMATION,
            "major_label": major_label,
            "site_total_visits": site_total_visits,
        }

    @app.get("/healthz")
    def healthz():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok", database="reachable")
        except Exception:
            db.session.rollback()
            return jsonify(status="error", database="unreachable"), 503

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        if app.config["APP_ENV"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app


def validate_runtime_config(app):
    if app.config.get("APP_ENV") != "production":
        return
    if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("生产环境必须设置至少 32 个字符的 SECRET_KEY。")
    database_url = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError("生产环境必须通过 DATABASE_URL 配置 PostgreSQL。")
    base_url = app.config.get("APP_BASE_URL", "")
    if not base_url.startswith("https://"):
        raise RuntimeError("生产环境 APP_BASE_URL 必须使用 https://。")
