#!/usr/bin/with-contenv bashio

export MQTT_HOST="$(bashio::config 'mqtt_host')"
export MQTT_PORT="$(bashio::config 'mqtt_port')"
export HA_BASE_URL="$(bashio::config 'ha_base_url')"
export HA_TOKEN="$(bashio::config 'ha_token')"
export GRAPHHOPPER_URL="$(bashio::config 'graphhopper_url')"
export PHOTON_URL="$(bashio::config 'photon_url')"
export BACKEND_CORS_ORIGINS="*"
export POSTGRES_HOST=""   # Add-on nutzt vorerst kein eigenes Postgres

bashio::log.info "Starte Navi ${ADDON_VERSION}..."
bashio::log.info "MQTT: ${MQTT_HOST}:${MQTT_PORT}"

cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
