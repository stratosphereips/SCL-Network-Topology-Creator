# Network Topology Builder Plugin

This repository is the standalone home for the SCL Network Topology Creator plugin.

> This branch (`federated_module_testing_framework`) extends the plugin to build SLIPS federation test networks. A node's image + config are composed from its **profile** (slips_variant → `federation_network-slips`; services → `federation_network-service`; else the base image). The UI/API bind to `127.0.0.1:9002` only. Build the images with `./build-images.sh`.

It provides a local control plane for designing and running generated StratoCyberLab network topologies. Each topology can define routed networks, router hierarchies, Ubuntu hosts, host roles, local users, optional generated data, internet access per network, router firewall rules, and SSH access on selected hosts.
It also lets you place the `hackerlab` container onto one selected network so you can start the lab from that segment.
Routers can be chained in a parent-child tree, and each network can be attached to several routers while choosing one of them as the default gateway.
Firewall rules are edited in a clickable graph instead of a long checkbox list.

### Live SLIPS runtime logs

When a topology with SLIPS sensors is **started**, each peer's runtime logs
(`/var/log/slips`, `/var/log/slips_output`) are **bind-mounted to the host in
real time** — nothing else from the container is mounted. The host path is
configurable per device (no hardcoded server path):

```
<EXPERIMENTS_ROOT>/<experiment>/<peer>/slips
<EXPERIMENTS_ROOT>/<experiment>/<peer>/slips_output
```

- `EXPERIMENTS_ROOT` — host base dir (default `/var/lib/scl-experiments`). Set it
  on the control plane env when deploying.
- `<experiment>` — the `log_name` passed by the Runner plugin (`<id>/start` body)
  or, when started without one, the topology name.
- `<peer>` — the SLIPS peer hostname (`slips-1`, `slips-2`, …).

Start the control plane with a custom base, e.g.:

```bash
EXPERIMENTS_ROOT=/data/scl-experiments docker compose up -d --build
```

The Runner plugin reads these live logs for result collection (and also mounts
`EXPERIMENTS_ROOT`, so no end-of-run `docker cp` is needed).

## Files

- `metadata.json` describes the plugin for SCL plugin discovery.
- `docker-compose.yml` starts the plugin control plane.
- `Dockerfile` builds the control-plane container.
- `app.py` serves the UI and implements topology storage/start/stop.

## Runtime Model

Generated topologies use one or more router containers. Root routers connect to `playground-net`, child routers connect to their parent through transit networks, and assigned networks hang off the router you choose. Network segments are configured as Docker bridge networks with deterministic `10.77.<n>.0/24` subnets. Hosts are Ubuntu containers with role labels and startup scripts.

The first version intentionally starts with Ubuntu-only hosts. Service roles prepare directories, users, and role-specific files; lightweight package-backed services are attempted when a segment has internet access.
If SSH is enabled for a host, the generated container creates the specified SSH user and starts `sshd`.
If you select a hackerlab network, the plugin adds the `scl-hackerlab` container to that network with a deterministic `.2` address.

## Installation

Clone this repository into the `plugins` directory of an existing StratoCyberLab checkout:

```bash
cd /path/to/stratocyberlab
git clone https://github.com/<github-owner>/SCL-Network-Topology-Creator.git plugins/network-topology
docker compose up -d --build control-plane
```

Open the plugin UI from the SCL `Plugins` section, select `Network Topology Builder`, and press `Start`.

Replace `<github-owner>` with the GitHub account or organization where this repository is published.

If you add or remove plugins under `./plugins`, restart the SCL dashboard so it rescans plugin metadata. For ordinary changes inside this repository, restart only the plugin container and refresh the plugin page.

Legacy saved topologies named `SSH Lab` are removed automatically the next time the plugin UI loads, because they belonged to the old standalone lab example.

## Run the UI and connect

The plugin container bundles the Docker CLI (with `docker compose`) and mounts the Docker socket, so it both **serves the UI/API** and **deploys the generated topologies** — no separate deploy step. The UI is a pure topology authoring tool: you can start it and create networks right away with **nothing pre-built**.

