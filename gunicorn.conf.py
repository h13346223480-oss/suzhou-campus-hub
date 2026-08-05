import os

default_bind = f"0.0.0.0:{os.getenv('PORT')}" if os.getenv("PORT") else "127.0.0.1:8000"
bind = os.getenv("GUNICORN_BIND", default_bind)
workers = int(os.getenv("WEB_CONCURRENCY", "3"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
# 访问日志由 Flask 以脱敏格式输出，不记录完整 IP、查询参数或 Cookie。
accesslog = None
errorlog = "-"
capture_output = True
