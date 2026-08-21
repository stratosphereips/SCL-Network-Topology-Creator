# Basic UI "didn't break it" tests.
#
# The UI is a single vanilla-JS app embedded as a Python raw string in
# app.py. We can't run it in a full browser here, so we guard the most common
# regressions:
#   1. the embedded <script> is valid JS (checked with `node --check`)
#   2. the required DOM element ids still exist
#   3. the __HOST_TYPES__ JSON injection is valid and includes our types
#   4. the new per-host fields (cronjobs / run_web) are still wired up
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

import app

REQUIRED_IDS = [
    "saveTopology",
    "newTopology",
    "topologyName",
    "networkCount",
    "defaultHosts",
    "networks",
    "routers",
    "savedTopologies",
    "hackerlabNetwork",
    "selectedJson",
    "status",
    "firewallGraph",
]


def _extract_scripts():
    return re.findall(r"<script>(.*?)</script>", app.INDEX_HTML, re.DOTALL)


def test_host_types_injection_is_valid_json():
    # The server replaces __HOST_TYPES__ with json.dumps(HOST_TYPES)
    rendered = app.INDEX_HTML.replace("__HOST_TYPES__", json.dumps(app.HOST_TYPES))
    m = re.search(r"const HOST_TYPES\s*=\s*(\{.*?\});", rendered, re.DOTALL)
    assert m, "could not locate HOST_TYPES assignment"
    types = json.loads(m.group(1))
    # generic roles remain; no fused federation types
    for role in app.GENERIC_ROLES:
        assert role in types
    for fused in ("slips-peer", "slip-ftp", "slip-snmp", "pivot", "aracne-attacker"):
        assert fused not in types


def test_profile_registries_present_in_ui_html():
    # slips/services/connections are injected into the JS at serve time
    assert "SLIPS_PROFILES" in app.INDEX_HTML
    assert "SERVICES" in app.INDEX_HTML
    assert "CONNECTION_TYPES" in app.INDEX_HTML
    # the profile editor is wired (slips_variant literal; services via profChecks)
    assert 'data-field="profile.slips_variant"' in app.INDEX_HTML
    assert "profile.services" in app.INDEX_HTML
    assert "profile.connections" in app.INDEX_HTML
    assert "add-connection" in app.INDEX_HTML  # connection editor (add/dropdown)
    assert "profile.addconn_type" in app.INDEX_HTML
    assert "profile.connection_interval" in app.INDEX_HTML


def test_required_dom_ids_present():
    for dom_id in REQUIRED_IDS:
        assert f'id="{dom_id}"' in app.INDEX_HTML, f"missing element id: {dom_id}"


def test_new_host_fields_wired():
    assert 'data-field="host.repeats"' in app.INDEX_HTML  # repeats field (replaces +1)
    assert 'data-field="host.ssh_enabled"' in app.INDEX_HTML
    assert 'data-field="host.run_web"' in app.INDEX_HTML
    assert "profile.connection_type" in app.INDEX_HTML   # unified connection rows
    assert "add-connection" in app.INDEX_HTML            # add connection from dropdown
    # free-form cron textarea removed (connections are the single source)
    assert 'data-field="host.cronjobs"' not in app.INDEX_HTML
    # +1 duplicate button removed (repeats replicates internally)
    assert "duplicate-host" not in app.INDEX_HTML
    # Start/Stop buttons remain in the saved list
    assert 'data-action="start-topology"' in app.INDEX_HTML
    assert 'data-action="stop-topology"' in app.INDEX_HTML
    # per-topology Open + Delete actions so save/load/remove don't need Docker
    assert 'data-action="load-topology"' in app.INDEX_HTML
    assert 'data-action="delete-topology"' in app.INDEX_HTML


def test_scripts_are_valid_javascript():
    scripts = _extract_scripts()
    assert scripts, "no <script> blocks found in INDEX_HTML"
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed; cannot run JS syntax check")
    for i, script in enumerate(scripts):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(script)
            tmp = fh.name
        try:
            result = subprocess.run(
                [node, "--check", tmp],
                capture_output=True,
                text=True,
            )
        finally:
            os.unlink(tmp)
        assert result.returncode == 0, f"script[{i}] invalid JS:\n{result.stderr}"
