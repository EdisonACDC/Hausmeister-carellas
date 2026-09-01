#!/usr/bin/with-contenv bashio
set -e
mkdir -p /data/uploads
uvicorn app.main:public_app --host 0.0.0.0 --port 8080 &
exec uvicorn app.main:admin_app --host 0.0.0.0 --port 8099
