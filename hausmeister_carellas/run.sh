#!/usr/bin/with-contenv bashio
set -e
mkdir -p /config/uploads
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
