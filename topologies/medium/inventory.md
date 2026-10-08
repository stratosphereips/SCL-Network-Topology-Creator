# Topology inventory — Medium experiment

_id: `medium`. Generated from topology.json by make_inventory.py; the Topology Creator is the source of truth._

**Networks:** Federation (`172.20.1.0/24`, internet=yes)

## Hosts

| Host | Role | Services | Outbound connections |
|---|---|---|---|
| slips-1 | SLIPS sensor (strong) | Apache webpage | FTP check (internal) → ubuntu-1 (* * * * *)<br>Wikipedia (external) (*/5 * * * *) |
| slips-2 | SLIPS sensor (middle) | — | Internal web (internal) → ubuntu-2 (*/2 * * * *)<br>Google (external) (*/7 * * * *) |
| slips-3 | SLIPS sensor (weak) | — | Internal web (internal) → slips-1 (*/4 * * * *)<br>Wikipedia (external) (*/10 * * * *) |
| ubuntu-1 | Host | FTP server | Google (external) (*/6 * * * *)<br>Wikipedia (external) (*/8 * * * *) |
| ubuntu-2 | Host | SNMP, Web server | — |
| connect | Attacker pivot (aracne SSH entry) | — | — |
| attack-1 | Static attacker | — | — |

## Connection types used

- **FTP check (internal)** (internal) — an internal FTP host
- **Google (external)** (external) — google.com
- **Internal web (internal)** (internal) — an internal web host (:8000)
- **Wikipedia (external)** (external) — en.wikipedia.org — a few random articles, with pauses

## Notes

- Personal-PC browsers (external web traffic): slips-1, slips-2, slips-3, ubuntu-1.
- Hosts with only internal/service connections or none read as infrastructure (e.g. the DB host).
- The static attacker runs deterministic nmap/hydra against the subnet; the aracne pivot is the LLM agent’s SSH entry point.
