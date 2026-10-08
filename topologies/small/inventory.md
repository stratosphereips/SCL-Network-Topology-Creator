# Topology inventory — Small experiment

_id: `small`. Generated from topology.json by make_inventory.py; the Topology Creator is the source of truth._

**Networks:** Federation (`10.77.1.0/24`, internet=yes)

## Hosts

| Host | Role | Services | Outbound connections |
|---|---|---|---|
| slips-weak | SLIPS sensor (weak) | — | Wikipedia (external) ()<br>Google (external) (*/2 * * * *) |
| slips-strong | SLIPS sensor (strong) | — | Google (external) (*/3 * * * *)<br>Images (external) () |
| static-attacker | Static attacker | — | — |

## Connection types used

- **Google (external)** (external) — google.com
- **Images (external)** (external) — wikimedia/wikipedia images, with pauses
- **Wikipedia (external)** (external) — en.wikipedia.org — a few random articles, with pauses

## Notes

- Personal-PC browsers (external web traffic): slips-weak, slips-strong.
- Hosts with only internal/service connections or none read as infrastructure (e.g. the DB host).
- The static attacker runs deterministic nmap/hydra against the subnet; the aracne pivot is the LLM agent’s SSH entry point.
