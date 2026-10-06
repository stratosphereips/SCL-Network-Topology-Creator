# Federation SLIPS peer image = the SLIPS branch's OWN docker image (built by
# the plugin from <repo>@<commit> with the branch's docker/Dockerfile) plus a
# thin federation layer: lab services (ssh/apache/cron), the peer entrypoint,
# traffic scripts, and the strong/middle/weak detector configs rendered from
# the branch's own config/slips.yaml. No source files are patched in: every
# SLIPS/module change must live in the SLIPS branch.
#
# Build context: federation/ (see app.build_federation_images).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG SLIPS_COMMIT=unknown
ARG SLIPS_BRANCH=unknown
LABEL org.stratosphere.slips.commit=${SLIPS_COMMIT} \
      org.stratosphere.slips.branch=${SLIPS_BRANCH}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -o Acquire::Retries=5 \
    && apt-get install -y --no-install-recommends \
        apache2 \
        cron \
        curl \
        iproute2 \
        iputils-ping \
        net-tools \
        openssh-server \
    && mkdir -p /var/run/sshd \
    && (id admin >/dev/null 2>&1 || useradd -m -s /bin/bash admin) \
    && printf '%s\n' 'admin:G9!tR4#vX7@cM2$kP8n' | chpasswd \
    && printf '%s\n' 'root:Z3!qL6#pT1@hN9$wR5x' | chpasswd \
    && printf '\nPasswordAuthentication yes\nPermitRootLogin yes\n' >> /etc/ssh/sshd_config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# The lab tooling (runner yaml patching, whitelist/GT injection, entrypoint)
# addresses SLIPS at /opt/StratosphereLinuxIPS; upstream installs it at
# $SLIPS_DIR (/StratosphereLinuxIPS).
RUN ln -sfn "${SLIPS_DIR}" /opt/StratosphereLinuxIPS \
    && printf '%s\n' "${SLIPS_COMMIT}" > /opt/slips_commit

# Detector variants rendered on top of the branch's own config/slips.yaml.
COPY slips/configs /opt/federation-configs
RUN python3 /opt/federation-configs/render_configs.py \
        --base "${SLIPS_DIR}/config/slips.yaml" \
        --overrides /opt/federation-configs/overrides.yaml \
        --variants /opt/federation-configs/variants.yaml \
        --modules-dir "${SLIPS_DIR}/modules" \
        --out-dir "${SLIPS_DIR}/config"

COPY slips/slips-entrypoint.sh /usr/local/bin/slips-entrypoint.sh
COPY slips/slips_site /var/www/slips_site
COPY scripts /scripts
RUN chmod +x /usr/local/bin/slips-entrypoint.sh /scripts/*.sh \
    && mkdir -p /var/log/slips /var/log/slips_output

EXPOSE 22 8000
ENTRYPOINT ["/usr/local/bin/slips-entrypoint.sh"]
