# Service tickbox bake matrix: assert every service/combination is written
# through into the node.conf baked into the per-node docker definitions,
# and — with SCLLONG=1 — actually start the dockers and check that the
# webpage IS served on ticked hosts and NOT served on unticked hosts.
#
# Fast part (always): generate compose for the matrix topology and assert
# node.conf contents per host.
# Long part (SCLLONG=1 + docker + images): start one container per matrix
# node on a scratch bridge, verify via curl/pgrep/crontab, then clean up.
#
# Run the long part with:
#   SCLLONG=1 python -m pytest tests/test_service_bake.py -s
import json
import os
import re
import shutil
import subprocess
import time

import pytest

import app

# Marker from the consolidated frontpage (slips_site copied over snmp/www).
FRONTPAGE_MARKER = "Acme"

MATRIX = {
    "name": "service bake matrix",
    "networks": [{
        "id": "n", "name": "bake", "cidr": "10.77.9.0/24", "internet": True,
        "hosts": [
            # slips sensor serving the apache webpage (only via tickbox)
            {"id": "sa", "name": "sensor-apache", "type": "normal-user",
             "profile": {"slips_variant": "weak", "attacker_pivot": False,
                         "services": ["apache"], "connections": []}},
            # plain sensor — must NOT serve any webpage
            {"id": "sp", "name": "sensor-plain", "type": "normal-user",
             "profile": {"slips_variant": "weak", "attacker_pivot": False,
                         "services": [], "connections": []}},
            # snmp alone — must NOT serve a webpage (web never bundled)
            {"id": "sn", "name": "svc-snmp", "type": "normal-user",
             "profile": {"slips_variant": "none", "attacker_pivot": False,
                         "services": ["snmp"], "connections": []}},
            # snmp + web combo — all-and-any combining
            {"id": "sb", "name": "svc-snmp-web", "type": "normal-user",
             "profile": {"slips_variant": "none", "attacker_pivot": False,
                         "services": ["snmp", "web"], "connections": []}},
            # apache ticked on a plain service host -> served as 'web'
            {"id": "sap", "name": "svc-apache", "type": "normal-user",
             "profile": {"slips_variant": "none", "attacker_pivot": False,
                         "services": ["apache"], "connections": []}},
            # sqlite db
            {"id": "sq", "name": "svc-sqlite", "type": "normal-user",
             "profile": {"slips_variant": "none", "attacker_pivot": False,
                         "services": ["sqlite"], "connections": []}},
            # bare host: no services at all
            {"id": "sbare", "name": "svc-bare", "type": "normal-user",
             "profile": {"slips_variant": "none", "attacker_pivot": False,
                         "services": [], "connections": []}},
        ],
    }],
    "routers": [{"id": "r1", "name": "core"}],
}


def _valid():
    valid = app.validate_topology(json.loads(json.dumps(MATRIX)))
    valid["id"] = "bake"
    return valid


@pytest.fixture(scope="module")
def matrix():
    return _valid()


@pytest.fixture(scope="module")
def matrix_compose(matrix):
    return app.generate_compose(matrix)


