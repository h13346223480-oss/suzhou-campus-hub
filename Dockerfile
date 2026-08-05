FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /srv/app

RUN groupadd --system --gid 10001 campus \
    && useradd --system --uid 10001 --gid campus --create-home campus

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY --chown=campus:campus . .
RUN mkdir -p /srv/app/instance /srv/app/app/static/uploads \
    && chown -R campus:campus /srv/app/instance /srv/app/app/static/uploads

USER campus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/healthz', timeout=3)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
