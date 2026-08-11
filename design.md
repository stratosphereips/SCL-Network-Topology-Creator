# Design — SLIPS Federation Testing Framework

This document describes the final architecture for building and running
scalable SLIPS federation experiments. It is the target design shared across
three pieces: the **network topology plugin** (this repo, branch
`federated_module_testing_framework`), the **experiment runner**
(`stratosphereips/Jan-thesis-work`), and the **SLIPS image** (in the runner
project). A companion, human-facing changelog is in `changes.md`.

## 1. Goal

Recreate and *scale* the SLIPS federation experiment:

- Stand up **N SLIPS peers** with **different capacities / detection profiles**
  (weak / middle / strong), each a **distinct network-ready Docker container**
  (unique IP, MAC, hostname, peer id).
- Deploy **services** (ftp, snmp, …) and **background traffic** (external:
  wikipedia…; internal: cross-device calls) per node, all **composable**.
- Drive the run with a **runner**: baseline → attack (Aracne via SSH pivot) →
  monitor → collect → visualize.
- Run the **same experiment on different-sized networks** (5 / 10 / 20 / 50
  nodes) and **sweep** experiment parameters (label method, model, sharing
  policy) — with **no hardcoded addresses** and **reproducible reruns**.
- Collect every run into a self-describing result directory and auto-generate
  visuals.

Principles:
- **Topology is separate from experiment.** The topology decides *what exists*;
  the experiment decides *how it's driven*.
- **No hardcoded addresses.** Hosts are identified by hostname; Docker's
  embedded DNS resolves them; IPs are allocated deterministically by the plugin.
- **Configuration over rebuilds.** A node's behaviour comes from a *profile*
  (env + config) applied at container start, not from per-combination images.

## 2. Components

### 2.1 Network topology plugin (`federated_module_testing_framework`)

A standalone SCL-style plugin (control plane, docker.sock, `docker compose up/down`).

- **Authoring UI**: networks, nodes, per-node fine-grain profile, node
  duplication ("Add +1"), network copy, firewall graph.
- **HTTP API** (headless, automation-friendly): list / create / get / start /
  stop / jobs.
- **Compose bake**: turns a topology + profiles into a complete
  `docker-compose.yml`, then deploys it.
- Binds `127.0.0.1:9002` only (SSH-tunnel access).

### 2.2 Experiment runner (`Jan-thesis-work`)

The driver. Consumes the topology manifest + an experiment definition, calls the
plugin API to deploy, then runs the timed phases, collects logs, and visualizes.

### 2.3 SLIPS image (`federation_network-slips`)

Built from the runner project's `slips/`. Contains SLIPS (fl_module_jan branch),
Zeek, Redis, the p2p4slips Go binary, and **baked federated peer configs**.
Behaviour at boot is driven by env injected by the plugin.

## 3. The profile model

There are **no fused host types** (no `slips-peer` / `slip-ftp` / `pivot` …).
A node's behaviour is composed entirely from its profile, so image + config are
put together from the settings (not a hardcoded per-role image):

```jsonc
{
  "slips_variant": "weak",          // none | weak | middle | strong
  "attacker_pivot": false,          // at most one true in the whole topology
  "services": ["ftp", "snmp"],      // ftp | snmp | web | ... (registry)
  "connections": ["wikipedia", "images"],  // external traffic generators
  "internal": ["ftp_check"]          // internal (cross-device) traffic generators
}
```

**Image selection** (from settings, not a type enum):
- `slips_variant != none` → `federation_network-slips`
- else `services` non-empty → `federation_network-service` (unified runtime)
- else → plain base image

**Config assembly** at bake/deploy time:
- sensor → `SLIPS_PROFILE` (variant → cpus/mem + module set),
  `SLIPS_PEERS` (all sensor hostnames), `RUN_WEB`, thread env.
- service node → `SERVICES` env (which daemons the unified runtime starts).
- connections/internal → expanded cron lines; internal `{target}` resolved to a
  host providing the service role.

