# Long docker-bake verification for the federation experiment.
#
# These tests verify the *generated* docker-compose.yml (fast, no containers)
# and, when SCLLONG=1 is set and Docker is available, actually deploy the
# topology and check that dockers are baked correctly: all crons are present,
# SLIPS is running, and the served webpages are identical to the OG runner.
#
# Run the long part with:
#   SCLLONG=1 python -m pytest tests/test_deploy_long.py -s
import json
import os
import shutil
import subprocess
import tempfile
import time

import pytest

import app

OG_EXPERIMENT = {
    "name": "OG Federation Experiment",
    "networks": [{
        "id": "fed", "name": "Federation",
        "cidr": "172.20.1.0/24", "internet": True,
        "hosts": [
            {"id": "s1", "name": "slips-1", "type": "normal-user",
             "ssh_enabled": True, "username": "admin", "password": "G9!tR4#vX7@cM2$kP8n", "run_web": True,
             "profile": {"slips_variant": "strong", "services": [], "connections": [
                 {"id": "ftp_check", "target": "ubuntu-1", "interval": "* * * * *"},
                 {"id": "wikipedia", "interval": "*/5 * * * *"}]}},
            {"id": "s2", "name": "slips-2", "type": "normal-user",
             "ssh_enabled": True, "username": "admin", "password": "G9!tR4#vX7@cM2$kP8n",
             "profile": {"slips_variant": "middle", "services": [], "connections": [
                 {"id": "web_internal", "target": "ubuntu-2", "interval": "*/2 * * * *"},
                 {"id": "google", "interval": "*/7 * * * *"}]}},
            {"id": "s3", "name": "slips-3", "type": "normal-user",
             "ssh_enabled": True, "username": "admin", "password": "G9!tR4#vX7@cM2$kP8n",
             "profile": {"slips_variant": "weak", "services": [], "connections": [
                 {"id": "web_internal", "target": "slips-1", "interval": "*/4 * * * *"},
                 {"id": "wikipedia", "interval": "*/10 * * * *"}]}},
            {"id": "f1", "name": "ubuntu-1", "type": "normal-user",
             "ssh_enabled": True, "username": "admin", "password": "admin",
             "profile": {"slips_variant": "none", "services": ["ftp"], "connections": [
                 {"id": "google", "interval": "*/6 * * * *"},
                 {"id": "wikipedia", "interval": "*/8 * * * *"}]}},
            {"id": "u2", "name": "ubuntu-2", "type": "normal-user",
             "ssh_enabled": True, "username": "admin", "password": "admin",
             "profile": {"slips_variant": "none", "services": ["snmp"], "connections": []}},
        ],
    }],
    "routers": [{"id": "r1", "name": "core"}],
}


@pytest.fixture(scope="module")
def og_topology():
    valid = app.validate_topology(json.loads(json.dumps(OG_EXPERIMENT)))
    valid["id"] = "og-fed-1"
    return valid


@pytest.fixture(scope="module")
def og_compose(og_topology):
    return app.generate_compose(og_topology)


# ---------------------------------------------------------------------------
# Static bake verification (fast)
# ---------------------------------------------------------------------------
def test_compose_has_all_expected_services(og_compose):
    expected = {
        "fed-s1": app.SLIPS_RUNTIME_IMAGE,
        "fed-s2": app.SLIPS_RUNTIME_IMAGE,
        "fed-s3": app.SLIPS_RUNTIME_IMAGE,
        "fed-f1": app.SERVICE_RUNTIME_IMAGE,
        "fed-u2": app.SERVICE_RUNTIME_IMAGE,
    }
    for name, image in expected.items():
        assert name in og_compose["services"], f"missing service {name}"
        assert og_compose["services"][name]["image"] == image


def test_compose_sensor_caps_and_resources(og_topology, og_compose):
    s1 = og_compose["services"]["fed-s1"]
    assert s1["cap_add"] == ["NET_ADMIN", "NET_RAW", "SYS_ADMIN"]
    assert s1["cpus"] == 4 and s1["mem_limit"] == "8g"  # strong
    s2 = og_compose["services"]["fed-s2"]
    assert s2["cpus"] == 2 and s2["mem_limit"] == "4g"  # middle
    s3 = og_compose["services"]["fed-s3"]
    assert s3["cpus"] == 1 and s3["mem_limit"] == "2g"  # weak


# ---------------------------------------------------------------------------
# Cron verification against the OG runner (fast)
# ---------------------------------------------------------------------------
OG_CRONS = {
    # node -> set of cron lines expected (from the OG slips/ftp entrypoints)
    "fed-s1": {
        "* * * * * check-ftp.sh ubuntu-1",
        "*/5 * * * * internet-traffic.sh wikipedia",
    },
    "fed-s2": {
        "*/2 * * * * curl-website.sh ubuntu-2",
        "*/7 * * * * internet-traffic.sh google",
    },
    "fed-s3": {
        "*/4 * * * * curl-website.sh slips-1",
        "*/10 * * * * internet-traffic.sh wikipedia",
    },
    "fed-f1": {
        "*/6 * * * * internet-traffic.sh google",
        "*/8 * * * * internet-traffic.sh wikipedia",
    },
}


def _node_config_for(og_topology, service_name):
    peers = app.peer_names_of(og_topology)
    for net in og_topology["networks"]:
        for host in net["hosts"]:
            if f'{net["id"]}-{host["id"]}' == service_name:
                return app.node_config(og_topology, host, host["profile"], peers)
    raise KeyError(service_name)


def test_all_og_crons_baked(og_topology):
    peers = app.peer_names_of(og_topology)
    for service_name, expected_crons in OG_CRONS.items():
        cfg = app.node_config(og_topology, og_topology["networks"][0]["hosts"][0], {}, peers) if False else None
    for service_name, expected_crons in OG_CRONS.items():
        cfg = _node_config_for(og_topology, service_name)
        for cron in expected_crons:
            assert cron in cfg, f"{service_name} missing cron: {cron!r}\n---\n{cfg}"


