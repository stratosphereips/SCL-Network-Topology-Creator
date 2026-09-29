# Very basic static attacker for SCL federation experiments.
# Minimal Ubuntu + nmap; runs deterministic nmap -sS -A (with brute-forcing
# scripts) over its network subnet every 5 minutes. This is a topology/repo
# concern (NOT part of the legacy thesis-project build source).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nmap iproute2 iputils-ping curl openssh-client netcat-openbsd \
        # hydra drives the SSH brute-forcing pass; nmap's ssh-brute NSE
        # script is unusable here (libssh2 1.10 in Ubuntu 22.04 cannot
        # complete a handshake with modern OpenSSH either way, NSE returns
        # "Unable to complete libssh2 handshake"), so nmap does discovery
        # and hydra does the actual brute attempts.
        hydra \
    && mkdir -p /var/log/static_attacker \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /usr/local/bin/static-attacker-entrypoint.sh
COPY users.txt /root/users.txt
RUN chmod +x /usr/local/bin/static-attacker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/static-attacker-entrypoint.sh"]
