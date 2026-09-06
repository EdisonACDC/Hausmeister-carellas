FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION=1.5.2
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
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt
COPY app /app/app
RUN python3 -m py_compile /app/app/patch_zone_groups.py /app/app/patch_manager_public_groups.py /app/app/patch_manager_zones_fix.py /app/app/patch_backup.py \
    && python3 /app/app/patch_zone_groups.py \
    && python3 /app/app/patch_manager_public_groups.py \
    && python3 /app/app/patch_manager_zones_fix.py \
    && python3 /app/app/patch_backup.py \
    && python3 -m py_compile /app/app/main.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
