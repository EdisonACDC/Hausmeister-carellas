FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION=1.5.37
ARG BUILD_ARCH

LABEL \
  io.hass.name="Hausmeister Carellas" \
  io.hass.description="Gestione segnalazioni manutenzione con zone e QR" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache python3 py3-pip
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN PIP_EXTRA_INDEX_URL= pip3 install \
    --index-url https://pypi.org/simple \
    --timeout 120 \
    --retries 12 \
    --resume-retries 12 \
    --no-cache-dir \
    --break-system-packages \
    -r /app/requirements.txt
COPY app /app/app
RUN python3 -m py_compile /app/app/fix_maintenance_patch.py \
    && python3 /app/app/fix_maintenance_patch.py \
    && python3 -m py_compile /app/app/patch_zone_groups.py /app/app/patch_whatsapp.py /app/app/patch_whatsapp_direct.py /app/app/patch_maintenance.py /app/app/patch_backup.py /app/app/patch_smart_inventory.py /app/app/patch_ios_photos.py /app/app/patch_qr_bulk_fast_ticket.py /app/app/patch_manager_navigation_language.py /app/app/patch_admin_i18n_runtime.py /app/app/patch_admin_language_server.py /app/app/patch_ha_frontend_language.py \
    && python3 /app/app/patch_zone_groups.py \
    && python3 /app/app/patch_whatsapp.py \
    && python3 /app/app/patch_whatsapp_direct.py \
    && python3 /app/app/patch_maintenance.py \
    && python3 /app/app/patch_backup.py \
    && python3 /app/app/patch_smart_inventory.py \
    && python3 /app/app/patch_ios_photos.py \
    && python3 /app/app/patch_qr_bulk_fast_ticket.py \
    && python3 /app/app/patch_manager_navigation_language.py \
    && python3 /app/app/patch_admin_i18n_runtime.py \
    && python3 /app/app/patch_admin_language_server.py \
    && python3 /app/app/patch_ha_frontend_language.py \
    && python3 -m py_compile /app/app/main.py /app/app/ha_sensor_publisher.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
