# syntax=docker/dockerfile:1
# SCL Leosac host (`leosac-server`) — Leosac physical access control, full stack:
# C++ core (leosac/access-control, cmake + ODB ORM) + websock-api module (:8888,
# WebSocket JSON API) + PostgreSQL (:5432) + Ember web UI
# (leosac/access-control-web) behind nginx (:80). Mirrors the ERPNext host image.
#
# Core + web are cloned from GitHub at BUILD time (network OK, like OH/ERPNext).
# The C++ core is compiled with its pinned submodules (zmqpp, websocketpp, spdlog,
# date, flagset, json) and installed to /usr/local; leosac auto-creates the DB
# schema on first start (kernel.cpp create_update_schema). First-boot seeding
# (first admin + demo users/doors/credentials) runs in leosac-app-start.sh via
# /usr/local/bin/leosac-create-admin (ODB helper compiled against the built tree)
# + /usr/local/bin/seed_leosac.py (WS API client). The PostgreSQL datadir is on a
# named volume (compose.py), so data persists across topology stop/start cycles.
#
# Pinned: core=develop tip, web=master tip (ARM64-safe: everything builds from
# source on the box; upstream publishes no arm64 image). Override the cloned
# repo/branch with the LEOSAC_*/LEOSAC_WEB_* env vars + ensure_leosac_image()
# build-args (see images.py).

FROM scl-plugin-network-topology-ubuntu:0.1
ARG LEOSAC_URL=https://github.com/leosac/access-control
ARG LEOSAC_REF=954e17225ff448b1ad78df3ab22cacb036a85cbb
ARG LEOSAC_WEB_URL=https://github.com/leosac/access-control-web
ARG LEOSAC_WEB_REF=d9a41ad75dfd357112f5483b28184155b6608f52

LABEL maintainer="StratoCyberLab Team"
LABEL description="SCL Leosac host — access-control core + websock-api + PostgreSQL + Ember web UI (red-team engagement target)"
LABEL org.opencontainers.image.source="${LEOSAC_URL} ${LEOSAC_WEB_URL}"
LABEL org.opencontainers.image.revision="core=${LEOSAC_REF} web=${LEOSAC_WEB_REF}"

ENV DEBIAN_FRONTEND=noninteractive
ENV PUPPETEER_SKIP_DOWNLOAD=1

# Build + runtime deps in one layer (erpnext keeps -dev pkgs too). Dependency
# list mirrors upstream CI (.github/workflows/build.yml) with noble package
# names; `odb` (the ODB ORM compiler, 2.4.0-16 arm64 in noble/universe) generates
# the database layer at cmake time, so it must be present at BUILD time only.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake build-essential pkg-config curl ca-certificates gosu jq \
        netcat-openbsd python3 python3-websockets \
        libssl-dev libzmq3-dev libcurl4-openssl-dev libtclap-dev libscrypt-dev \
        libboost-all-dev libsqlite3-dev libpq-dev \
        odb libodb-dev libodb-pgsql-dev libodb-sqlite-dev libodb-boost-dev \
        libgpiod-dev \
        postgresql-16 postgresql-client-16 nginx \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*' \
    && npm install -g yarn \
    && python3 -c "import websockets; print('websockets', websockets.__version__)"

# ── Leosac core: clone pinned ref + submodules, build, install. ────────────────
RUN git init /opt/leosac-src \
    && git -C /opt/leosac-src remote add origin "${LEOSAC_URL}" \
    && git -C /opt/leosac-src fetch --depth 1 origin "${LEOSAC_REF}" \
    && git -C /opt/leosac-src checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/leosac-src rev-parse HEAD)" = "${LEOSAC_REF}" \
    && git -C /opt/leosac-src submodule update --init --recursive \
    && cmake -S /opt/leosac-src -B /opt/leosac-build \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
    && cmake --build /opt/leosac-build -j"$(nproc)" \
    && cmake --install /opt/leosac-build \
    && ldconfig \
    && test -x /usr/local/bin/leosac \
    && test -f /usr/local/lib/leosac/libwebsock-api.so \
    && test -f /usr/local/lib/leosac/libsmtp.so

