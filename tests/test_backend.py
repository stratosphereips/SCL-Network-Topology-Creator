# Basic backend unit tests for the topology creator.
# Purpose: catch regressions in the core logic (image mapping, entrypoint
# selection, validate_topology normalization, and generate_compose output).
import json
import os

import pytest

import app


FED_TYPES = {
    "slips-peer": "federation_network-slips:latest",
    "aracne-attacker": "federation_network-attacker:latest",
    "pivot": "federation_network-pivot:latest",
    "slip-ftp": "federation_network-ftp:latest",
    "slip-snmp": "federation_network-snmp:latest",
}


def _basic_topology():
    return {
        "name": "Basic",
        "networks": [
            {
                "id": "slip-net",
                "name": "SLIPS",
                "cidr": "10.77.1.0/24",
                "hosts": [
                    {
                        "id": "s1",
                        "name": "slips-1",
                        "type": "slips-peer",
                        "run_web": True,
                        "cronjobs": ["*/2 * * * * curl -s http://10.77.2.11/ >/dev/null"],
                    },
                    {"id": "s2", "name": "slips-2", "type": "slips-peer"},
                ],
            },
            {
                "id": "victim",
                "name": "Victims",
                "cidr": "10.77.2.0/24",
                "hosts": [
                    {"id": "f1", "name": "ubuntu-1", "type": "slip-ftp"},
                    {"id": "n1", "name": "snmp-1", "type": "slip-snmp"},
                ],
            },
        ],
        "routers": [{"id": "r1", "name": "core"}],
    }


# --------------------------------------------------------------------------
# host_image
# --------------------------------------------------------------------------
def test_host_image_known_types():
    for host_type, expected in FED_TYPES.items():
        assert app.host_image(host_type) == expected


def test_host_image_unknown_type_falls_back_to_base():
    assert app.host_image("ftp") == app.BASE_IMAGE
    assert app.host_image("") == app.BASE_IMAGE


# --------------------------------------------------------------------------
# host_entrypoint_cmd
# --------------------------------------------------------------------------
def test_entrypoint_cmd_by_type():
    assert app.host_entrypoint_cmd("pivot") == "/usr/sbin/sshd -D"
    assert app.host_entrypoint_cmd("slips-peer") == "/usr/local/bin/slips-entrypoint.sh"
    assert app.host_entrypoint_cmd("aracne-attacker") == "/entrypoint.sh"
    assert app.host_entrypoint_cmd("anything-else") == "tail -f /dev/null"


# --------------------------------------------------------------------------
# FEDERATION_HOST_TYPES registry
# --------------------------------------------------------------------------
def test_federation_host_types_contains_all_custom_types():
    assert set(app.FEDERATION_HOST_TYPES) == set(FED_TYPES.keys())


def test_all_federation_types_present_in_host_types():
    for host_type in app.FEDERATION_HOST_TYPES:
        assert host_type in app.HOST_TYPES


# --------------------------------------------------------------------------
# validate_topology
# --------------------------------------------------------------------------
def test_validate_topology_basic():
    valid = app.validate_topology(_basic_topology())
    assert len(valid["networks"]) == 2
    assert valid["networks"][0]["hosts"][0]["type"] == "slips-peer"
    # ids normalized / defaulted
    assert valid["networks"][0]["default_router_id"]
    # unknown host type is coerced to normal-user
    unknown = {"id": "x", "name": "x", "type": "does-not-exist"}
    n = app.validate_topology({
        "name": "t",
        "networks": [{"id": "n", "cidr": "10.77.9.0/24", "hosts": [unknown]}],
    })
    assert n["networks"][0]["hosts"][0]["type"] == "normal-user"


def test_validate_topology_requires_name():
    with pytest.raises(ValueError):
        app.validate_topology({"networks": []})


# --------------------------------------------------------------------------
# generate_compose — the docker config baking
# --------------------------------------------------------------------------
def _generate():
    valid = app.validate_topology(_basic_topology())
    valid["id"] = "test-lab"
    return app.generate_compose(valid)


def test_generate_compose_network_images():
    comp = _generate()
    assert comp["services"]["slip-net-s1"]["image"] == "federation_network-slips:latest"
    assert comp["services"]["slip-net-s2"]["image"] == "federation_network-slips:latest"
    assert comp["services"]["victim-f1"]["image"] == "federation_network-ftp:latest"
    assert comp["services"]["victim-n1"]["image"] == "federation_network-snmp:latest"


def test_generate_compose_slips_caps_and_env():
    s1 = _generate()["services"]["slip-net-s1"]
    assert s1["cap_add"] == ["NET_ADMIN", "NET_RAW", "SYS_ADMIN"]
    env = s1.get("environment", {})
    assert env.get("PYTHONSTARTMETHOD") == "spawn"
    assert env.get("RUN_WEB") == "1"


def test_generate_compose_cron_only_when_present():
    comp = _generate()
    # host with cronjobs gets a wrapped command
    assert comp["services"]["slip-net-s1"].get("command") is not None
    assert "*/2 * * * * curl" in comp["services"]["slip-net-s1"]["command"][-1]
    # host without cronjobs keeps native startup (no command override)
    assert comp["services"]["slip-net-s2"].get("command") is None


def test_generate_compose_networks_created():
    comp = _generate()
    nets = [k for k in comp["networks"] if k != "playground-net"]
    assert len(nets) == 2
    assert "topo_slip-net" in nets
    assert "topo_victim" in nets


def test_generate_compose_all_hosts_present():
    comp = _generate()
    for key in ("slip-net-s1", "slip-net-s2", "victim-f1", "victim-n1"):
        assert key in comp["services"]