def test_no_wikipedia_paper_registry_entry():
    assert "wikipedia_paper" not in app.CONNECTION_TYPES
    assert "google" in app.CONNECTION_TYPES  # OG uses google traffic


def test_served_webpages_identical_to_og():
    # service /www is OG snmp/www/index.html; slips /var/www/slips_site is OG slips_site
    def image_web(image, path):
        return subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", f"cat {path}"],
            capture_output=True, text=True,
        ).stdout

    svc = image_web(app.SERVICE_RUNTIME_IMAGE, "/www/index.html")
    slips = image_web(app.SLIPS_RUNTIME_IMAGE, "/var/www/slips_site/index.html")
    og_svc = open("/home/svobojan/thesis_project/snmp/www/index.html").read()
    og_slips = open("/home/svobojan/thesis_project/slips/slips_site/index.html").read()
    assert svc == og_svc, "service /www web page differs from OG"
    assert slips == og_slips, "slips_site web page differs from OG"


# ---------------------------------------------------------------------------
# Real docker bake (long) — gated by SCLLONG=1
#
# Flow per node: create a scratch bridge network, run ONE baked container
# detached on it, verify via the CLI (crontab / process / web), then remove
# the container and the network. Nothing is left behind.
# ---------------------------------------------------------------------------
def _docker_available():
    return shutil.which("docker") is not None


def _compose_of(og_compose, service_name):
    return og_compose["services"][service_name]


@pytest.mark.long
def test_bake_one_container_verify_and_cleanup(og_topology, og_compose):
    if not os.environ.get("SCLLONG") == "1":
        pytest.skip("set SCLLONG=1 (and have docker + images) to run the bake test")
    if not _docker_available():
        pytest.skip("docker not available")

    import threading

    network = f"scl-og-bake-{os.getpid()}"
    results = {}

    def bake_and_check(service_name, checks):
        try:
            svc = _compose_of(og_compose, service_name)
            image = svc["image"]
            entrypoint = svc.get("entrypoint", [])
            container = f"{service_name}-bake"
            # remove any leftover container
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)
            cmd = ["docker", "run", "-d", "--name", container, "--network", network]
            if entrypoint:
                # compose entrypoint is ["sh","-lc", cmd]; run the baked command directly
                cmd.append("--entrypoint")
                cmd.append("sh")
                cmd.append(image)
                cmd.append("-lc")
                cmd.append(entrypoint[-1])
            else:
                cmd.append(image)
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            assert run.returncode == 0, f"{service_name} run failed:\n{run.stderr}"

            # wait until the container is up and its checks pass
            last = ""
            ok = False
            for _ in range(20):
                time.sleep(5)
                try:
                    last = checks(container)
                    if last.get("ok"):
                        ok = True
                        break
                except Exception as exc:  # pragma: no cover
                    last = {"error": str(exc)}
            assert ok, f"{service_name}: checks never passed:\n{last}"
            results[service_name] = last
        finally:
            subprocess.run(["docker", "rm", "-f", f"{service_name}-bake"], capture_output=True, text=True)

    # create the scratch network
    subprocess.run(["docker", "network", "create", network], capture_output=True, text=True)
    try:
        # NOTE: external DNS resolution inside a raw bridge network uses the
        # container name, not the hostname. For a single-node smoke test we
        # check cron lines and processes; peer/DNS + cross-node routing are
        # exercised by the plugin's compose deploy, not here.
        def sensor_checks(container):
            out = {"ok": False}
            # crontab must contain the sensor's OG crons
            cron = _exec(container, "crontab -l 2>/dev/null || true")
            svc_name = container.replace("-bake", "")
            for expected in OG_CRONS.get(svc_name, set()):
                if expected not in cron.stdout:
                    out["missing_cron"] = expected
                    return out
            # SLIPS process must be running
            proc = _exec(container, "pgrep -f 'slips.py -c' || true")
            if "slips.py" not in proc.stdout:
                out["slips"] = "not running"
                return out
            out["ok"] = True
            return out

        def service_checks(container):
            out = {"ok": False}
            cron = _exec(container, "crontab -l 2>/dev/null || true")
            svc_name = container.replace("-bake", "")
            for expected in OG_CRONS.get(svc_name, set()):
                if expected not in cron.stdout:
                    out["missing_cron"] = expected
                    return out
            out["ok"] = True
            return out

        threads = []
        # verify one small slips sensor + one service node
        for service_name, checks in (("fed-s1", sensor_checks), ("fed-f1", service_checks)):
            t = threading.Thread(target=bake_and_check, args=(service_name, checks))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=900)

        for service_name in ("fed-s1", "fed-f1"):
            assert service_name in results, f"{service_name} did not complete"
            assert results[service_name].get("ok"), f"{service_name} failed: {results[service_name]}"
    finally:
        # remove any leftover baked containers + the network
        for name in ("fed-s1-bake", "fed-f1-bake"):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True, text=True)

    # confirm nothing is left over
    leftover = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=scl-og-bake", "--format", "{{.Names}}"],
        capture_output=True, text=True).stdout.strip()
    assert leftover == "", f"leftover baked containers: {leftover}"
    nets = subprocess.run(
        ["docker", "network", "ls", "--filter", f"name={network}", "--format", "{{.Name}}"],
        capture_output=True, text=True).stdout.strip()
    assert nets == "", f"leftover network: {nets}"


def _exec(container, cmd):
    return subprocess.run(
        ["docker", "exec", container, "sh", "-lc", cmd],
        capture_output=True, text=True,
    )

