ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.20
FROM $BUILD_FROM

ENV LANG=C.UTF-8

RUN apk add --no-cache openjdk21-jre wget bash curl

ARG GRAPHHOPPER_VERSION=8.0
RUN mkdir -p /opt/graphhopper && cd /opt/graphhopper && \
    wget -O graphhopper.jar \
    "https://github.com/graphhopper/graphhopper/releases/download/${GRAPHHOPPER_VERSION}/graphhopper-web-${GRAPHHOPPER_VERSION}.jar"

# GraphHopper config (custom-models, profiles)
COPY graphhopper/config.yml /opt/graphhopper/config.yml

# s6 service definition
COPY rootfs/ /

EXPOSE 8989

LABEL \
    io.hass.name="Yapaia Routing" \
    io.hass.description="GraphHopper routing engine for Yapaia Go" \
    io.hass.version="0.5.0" \
    io.hass.type="addon" \
    io.hass.arch="amd64|aarch64" \
    maintainer="Apfelsafft <apfelsafft@gmail.com>"