### 1. Start the UI

```bash
docker compose up -d --build
docker compose ps                      # control-plane "Up"
```

### 2. Connect to the UI

- **On the same machine** (localhost): open `http://127.0.0.1:9002`
- **From a remote computer**, tunnel over SSH and open the URL on *your* machine:
  ```bash
  ssh -N -L 9002:127.0.0.1:9002 user@server
  # then open http://127.0.0.1:9002 on your laptop
  ```
- The port is bound to `127.0.0.1` only — see *Remote access via SSH tunnel* below for details.

### 3. Build the runtime images (only needed to *deploy* sensors/services)

The `federation_network-slips` / `federation_network-service` images are required only when you **Start** a topology that has slips/service nodes. Build them:

- **From the UI:** press **Build images** (mount the SLIPS/runner project into the container first):
  ```bash
  FEDERATION_BUILD_SOURCES=/path/to/thesis_project docker compose up -d --build
  # then click "Build images" in the UI (or POST /api/images/build)
  ```
- **Or manually:** `./build-images.sh /path/to/thesis_project`

The topologies (networks, nodes, profiles, firewall) need no images — you can design + save them before/without any build.

In the UI: **New** starts with a single **Federation** network containing 3 SLIPS peers (weak/middle/strong) plus the FTP / Web / SNMP service devices. Set each node's profile (slips variant, services, connections, internal, attacker pivot), set **Repeats** to scale a node into N identical devices, **Save**, then deploy via the API (Start/Stop are API-only — runner-driven). The same work is available headlessly through the **HTTP API** section next.

Node behavior notes:

- **Services** `snmp` and `web` are **mutually exclusive** on a node (both would fight over port 8000).
- **Connections** are authored per node as a list of `{ type, target, interval }`: pick a connection type from the dropdown, optionally a target device (hostname — stable, unlike IPs), and how often (cron). Each added connection appears as an editable row.
- Set **Repeats** on a node (instead of duplicating) and the plugin replicates it `N` times internally with fresh ids/names/IPs.

### Served webpages (identical to the OG runner)

The two distinct web pages are baked into the runtime images from the runner project (they are **not** re-generated by the plugin):

- **Service web** (`ubuntu-2`, port 8000): `build-images.sh` builds the service image, whose `service/Dockerfile` runs `COPY snmp/www /www`; the service entrypoint serves `/www` with `python3 -m http.server 8000`. Source: `snmp/www/index.html` (Acme Network — Device Management).
- **Slips web** (`slips-1` with `RUN_WEB`, port 8000): the slips image `COPY slips/slips_site /var/www/slips_site`; the slips entrypoint starts Apache on :8000 when `RUN_WEB=1`. Source: `slips/slips_site/index.html` (Acme Devices — Internal Portal).

The `test_served_webpages_identical_to_og` test in `tests/test_deploy_long.py` diffs both against the runner sources byte-for-byte.

### Multiplying nodes (Repeats)

Author a node once and set **Repeats** to clone it in the plugin (no UI duplication). `generate_compose`/`expand_repeats` create one Docker service per replica with unique id/name/IP, include every replica in `SLIPS_PEERS`, bake each replica's cron, and never mark replicas as the attacker pivot. Covered by the `test_repeats_*` tests.

### Connection registry (`connections.json`)

Connection types live in `connections.json` next to `app.py` — add a new external/internal connection there without touching code:

```json
{
  "my_conn": {
    "label": "My connection (external)",
    "scope": "external",
    "interval": "*/7 * * * *",
    "command": "myscript.sh"
  },
  "my_internal": {
    "label": "My internal check",
    "scope": "internal",
    "interval": "* * * * *",
    "command": "check-thing.sh {target}",
    "target_role": "ftp"
  }
}
```

