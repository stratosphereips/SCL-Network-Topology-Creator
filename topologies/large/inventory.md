# Topology inventory — Large experiment

_id: `large`. Generated from topology.json by make_inventory.py; the Topology Creator is the source of truth._

**Networks:** Federation (`10.77.1.0/24`, internet=yes)

## Hosts

| Host | Role | Services | Outbound connections |
|---|---|---|---|
| slips-weak | SLIPS sensor (weak) | — | SQLite query (internal) → db-1 (*/2 * * * *)<br>Wikipedia (external) (*/10 * * * *) |
| slips-middle | SLIPS sensor (middle) | — | Internal web (internal) → snmp-1 (*/2 * * * *)<br>Google (external) (*/7 * * * *) |
| slips-strong | SLIPS sensor (strong) | — | FTP check (internal) → ftp-1 (* * * * *)<br>Wikipedia (external) (*/5 * * * *) |
| ftp-1 | Host | FTP server | Google (external) (*/6 * * * *)<br>Wikipedia (external) (*/8 * * * *) |
| web-1 | Host | Web server | — |
| snmp-1 | Host | SNMP, Web server | — |
| attacker | Static attacker | — | — |
| db-1 | Host | SQLite DB | Google (external) (*/9 * * * *)<br>Reddit, 30s reload (external) (*/5 * * * *) |
| aracne | Attacker pivot (aracne SSH entry) | — | — |

## Connection types used

- **FTP check (internal)** (internal) — an internal FTP host
- **Google (external)** (external) — google.com
- **Reddit, 30s reload (external)** (external) — reddit.com — open feed, read ~30s, reload
- **SQLite query (internal)** (internal) — an internal SQLite host
- **Internal web (internal)** (internal) — an internal web host (:8000)
- **Wikipedia (external)** (external) — en.wikipedia.org — a few random articles, with pauses

## Notes

- Personal-PC browsers (external web traffic): slips-weak, slips-middle, slips-strong, ftp-1, db-1.
- Hosts with only internal/service connections or none read as infrastructure (e.g. the DB host).
- The static attacker runs deterministic nmap/hydra against the subnet; the aracne pivot is the LLM agent’s SSH entry point.
