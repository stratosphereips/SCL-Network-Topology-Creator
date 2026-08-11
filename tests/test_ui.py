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
    for host_type in app.FEDERATION_HOST_TYPES:
        assert host_type in types


def test_federation_types_present_in_ui_html():
    # Labels/options are injected via the __HOST_TYPES__ JSON at serve time,
    # so assert against the HOST_TYPES registry (the injection source).
    labels = [info["label"] for info in app.HOST_TYPES.values()]
    for expected in ["SLIPS IDS Peer", "Aracne Attacker", "SSH Pivot", "FTP Server", "SNMP / Web"]:
        assert expected in labels, f"missing label: {expected}"


def test_required_dom_ids_present():
    for dom_id in REQUIRED_IDS:
        assert f'id="{dom_id}"' in app.INDEX_HTML, f"missing element id: {dom_id}"


def test_new_host_fields_wired():
    assert 'data-field="host.cronjobs"' in app.INDEX_HTML
    assert 'data-field="host.run_web"' in app.INDEX_HTML
    assert "duplicate-network" in app.INDEX_HTML  # Copy-network action


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
