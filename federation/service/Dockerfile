FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Unified service runtime: hosts any of the selectable services (ftp, snmp,
# web …) and starts only the ones listed in $SERVICES at boot.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        vsftpd \
        snmp \
        snmpd \
        snmptrapd \
        python3 \
        openssh-server \
        ca-certificates \
        curl \
        iproute2 \
        wget \
        vim \
        cron \
    && mkdir -p /var/run/sshd \
    && useradd -m -s /bin/bash admin \
    && printf '%s\n' 'admin:admin' | chpasswd \
    && mkdir -p /home/admin/ftp \
    && chown -R admin:admin /home/admin/ftp \
    && echo "Hello from FTP server" > /home/admin/ftp/welcome.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY ftp/vsftpd.conf /etc/vsftpd.conf
COPY snmp/snmpd.conf /etc/snmp/snmpd.conf
COPY snmp/www /www
# SQLite service payload: sample companies.db (55,991 rows of dummy company
# data) from codecrafters-io/sample-sqlite-databases, pinned to a commit and
# verified by sha256 so the build stays reproducible.
ARG COMPANIES_DB_URL=https://raw.githubusercontent.com/codecrafters-io/sample-sqlite-databases/6805601903957406acf80a1d575bdfa6cf304321/companies.db
ARG COMPANIES_DB_SHA256=b364b13ce6c450fef4281dca84384fcbc0c75ddd848adb6af30f171416218bc7
RUN mkdir -p /srv/db \
    && curl -fsSL --retry 5 -o /srv/db/companies.db "$COMPANIES_DB_URL" \
    && echo "$COMPANIES_DB_SHA256  /srv/db/companies.db" | sha256sum -c -
COPY scripts /scripts
# services.json is the single source of truth for the unified runtime's
# "start" per service id (and for the topology plugin's service picker).
COPY services.json /opt/services.json
COPY service/service-entrypoint.sh /usr/local/bin/service-entrypoint.sh
RUN chmod +x /usr/local/bin/service-entrypoint.sh \
    && chmod +x /scripts/*.sh \
    && printf '\nPasswordAuthentication yes\nPermitRootLogin no\n' >> /etc/ssh/sshd_config

EXPOSE 20 21 22 161/udp 162/udp 8000/tcp 8010/tcp

ENTRYPOINT ["/usr/local/bin/service-entrypoint.sh"]