# ── First-admin bootstrap helper (compiled against the built tree). ────────────
# The WS API has no unauthenticated user-creation path (APISession gate), so the
# first admin is persisted straight through the same ODB layer leosac uses.
COPY leosac-create-admin.cpp /tmp/leosac-create-admin.cpp
RUN g++ -std=c++14 -O2 /tmp/leosac-create-admin.cpp -o /usr/local/bin/leosac-create-admin \
        -I/opt/leosac-src \
        -I/opt/leosac-build/odb_gen \
        -I/opt/leosac-src/deps/flagset \
        -I/opt/leosac-src/deps/date/include \
        -I/opt/leosac-src/deps/json/include \
        -I/opt/leosac-src/deps/spdlog/include \
        -L/usr/local/lib -lleosac_lib -lleosac_db -lodb-pgsql -lodb -lscrypt \
    && rm /tmp/leosac-create-admin.cpp \
    && test -x /usr/local/bin/leosac-create-admin \
    && ! ldd /usr/local/bin/leosac-create-admin | grep -q 'not found'

# ── PostgreSQL: initialized cluster, listening on all interfaces. ──────────────
RUN pg_createcluster 16 main \
    && sed -i "s/^#\?listen_addresses.*/listen_addresses = '*'/" \
        /etc/postgresql/16/main/postgresql.conf \
    && printf 'host all all 0.0.0.0/0 scram-sha-256\n' >> \
        /etc/postgresql/16/main/pg_hba.conf

# ── Ember web UI: clone pinned ref, build with a placeholder backend address. ──
# LEOSAC_ADDR is baked into the bundle at build time (config/environment.js);
# leosac-app-start.sh seds the placeholder into the container's real hostname at
# boot, keeping the image topology-agnostic. defaultLocale is fr upstream -> en.
RUN git init /opt/leosac-web \
    && git -C /opt/leosac-web remote add origin "${LEOSAC_WEB_URL}" \
    && git -C /opt/leosac-web fetch --depth 1 origin "${LEOSAC_WEB_REF}" \
    && git -C /opt/leosac-web checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/leosac-web rev-parse HEAD)" = "${LEOSAC_WEB_REF}" \
    && sed -i "s/defaultLocale: 'fr'/defaultLocale: 'en'/" \
        /opt/leosac-web/config/environment.js \
    && cd /opt/leosac-web \
    && LEOSAC_ADDR=ws://leosac.internal:8888 yarn install --network-timeout 100000 \
    && LEOSAC_ADDR=ws://leosac.internal:8888 NODE_OPTIONS=--max-old-space-size=3072 \
        yarn build --prod \
    && rm -rf /opt/leosac-web-dist \
    && cp -a /opt/leosac-web/dist /opt/leosac-web-dist \
    && test -f /opt/leosac-web-dist/index.html

# ── nginx front door for the built web UI. ─────────────────────────────────────
COPY nginx-leosac.conf /etc/nginx/sites-available/leosac
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /etc/nginx/sites-available/leosac /etc/nginx/sites-enabled/leosac

# ── Kernel config + first-boot supervisor + seeder. ────────────────────────────
COPY kernel-leosac.xml /etc/leosac.d/kernel.xml
COPY leosac-app-start.sh /usr/local/bin/leosac-app-start.sh
COPY leosac-healthcheck.sh /usr/local/bin/leosac-healthcheck.sh
COPY seed_leosac.py /usr/local/bin/seed_leosac.py
RUN chmod +x /usr/local/bin/leosac-app-start.sh /usr/local/bin/leosac-healthcheck.sh \
    && chmod 0644 /usr/local/bin/seed_leosac.py

EXPOSE 80 8888 5432
HEALTHCHECK --interval=15s --timeout=10s --start-period=420s --retries=28 \
    CMD /usr/local/bin/leosac-healthcheck.sh

WORKDIR /srv
