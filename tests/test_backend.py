# Basic backend unit tests for the topology creator.
# Purpose: catch regressions in the core logic (profile→image/config baking,
# validate_topology normalization, and generate_compose output).
import pytest

import app


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
                        "id": "s1", "name": "slips-1", "type": "normal-user",
                        "run_web": True,
                        "profile": {"slips_variant": "weak", "attacker_pivot": False,
                                    "services": [], "connections": ["wikipedia"], "internal": []},
                    },
                    {"id": "s2", "name": "slips-2", "type": "normal-user",
                     "profile": {"slips_variant": "strong", "attacker_pivot": False,
                                 "services": [], "connections": [], "internal": []}},
                    {"id": "f1", "name": "ftp-1", "type": "normal-user",
                     "profile": {"slips_variant": "none", "attacker_pivot": False,
                                 "services": ["ftp"], "connections": [], "internal": []}},
                    {"id": "n1", "name": "snmp-1", "type": "normal-user",
                     "profile": {"slips_variant": "none", "attacker_pivot": False,
                                 "services": ["snmp"], "connections": [], "internal": ["ftp_check"]}},
                ],
            }
        ],
        "routers": [{"id": "r1", "name": "core"}],
    }


# --------------------------------------------------------------------------
# node_image / node_entrypoint — composed from the profile, not a type enum
# --------------------------------------------------------------------------
def test_node_image_sensor():
    assert app.node_image({"slips_variant": "weak"}) == app.SLIPS_RUNTIME_IMAGE
    assert app.node_image({"slips_variant": "strong"}) == app.SLIPS_RUNTIME_IMAGE


def test_node_image_service():
    assert app.node_image({"slips_variant": "none", "services": ["ftp"]}) == app.SERVICE_RUNTIME_IMAGE


def test_node_image_plain():
    assert app.node_image({}) == app.BASE_IMAGE
    assert app.node_image({"slips_variant": "none", "services": []}) == app.BASE_IMAGE


def test_node_entrypoint():
    assert app.node_entrypoint({"slips_variant": "weak"}) == "/usr/local/bin/slips-entrypoint.sh"
    assert app.node_entrypoint({"services": ["snmp"]}) == "/usr/local/bin/service-entrypoint.sh"
    assert app.node_entrypoint({}) is None


def test_is_managed_node():
    assert app.is_managed_node({"slips_variant": "weak"}) is True
    assert app.is_managed_node({"services": ["ftp"]}) is True
    assert app.is_managed_node({}) is False


def test_no_fused_federation_types_remain():
    # There are no slips-ftp / slips-peer / pivot type enums anymore.
    for fused in ("slips-peer", "slip-ftp", "slip-snmp", "pivot", "aracne-attacker"):
        assert fused not in app.HOST_TYPES


# --------------------------------------------------------------------------
# validate_topology
# --------------------------------------------------------------------------
def test_validate_topology_basic_and_profile():
    valid = app.validate_topology(_basic_topology())
    assert len(valid["networks"]) == 1
    assert valid["networks"][0]["hosts"][0]["profile"]["slips_variant"] == "weak"
    assert valid["networks"][0]["hosts"][2]["profile"]["services"] == ["ftp"]


def test_validate_topology_requires_name():
    with pytest.raises(ValueError):
        app.validate_topology({"networks": []})


def test_validate_topology_unknown_profile_fields_dropped():
    t = {
        "name": "t",
        "networks": [{"id": "n", "cidr": "10.77.9.0/24", "hosts": [
            {"id": "h", "profile": {"slips_variant": "bogus-tier",
                                    "services": ["nope"], "connections": ["wikipedia"], "internal": []}}
        ]}],
    }
    valid = app.validate_topology(t)
    p = valid["networks"][0]["hosts"][0]["profile"]
    assert p["slips_variant"] == "none"  # unknown variant -> none
    assert p["services"] == []           # unknown service -> dropped


def test_validate_topology_at_most_one_attacker_pivot():
    t = {
        "name": "t",
        "networks": [{"id": "n", "cidr": "10.77.9.0/24", "hosts": [
            {"id": "a", "profile": {"attacker_pivot": True}},
            {"id": "b", "profile": {"attacker_pivot": True}},
        ]}],
    }
    with pytest.raises(ValueError, match="attacker pivot"):
        app.validate_topology(t)