def _baked_node_conf(svc):
    """Extract the node.conf content from the compose entrypoint."""
    ep = " ".join(svc.get("entrypoint") or [])
    match = re.search(r"cat > /opt/network-setup/node.conf <<'EOF'\n(.*?)\nEOF", ep, re.S)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Fast bake checks (no containers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("svc,expect", [
    ("n-sa", {"RUN_WEB=1": True, "SERVICE": None}),
    ("n-sp", {"RUN_WEB": False}),
    ("n-sn", {"SERVICES='snmp'": True}),
    ("n-sb", {"SERVICES='snmp,web'": True}),
    ("n-sap", {"SERVICES='web'": True}),   # apache translated on service hosts
    ("n-sq", {"SERVICES='sqlite'": True}),
    ("n-sbare", {"SERVICES=": False}),
])
def test_node_conf_service_wiring(matrix_compose, svc, expect):
    cfg = _baked_node_conf(matrix_compose["services"][svc])
    for token, present in expect.items():
        if token == "RUN_WEB" and present is False:
            assert "RUN_WEB" not in cfg, f"{svc} unexpectedly has RUN_WEB:\n{cfg}"
        elif token == "SERVICE" and present is None:
            assert "SERVICES=" not in cfg or "'apache'" not in cfg, f"{svc} leaks apache:\n{cfg}"
        elif present:
            assert token in cfg, f"{svc} missing {token!r}:\n{cfg}"
        else:
            assert token not in cfg, f"{svc} unexpectedly has {token!r}:\n{cfg}"


def test_webpage_hosts_exactly_match_ticked_boxes(matrix):
    # Keepalive targets are the authoritative "who serves a :8000 page" list.
    targets = app.keepalive_targets(matrix)
    assert sorted(targets) == [
        "http://sensor-apache:8000",
        "http://svc-apache:8000",
        "http://svc-snmp-web:8000",
    ]


def test_every_matrix_service_image_choice(matrix_compose):
    assert matrix_compose["services"]["n-sa"]["image"] == app.SLIPS_RUNTIME_IMAGE
    assert matrix_compose["services"]["n-sp"]["image"] == app.SLIPS_RUNTIME_IMAGE
    for svc in ("n-sn", "n-sb", "n-sap", "n-sq"):
        assert matrix_compose["services"][svc]["image"] == app.SERVICE_RUNTIME_IMAGE
    assert matrix_compose["services"]["n-sbare"]["image"] == app.BASE_IMAGE


def test_no_apache_token_escapes_any_node_conf(matrix_compose):
    for name, svc in matrix_compose["services"].items():
        cfg = _baked_node_conf(svc)
        if not cfg:
            continue
        assert "SERVICES='apache'" not in cfg, f"{name} has raw apache service"


# ---------------------------------------------------------------------------
# Real docker bake (long) — gated by SCLLONG=1
# Flow per node: start ONE baked container on a scratch bridge network, run
# the node's checks via docker exec, then remove it. Nothing is left behind:
# checking that the website IS served on ticked hosts and NOT on unticked.
# ---------------------------------------------------------------------------
def _docker_available():
    return shutil.which("docker") is not None


def _exec(container, cmd):
    return subprocess.run(
        ["docker", "exec", container, "sh", "-lc", cmd],
        capture_output=True, text=True)


def _wait_for(check_fn, attempts=20, pause=5):
    last = {"ok": False}
    for _ in range(attempts):
        time.sleep(pause)
        try:
            last = check_fn()
            if last.get("ok"):
                return last
        except Exception as exc:  # pragma: no cover
            last = {"error": str(exc)}
    return last


@pytest.mark.long
def test_service_dockers_serve_webpage_exactly_where_ticked(matrix_compose):
    if not os.environ.get("SCLLONG") == "1":
        pytest.skip("set SCLLONG=1 (and have docker + images) to run the bake test")
    if not _docker_available():
        pytest.skip("docker not available")

    network = f"scl-bake-{os.getpid()}"
    subprocess.run(["docker", "network", "create", network],
                   capture_output=True, text=True)

    def start_node(service_name, container):
        svc = matrix_compose["services"][service_name]
        image = svc["image"]
        starter = svc.get("entrypoint") or svc.get("command")
        subprocess.run(["docker", "rm", "-f", container],
                       capture_output=True, text=True)
        cmd = ["docker", "run", "-d", "--name", container,
               "--network", network, "--hostname", svc["hostname"]]
        if starter:
            cmd += ["--entrypoint", "sh", image, "-lc", starter[-1]]
        else:
            cmd.append(image)
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        assert run.returncode == 0, f"{service_name} run failed:\n{run.stderr}"

    def web_served(container):
        out = _exec(container, "curl -s -m 5 http://127.0.0.1:8000/")
        if out.returncode != 0 or FRONTPAGE_MARKER not in out.stdout:
            return {"ok": False, "curl": (out.stdout + out.stderr)[:300]}
        return {"ok": True}

    def web_refused(container):
        out = _exec(container, "curl -s -m 5 http://127.0.0.1:8000/ >/dev/null 2>&1")
        if out.returncode == 0:
            body = _exec(container, "curl -s -m 5 http://127.0.0.1:8000/ | head -c 300").stdout
            return {"ok": False, "unexpected_page": body}
        return {"ok": True}

    def port_open(container, port):
        out = _exec(container, f"curl -s -m 5 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/")
        return {"ok": out.stdout.strip() not in ("", "000"), "http": out.stdout.strip()}

    def apt_cron(container):
        out = _exec(container, "crontab -l 2>/dev/null | grep -c 'apt-get update'")
        return {"ok": out.stdout.strip() >= "1", "crontab": out.stdout}

    def slips_running(container):
        # pgrep prints PIDs only; the [.] trick avoids matching our own shell.
        out = _exec(container, "pgrep -f 'slips[.]py -c' || true")
        return {"ok": bool(out.stdout.strip())}

    checks = {
        # sensor with apache tickbox serves the consolidated frontpage,
        # has the baked apt cron, and actually runs SLIPS
        "n-sa": lambda c: {"ok": web_served(c)["ok"] and apt_cron(c)["ok"]
                           and slips_running(c)["ok"]},
        # plain sensor: webpage refused
        "n-sp": web_refused,
        # snmp alone: webpage refused (web is never bundled with snmp)
        "n-sn": lambda c: {"ok": web_refused(c)["ok"] and apt_cron(c)["ok"]},
        # snmp + web combo: page up
        "n-sb": web_served,
        # apache ticked on a service host -> page up via 'web'
        "n-sap": web_served,
        # sqlite serves the dummy db on 8010
        "n-sq": lambda c: port_open(c, 8010),
        # bare host: no :8000 page at all
        "n-sbare": web_refused,
    }

    results = {}
    try:
        for service_name, check in checks.items():
            container = f"{service_name}-bake"
            try:
                start_node(service_name, container)
                results[service_name] = _wait_for(
                    lambda: check(container), attempts=24, pause=5)
            finally:
                subprocess.run(["docker", "rm", "-f", container],
                               capture_output=True, text=True)
    finally:
        subprocess.run(["docker", "network", "rm", network],
                       capture_output=True, text=True)

    failures = {name: res for name, res in results.items() if not res.get("ok")}
    assert not failures, f"service bake failures: {failures}"

    leftover = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=-bake", "--format", "{{.Names}}"],
        capture_output=True, text=True).stdout.strip()
    assert leftover == "", f"leftover baked containers: {leftover}"
