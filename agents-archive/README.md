# coder56 system-prompt variants (archive)

Three saved configurations of the coder56 agent system prompts. Each directory is
a complete, self-contained snapshot: `agents/{coder56_lead,coder56_phase,coder56_verifier,coder56_reporter}.md`
+ `AGENTS.md` (global memory protocol) + `opencode.json` (image-baked default config,
provenance only — the runtime opencode.json is rendered per-host by `scripts.py`).

| Variant | Source | What it is |
|---|---|---|
| `normal/`  | git `8474263` ("baseline: coder56 agents as deployed 2026-09-03 (pre-qwen-contract)") | The standard coder56 prompts. Verified byte-identical to the agents baked in live `scl-coder56-mcp-host:0.1` (sha256:3f73027036ca...) as of 2026-09-04. |
| `qwen3.8/` | git `ed05985` (qwen3.8 tip) | normal + task-tool TOOL CONTRACT blocks (lead +11 lines, phase +10 lines: strict 3-key JSON contract + FINAL REMINDER) added for the qwen3.8-27b model. |
| `noguard/` | derived from `8474263` on 2026-09-04 | Zero safety/guardrail content in any agent-visible string. For the shadow-guardrail experiment (external judge adjudicates, never gates). |

Provenance recorded 2026-09-04:
- Base opencode image `scl-plugin-network-topology-ubuntu-opencode:0.1` = sha256:63a7409549cf...
- Base Kali MCP image `scl-coder56-mcp-host:0.1` = sha256:3f73027036ca...
- `noguard/agents/*` + `noguard/AGENTS.md` are the build input copied to
  `images/scl-plugin-network-topology-ubuntu-opencode/agents-noguard/` (used by the
  `scl-coder56-mcp-host-noguard:0.1` overlay image). The two directories must stay identical.

The noguard strip manifest is in `noguard/README.md`.

## Overlay build record (2026-09-04)
- `scl-coder56-mcp-host-noguard:0.1` = sha256:6b567c4ab0d1..., built FROM
  `scl-coder56-mcp-host:0.1` (sha256:3f73027036ca...)
- baked guardrail.ts md5 47d9c69d0bc73b499ce4e4b7efa08656 (== working tree, shadow mode)
- baked opencode-guardrail.json md5 bf2454e59cb08e9da59370762d410c14 (== working tree)
- image content verified: agents + AGENTS.md contain zero safety/guardrail strings;
  judge `guardrail_coder56` prompt (6832 chars, ClawKeeper scope-keeper) intact
