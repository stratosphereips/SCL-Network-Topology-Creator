# Changes

This file summarises where the repo came from and what was added on top of it.

## Before us — the upstream base (SCL Network Topology Creator)

This repository started as **`stratosphereips/SCL-Network-Topology-Creator`**, a
standalone SCL (*StratoCyberLab*) plugin that provides a local control plane for
designing and running generated network topologies.

What the upstream plugin already provided:

- A **single-page web UI** (vanilla JS embedded in `app.py`) to author topologies.
- **Routed networks**: each topology defines one or more networks with
  deterministic `10.77.<n>.0/24` subnets, bridge networks, a router hierarchy
  (root router → child routers via transit links), and per-network internet toggle.
- **Hosts**: Ubuntu containers with a role dropdown (web-server, db, file-server,
  domain-admin, normal-user, jump-box, log-server), local users, SSH enable/disable,
  optional AI-generated seed data, and a clickable **firewall graph**.
- **Hackerlab placement**: attach the existing `scl-hackerlab` container to one
  network with a deterministic `.2` address.
- **Runtime model**: `generate_compose()` writes a complete `docker-compose.yml`
  and the control plane runs `docker-compose up/down` via a mounted
  `/var/run/docker.sock` (the plugin ships `docker-cli` + `docker-cli-compose`).
- **HTTP API**: `list / create / get / start / stop / jobs / generate-data`.
- A **plugin lifecycle** compatible with the SCL dashboard (SIGINT shutdown etc.).

## What we put on top — `federated_module_testing_framework` branch

The branch adapts the plugin to build **SLIPS federation test networks** for the
Jan-thesis-work experiment runner. Everything below is new relative to upstream.

### 1. Federation host types (new roles)
Added five SLIPS-specific host types that map to `federation_network-*` images:

| Type | Image | Purpose |
|---|---|---|
| `slips-peer` | `federation_network-slips` | SLIPS IDS (Zeek / Redis / P2P federation) |
| `aracne-attacker` | `federation_network-attacker` | LLM-driven Aracne attacker |
| `pivot` | `federation_network-pivot` | SSH pivot node |
| `slip-ftp` | `federation_network-ftp` | FTP service host |
| `slip-snmp` | `federation_network-snmp` | SNMP + web service host |

The `host_image()` mapper resolves a type to its image; `host_entrypoint_cmd()`
lets each type start either natively (its built-in ENTRYPOINT/CMD) or behind a
cronjob wrapper.

### 2. SLIPS peer wiring in generated compose
When a host is a `slips-peer`, `generate_compose()` adds:
- capabilities `NET_ADMIN`, `NET_RAW`, `SYS_ADMIN`;
- thread/export-controller environment (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
  `KMP_BLOCKTIME`, `OPENBLAS_NUM_THREADS`, `PYTHONSTARTMETHOD=spawn`);
- an optional `RUN_WEB=1` flag and `SLIPS_PROFILE` from the machine profile.

### 3. Cronjobs and background traffic
Per-host **cron job** support: a textarea accepts literal crontab lines that are
injected into the container at startup. This lets a peer generate background
traffic (wikipedia, images, internal calls) as defined by the experiment.

### 4. Network copy
A **"Copy"** action on a network deep-clones the network together with all its
hosts, names, and firewall rule entries.

### 5. Image naming — `federation_network-*`
The plugin's images were renamed from a thesis-specific prefix to
**`federation_network-*`**, and the internal registry
`THESIS_HOST_TYPES` → `FEDERATION_HOST_TYPES`. A `build-images.sh` script builds
and tags the required images from the experiment project.

### 6. Localhost-only binding (security)
`docker-compose.yml` binds the UI/API to **`127.0.0.1:9002` only**. It is never
exposed on the LAN/internet; remote access is via SSH tunnel (documented in
`README.md`).

### 7. HTTP API + remote access documentation
`README.md` gained an **HTTP API reference** (with a `curl` example for the full
create → start → poll → stop flow) and a **Remote access via SSH tunnel**
section (`ssh -N -L 9002:127.0.0.1:9002 user@server`).

### 8. Unit tests
`tests/` adds a basic pytest suite + embedded-JS checks to catch regressions
(image mapping, entrypoint selection, topology validation, compose generation,
and UI wiring), verified against the live API.

### 9. Machine profile system (recent)
A per-host **profile** block was added for granular, reusable node setup:
- `slips_variant` — none / weak / middle / strong;
- `attacker_pivot` — yes/no, validated to **at most one** across the topology;
- `services` — ftp, snmp, … (extensible);
- `connections` (external) and `internal` — traffic generators backed by a
  registry;
- an **"Add +1"** node-duplicate action on the host card.

The profile is stored in `topology.json` and baked into the generated compose by
`generate_compose()` (resources, env, expanded cron lines; internal connections
resolve `{target}` to a host providing the required service role). Registries
(`SLIPS_PROFILES`, `SERVICES`, `CONNECTION_TYPES`) mean adding a new variant,
service, or connection type is a single config entry.
