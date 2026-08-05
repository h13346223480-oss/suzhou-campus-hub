import logging
import re
import sys
import time
from uuid import uuid4

from flask import g, request


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def configure_logging(app):
    """Send production-friendly application logs to stdout."""
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    app.logger.propagate = False


def register_request_logging(app):
    """Log request metadata without query strings, bodies, cookies, or IP addresses."""
    @app.before_request
    def start_request_timer():
        supplied_id = request.headers.get("X-Request-ID", "")
        g.request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid4().hex
        g.request_started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        response.headers.setdefault("X-Request-ID", g.get("request_id", uuid4().hex))
        if app.config.get("LOG_REQUESTS", True):
            duration_ms = round((time.perf_counter() - g.get("request_started_at", time.perf_counter())) * 1000, 2)
            app.logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%s",
                g.get("request_id"),
                request.method,
                request.path,
                response.status_code,
                duration_ms,
            )
        return response
