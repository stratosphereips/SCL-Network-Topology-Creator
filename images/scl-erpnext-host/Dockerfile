# syntax=docker/dockerfile:1
# SCL ERPNext host (`erpnext-server`) — Frappe framework + ERPNext app on the
# Frappe/bench stack: MariaDB (:3306) + Redis (:6379) + gunicorn web (:8000) +
# nginx front door (:80). Mirrors the OpenHospital host image.
#
# The Frappe + ERPNext apps are cloned from GitHub at BUILD time (network OK,
# like OH's git clone) and `bench init` / `get-app` prepare the bench. The site
# (new-site + install-app erpnext + seeded demo users/data) is created at FIRST
# BOOT by /usr/local/bin/erpnext-app-start.sh (idempotent, marker-gated). The
# MariaDB datadir AND the bench sites/ dir are on named volumes, so the site +
# its data persist across topology stop/start cycles.
#
# Pinned to the Frappe + ERPNext `version-15` branches (ARM64-safe, stable).
# Override the cloned repo/branch with the FRAPPE_*/ERPNEXT_* env vars + the
# ensure_erpnext_image() build-args (see images.py).

FROM scl-plugin-network-topology-ubuntu:0.1
ARG FRAPPE_URL=https://github.com/frappe/frappe
ARG FRAPPE_REF=version-15
ARG ERPNEXT_URL=https://github.com/frappe/erpnext
ARG ERPNEXT_REF=version-15

LABEL maintainer="StratoCyberLab Team"
LABEL description="SCL ERPNext host — Frappe + ERPNext (bench) + MariaDB + Redis + nginx (red-team engagement target)"
LABEL org.opencontainers.image.source="https://github.com/frappe/frappe https://github.com/frappe/erpnext"
LABEL org.opencontainers.image.revision="frappe=${FRAPPE_REF} erpnext=${ERPNEXT_REF}"

ENV DEBIAN_FRONTEND=noninteractive

# ── System deps: MariaDB + Redis + nginx + Python build headers + Node 20 + git. ─
# Wide -dev set so mysqlclient / pillow / pycurl / lxml / weasyprint-class wheels
# build from source on arm64. git safe.directory avoids fatal "dubious ownership"
# errors when bench re-clones into a dir owned by another uid.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git mariadb-server mariadb-client redis-server nginx \
        python3-pip python3.12-venv python3-dev \
        build-essential pkg-config libmysqlclient-dev libssl-dev libffi-dev \
        libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libtiff-dev libopenjp2-7-dev \
        libfreetype6-dev libwebp-dev liblcms2-dev libldap2-dev libsasl2-dev \
        libcurl4-openssl-dev libpoppler-cpp-dev libcairo2-dev libpango1.0-dev \
        libgdk-pixbuf2.0-dev fontconfig \
        curl ca-certificates gosu sudo netcat-openbsd jq cron \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*' \
    && npm install -g yarn \
    && pip install --break-system-packages --no-cache-dir frappe-bench

# ── A non-root user to run bench (bench warns/refuses some ops as root). ─────────
RUN useradd -m -s /bin/bash frappe

# ── Build the bench at image-build time: init (clones frappe) + get-app erpnext. ─
# No DB/Redis needed here — new-site/install-app run at first boot.
USER frappe
WORKDIR /home/frappe
RUN bench init frappe-bench \
        --frappe-path "${FRAPPE_URL}" \
        --frappe-branch "${FRAPPE_REF}" \
        --python python3 \
    && cd frappe-bench \
    && bench get-app erpnext "${ERPNEXT_URL}" --branch "${ERPNEXT_REF}" \
    && bench build

USER root

# ── Point bench's redis config at a single on-host redis instance (ports, not the
#    unix-socket default bench init writes) and snapshot the freshly-initialised
#    sites/ dir so the persistent sites volume can be seeded from it on first boot.
RUN jq '. + {"redis_cache":"redis://127.0.0.1:6379/0", \
             "redis_queue":"redis://127.0.0.1:6379/1", \
             "redis_socketio":"redis://127.0.0.1:6379/2", \
             "developer_mode":0}' \
        /home/frappe/frappe-bench/sites/common_site_config.json \
        > /tmp/csc.json && mv /tmp/csc.json /home/frappe/frappe-bench/sites/common_site_config.json \
    && rm -rf /home/frappe/frappe-bench/sites.seed \
    && cp -a /home/frappe/frappe-bench/sites /home/frappe/frappe-bench/sites.seed \
    && chown -R frappe:frappe /home/frappe/frappe-bench

# ── MariaDB: bind all interfaces + skip-name-resolve + utf8mb4 + sane InnoDB. ────
RUN printf '[mysqld]\n\
bind-address = 0.0.0.0\n\
skip-name-resolve = 1\n\
character-set-server = utf8mb4\n\
collation-server = utf8mb4_unicode_ci\n\
innodb_file_format = Barracuda\n\
innodb_file_per_table = 1\n\
innodb_large_prefix = 1\n\
innodb_buffer_pool_size = 256M\n\
sql_mode = STRICT_TRANS_TABLES\n' > /etc/mysql/mariadb.conf.d/99-erp-bind.cnf

# ── nginx front door (:80 -> gunicorn :8000). ───────────────────────────────────
COPY nginx-erp.conf /etc/nginx/sites-available/erpnext
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /etc/nginx/sites-available/erpnext /etc/nginx/sites-enabled/erpnext

# ── Supervisor + healthcheck + seed script. ─────────────────────────────────────
COPY erpnext-app-start.sh /usr/local/bin/erpnext-app-start.sh
COPY erpnext-healthcheck.sh /usr/local/bin/erpnext-healthcheck.sh
COPY seed_erpnext.py /usr/local/bin/seed_erpnext.py
COPY run_seed.py /usr/local/bin/run_seed.py
RUN chmod +x /usr/local/bin/erpnext-app-start.sh /usr/local/bin/erpnext-healthcheck.sh \
    && chown frappe:frappe /usr/local/bin/seed_erpnext.py /usr/local/bin/run_seed.py

# ── Build-time assertion: both apps + the sites skeleton are present. ───────────
RUN test -d /home/frappe/frappe-bench/apps/frappe \
    && test -d /home/frappe/frappe-bench/apps/erpnext \
    && test -f /home/frappe/frappe-bench/sites/common_site_config.json

EXPOSE 80 8000 3306 6379
HEALTHCHECK --interval=15s --timeout=10s --start-period=360s --retries=24 \
    CMD /usr/local/bin/erpnext-healthcheck.sh

WORKDIR /home/frappe/frappe-bench