# --------------------------------------------------------------------------
# generate_compose — the docker config baking
# --------------------------------------------------------------------------
def _generate():
    valid = app.validate_topology(_basic_topology())
    valid["id"] = "test-lab"
    return app.generate_compose(valid)


def test_generate_compose_images_from_profile():
    comp = _generate()
    assert comp["services"]["slip-net-s1"]["image"] == app.SLIPS_RUNTIME_IMAGE
    assert comp["services"]["slip-net-s2"]["image"] == app.SLIPS_RUNTIME_IMAGE
    assert comp["services"]["slip-net-f1"]["image"] == app.SERVICE_RUNTIME_IMAGE
    assert comp["services"]["slip-net-n1"]["image"] == app.SERVICE_RUNTIME_IMAGE


def test_generate_compose_sensor_env_and_resources():
    s1 = _generate()["services"]["slip-net-s1"]
    env = s1.get("environment", {})
    assert env.get("SLIPS_PROFILE") == "weak"
    assert env.get("SLIPS_PEERS") == "slips-1,slips-2"  # only sensors
    assert env.get("RUN_WEB") == "1"
    assert s1["cpus"] == 1 and s1["mem_limit"] == "2g"  # weak resources
    assert s1["cap_add"] == ["NET_ADMIN", "NET_RAW", "SYS_ADMIN"]


def test_generate_compose_service_env():
    f1 = _generate()["services"]["slip-net-f1"]
    assert f1.get("environment", {}).get("SERVICES") == "ftp"
    assert f1.get("cap_add") == ["NET_ADMIN"]


def test_generate_compose_internal_target_resolution():
    # snmp-1 has internal connection ftp_check -> resolves to ftp-1 hostname,
    # delivered to the entrypoint via EXTRA_CRON so it isn't clobbered.
    n1 = _generate()["services"]["slip-net-n1"]
    extra = n1.get("environment", {}).get("EXTRA_CRON", "")
    assert "check-ftp.sh ftp-1" in extra


def test_generate_compose_cron_only_when_present():
    comp = _generate()
    assert "internet-traffic.sh wikipedia" in comp["services"]["slip-net-s1"]["environment"]["EXTRA_CRON"]
    # slips-2 has no connections -> no EXTRA_CRON, no command override
    assert "EXTRA_CRON" not in comp["services"]["slip-net-s2"].get("environment", {})
    assert comp["services"]["slip-net-s2"].get("command") is None


def test_generate_compose_cron_not_clobbered_by_entrypoint():
    """Regression: connection crontab lines must reach the container.

    Previously the plugin wrote the crontab inline in the command, which the
    image entrypoint then overwrote with its own crontab (clobbering the baked
    traffic). Now the crontab is passed to the entrypoint via EXTRA_CRON so it
    merges rather than replaces.
    """
    comp = _generate()

    # Sensor with a connection: EXTRA_CRON carries the resolved traffic line,
    # and the command must NOT itself write crontab (entrypoint merges it).
    s1 = comp["services"]["slip-net-s1"]
    assert "EXTRA_CRON" in s1.get("environment", {})
    assert "internet-traffic.sh wikipedia" in s1["environment"]["EXTRA_CRON"]
    assert "crontab" not in s1["command"][-1]

    # Service host with an internal connection: EXTRA_CRON has the resolved
    # target (service role -> real hostname), so it survives the entrypoint.
    n1 = comp["services"]["slip-net-n1"]
    assert "EXTRA_CRON" in n1.get("environment", {})
    assert "check-ftp.sh ftp-1" in n1["environment"]["EXTRA_CRON"]
    assert "crontab" not in n1["command"][-1]

    # A managed node with no traffic leaves no EXTRA_CRON.
    s2 = comp["services"]["slip-net-s2"]
    assert "EXTRA_CRON" not in s2.get("environment", {})


def test_generate_compose_networks_created():
    comp = _generate()
    assert "topo_slip-net" in comp["networks"]


def test_generate_compose_all_hosts_present():
    comp = _generate()
    for key in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        assert key in comp["services"]