Registries make the system extensible with a single entry each:
- `SLIPS_PROFILES` — variant → resources (cpus/mem) + module set.
- `SERVICES` — id → label (+ future image/ports/target role).
- `CONNECTION_TYPES` — external/internal; internal entries carry a `target_role`.

### Copy / reuse

- A node is configured once, then **"Add +1"** clones it into a network with a
  regenerated name / hostname / IP slot / peer id, reusing the same image
  (Docker shares layers). A duplicated node is **never** the attacker pivot.
- Connection profiles are reusable across many nodes (they're registry ids).

## 4. Node identity (no hardcoded addresses, reproducible reruns)

- **Hostname** = the peer's name from the manifest (stable across reruns).
- **IP** = deterministically allotted by the plugin per network slot
  (`host_ip(cidr, host_index)`), fixed for a given topology.
- **MAC / container name** = Docker-generated; unique per container.
- **Peer id** = SLIPS federation peer id derived from hostname.
- **P2P discovery** = the plugin injects `SLIPS_PEERS="<all-peer-hostnames>"`
  on every slips-peer; the image entrypoint writes `p2p_config.yaml` with
  `/dns4/<hostname>/tcp/6668/p2p/...` multiaddresses. Docker DNS resolves them,
  so peers find each other without any IP in the config. Deterministic reruns:
  hostnames + IPs come from the manifest.

## 5. Experiment definition ↔ topology manifest

- **topology.json** (plugin): networks, nodes, profiles, firewall. *What exists.*
- **experiment.yaml** (runner): timeline (baseline/attack/monitor minutes),
  aracne params, sweep keys (label method / model / sharing policy), profile
  catalog. *How it's driven.*

The runner combines them per run: `for experiment × topology → deploy → run →
collect → visualize`.

## 6. Result directory

```
output/<experiment>/<run_id>/
├── manifest/            # topology.json + experiment.yaml + profiles (reproduce the run)
├── ip_assignment.json   # node -> IP (what was actually deployed)
├── containers.txt       # container/network layout
├── slips-<N>/           # per-peer SLIPS output (whole dir) + plots/
└── aracne_*.log, summary/   # aracne logs + combined visuals
```

`run_id` = timestamp + short manifest hash (identical topologies map to the same
run key across sweeps). Layout stays compatible with the existing visualizer.

## 7. Run lifecycle (runner)

1. Read `experiment.yaml` + `topology.json`.
2. POST topology to plugin; plugin bakes compose + deploys (`SLIPS_PROFILE`,
   `SLIPS_PEERS`, resources, cron lines all applied).
3. Runner builds the attacker network + dual-homed pivot (the attacker/pivot are
   a singleton experiment concern, not part of the scalable topology).
4. Phases: baseline (N min) → Aracne attack with restarts → post-attack monitor.
5. Collect (docker cp) per-peer output + aracne logs + manifest + IP assignment.
6. Visualize + aggregate across sweeps.

## 8. Status

Current state of the pieces (see `changes.md` for history):

- **Plugin**: host types, `federation_network-*` images, profiles, Add+1,
  network copy, registries, localhost binding, API docs, unit/smoke tests,
  DNS P2P injection (`SLIPS_PEERS`), deployed end-to-end in a smoke test.
- **SLIPS image**: baked variant configs (strong/middle/weak), dynamic
  `/dns4` P2P config; peers boot from a plugin-created topology.
- **Runner**: not yet consuming the topology manifest / emitting `manifest/`
  + `ip_assignment.json` into a per-run result dir.

### Open / next

- [ ] Runner reads topology + experiment.yaml and drives deploy/run/collect/visualize.
- [ ] Result dir: write `manifest/` + `ip_assignment.json`; name runs by experiment/run_id.
- [ ] Attacker network + dual-homed pivot built by the runner.
- [ ] Scale validation 5 → 10 → 20 → 50.
- [ ] Decide plugin delivery (branch vs PR to `SCL-Network-Topology-Creator` main).
- [ ] Expand `docs`/`design.md` details for schema + registries if needed.
