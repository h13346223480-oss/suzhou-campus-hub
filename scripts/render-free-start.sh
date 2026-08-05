#!/bin/sh
set -eu

flask --app wsgi.py db upgrade
flask --app wsgi.py bootstrap-admin
if [ -n "${ADMIN_RESET_PASSWORD:-}" ]; then
  flask --app wsgi.py reset-admin-password
fi
flask --app wsgi.py bootstrap-invite
exec gunicorn -c gunicorn.conf.py wsgi:app
