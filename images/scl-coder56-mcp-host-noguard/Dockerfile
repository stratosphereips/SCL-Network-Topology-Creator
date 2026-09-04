# NoGuard experiment overlay — ZERO safety/guardrail prompt content for the
# coder56 agents; everything else inherited verbatim from the proven Kali MCP
# image. The guardrail still ships and loads (GUARDRAIL_ENABLED=1 on the host)
# so it can adjudicate in SHADOW mode: verdicts persisted, never enforced.
#
# Build (context = the opencode image dir, so guardrail/ is the live working-tree
# source — never a vendored copy; see ensure_coder56_mcp_noguard_image in images.py):
#   docker build -f images/scl-coder56-mcp-host-noguard/Dockerfile \
#            -t scl-coder56-mcp-host-noguard:0.1 \
#            images/scl-plugin-network-topology-ubuntu-opencode
#
# agents-noguard/ is maintained at
#   agents-archive/noguard/  (canonical, with the strip manifest README)
# — keep the two identical.
FROM scl-coder56-mcp-host:0.1

# Zero-safety coder56 agent prompts (lead/phase/verifier/reporter). NOTE: the
# stripped AGENTS.md also lives in agents-noguard/ (NOT the context root, which
# holds the unstripped original). model: frontmatter lines are preserved so the
# runtime FRONTMODEL repin sed (scripts.py) still works.
COPY agents-noguard/coder56_lead.md agents-noguard/coder56_phase.md agents-noguard/coder56_verifier.md agents-noguard/coder56_reporter.md /root/.config/opencode/agents/
COPY agents-noguard/AGENTS.md /root/.config/opencode/AGENTS.md

# Shadow-mode-capable guardrail plugin + current judge config (judge keeps its
# FULL RoE-aware scope-keeper prompt — the external guardrail's knowledge is
# untouched by this experiment).
COPY guardrail/guardrail.ts /opt/guardrail/guardrail.ts
COPY guardrail/opencode-guardrail.json /opt/guardrail/opencode-guardrail.json