- `scope` is `external` (fixed command) or `internal` (resolves `{target}` to the chosen device; falls back to the first host running `target_role`).
- `interval` is the default cron schedule; a per-node connection can override it.
- The bundled registry ships `wikipedia` (opens a random Wikipedia page) / `images` external connections and `ftp_check` / `web_internal` internal ones.

## HTTP API

The web UI is a thin client over a REST API. You can drive the whole workflow headlessly (no browser) with `curl` or any HTTP client, which is what experiment runners and automation use.

Base URL (local machine): `http://127.0.0.1:9002`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/topologies` | List saved topologies (id, name, #networks, #hosts, running flag) |
| `POST` | `/api/topologies` | Create / update a topology from a JSON body. Validates and regenerates `docker-compose.yml`. |
| `GET` | `/api/topologies/<id>` | Fetch one topology's full JSON + running flag |
| `POST` | `/api/topologies/<id>/start` | Deploy the topology (`docker-compose up -d`). Returns a `job_id`. |
| `POST` | `/api/topologies/<id>/stop` | Tear it down (`docker-compose down`). Returns a `job_id`. |
| `GET` | `/api/images` | Which `federation_network-*` images exist locally |
| `POST` | `/api/images/build` | Build + tag the `federation_network-*` images (background `job_id`) |
| `GET` | `/api/jobs/<job_id>` | Poll status of a background start/stop/build/data job |
| `POST` | `/api/generate-data` | AI-generate host seed data (requires the SCL LLM endpoint) |

`start`, `stop` and `generate-data` run in the background and return a `job_id`; poll `/api/jobs/<job_id>` until `status == "completed"` (built into the UI — automation should do the same).

Minimal headless example — create a topology, deploy it, poll, tear down:

```bash
# Create / save (server validates and writes docker-compose.yml)
curl -s -X POST http://127.0.0.1:9002/api/topologies \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "my-lab",
        "networks": [
          {"id":"net-a","name":"Office","cidr":"10.77.1.0/24",
           "hosts":[{"id":"h1","name":"web","type":"web-server"}]}
        ],
        "routers":[{"id":"r1","name":"core"}]
      }'
# → {"topology": {"id": "my-lab-ab12cd", ...}}

# List, then deploy
ID=my-lab-ab12cd
curl -s http://127.0.0.1:9002/api/topologies                       # find the id
JOB=$(curl -s -X POST http://127.0.0.1:9002/api/topologies/$ID/start -d '{}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
curl -s http://127.0.0.1:9002/api/jobs/$JOB                        # poll until completed

# Tear down
curl -s -X POST http://127.0.0.1:9002/api/topologies/$ID/stop -d '{}'
```

## Remote access via SSH tunnel (when running on a server)

The plugin binds its UI and API to **`127.0.0.1:9002` only** (see `docker-compose.yml` → `ports: "127.0.0.1:9002:9002"`). It is **never** exposed to the LAN or the internet — only to processes on the server itself.

To reach it from a remote computer, open an SSH tunnel to the server, then open your **local** browser:

```bash
# On your laptop
ssh -L 9002:127.0.0.1:9002 user@server

# Then open this on the LAPTOP (all traffic flows over the encrypted SSH session):
open http://127.0.0.1:9002        # or just browse to http://127.0.0.1:9002
```

If you do not need an interactive shell, add `-N`:

```bash
ssh -N -L 9002:127.0.0.1:9002 user@server
```

Details / notes:

- The plugin is reachable only by SSH accounts that can log into the server; anything else on the network cannot connect.
- `curl` examples in the API section work unchanged over a tunnel once the local port is forwarded (use `127.0.0.1:9002`).
- To forward **multiple ports** (e.g. the UI plus another service), pass several `-L` flags: `-L 9002:127.0.0.1:9002 -L 9003:127.0.0.1:9003`.
- If you already keep an SSH session open (ControlMaster), add `-f -N` to background the tunnel without blocking your shell.

## LLM Data Generation

The UI can request AI-generated sample data for selected hosts. The plugin calls the SCL dashboard LLM endpoint through `http://dashboard/api/llm/chat`, so it uses the model configured in the main SCL assistant.
