#!/bin/sh
set -e

# Runs as root so it can fix ownership of the bind-mounted data dir
# (Docker creates it as root on first run), then drops to appuser.
chown -R appuser:appuser /data

exec setpriv --reuid=appuser --regid=appuser --init-groups sh -c '
  set -e
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  exec "$@"
' -- "$@"
