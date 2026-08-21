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
# generate_compose — the docker config baking (config file, not env)
# --------------------------------------------------------------------------
def _generate():
    valid = app.validate_topology(_basic_topology())
    valid["id"] = "test-lab"
    return app.generate_compose(valid)


def _config(service_name):
    # Build topology same way, then read the node_config for a service.
    valid = app.validate_topology(_basic_topology())
    valid["id"] = "test-lab"
    peers = [h["name"] for net in valid["networks"] for h in net["hosts"]
             if h["profile"]["slips_variant"] != "none"]
    for net in valid["networks"]:
        for host in net["hosts"]:
            if f'{net["id"]}-{host["id"]}' == service_name:
                return app.node_config(valid, host, host["profile"], peers)
    raise KeyError(service_name)


def test_generate_compose_images_from_profile():
    comp = _generate()
    assert comp["services"]["slip-net-s1"]["image"] == app.SLIPS_RUNTIME_IMAGE
    assert comp["services"]["slip-net-s2"]["image"] == app.SLIPS_RUNTIME_IMAGE
    assert comp["services"]["slip-net-f1"]["image"] == app.SERVICE_RUNTIME_IMAGE
    assert comp["services"]["slip-net-n1"]["image"] == app.SERVICE_RUNTIME_IMAGE


def test_generate_compose_no_env_for_managed_nodes():
    # Config is the only source of truth: managed nodes must NOT get node setup
    # as environment variables.
    for name in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        svc = _generate()["services"][name]
        env = svc.get("environment", {})
        for key in ("SLIPS_PROFILE", "SLIPS_PEERS", "SERVICES", "EXTRA_CRON", "RUN_WEB"):
            assert key not in env, f"{name} leaked env var {key}"


def test_generate_compose_managed_nodes_bake_config_via_entrypoint():
    comp = _generate()
    for name in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        svc = comp["services"][name]
        # config is embedded in the entrypoint (writes node.conf then runs runtime)
        ep = " ".join(svc["entrypoint"])
        assert app.NODE_CONFIG_PATH in ep
        # no env vars, no bind-mounts
        assert "environment" not in svc
        assert "volumes" not in svc


def test_node_config_sensor():
    c = _config("slip-net-s1")
    assert "SLIPS_PROFILE=weak" in c
    assert "SLIPS_PEERS='slips-1,slips-2'" in c  # only sensors
    assert "RUN_WEB=1" in c
    assert "EXTRA_CRON='" in c and "internet-traffic.sh wikipedia" in c
    # sensor with no traffic lines leaves EXTRA_CRON out
    assert "EXTRA_CRON" not in _config("slip-net-s2")


def test_node_config_service_and_internal_target():
    c = _config("slip-net-n1")
    assert "SERVICES='snmp'" in c
    assert "check-ftp.sh ftp-1" in c  # internal target resolved to service host
    assert "SLIPS_PROFILE" not in c


def test_node_config_resources_capacity():
    s1 = _generate()["services"]["slip-net-s1"]
    assert s1["cpus"] == 1 and s1["mem_limit"] == "2g"  # weak
    s2 = _generate()["services"]["slip-net-s2"]
    assert s2["cpus"] == 4 and s2["mem_limit"] == "8g"  # strong
    assert s1["cap_add"] == ["NET_ADMIN", "NET_RAW", "SYS_ADMIN"]


def test_generate_compose_all_hosts_present():
    comp = _generate()
    for key in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        assert key in comp["services"]


def test_managed_nodes_have_no_environment_at_all():
    for name in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        assert "environment" not in _generate()["services"][name]


def test_generate_compose_networks_created():
    comp = _generate()
    assert "topo_slip-net" in comp["networks"]


def test_generate_compose_all_hosts_present():
    comp = _generate()
    for key in ("slip-net-s1", "slip-net-s2", "slip-net-f1", "slip-net-n1"):
        assert key in comp["services"]


# --------------------------------------------------------------------------
# new federation behaviours: exclusive services, repeats, internal targets,
# egress default
# --------------------------------------------------------------------------
def test_snmp_and_web_are_mutually_exclusive():
    p = app._normalize_profile({"services": ["snmp", "web"]})
    assert p["services"] in (["snmp"], ["web"])  # only first of the group kept

    p = app._normalize_profile({"services": ["web", "snmp"]})
    assert p["services"] == ["web"]  # first occurrence retained, snmp dropped


def test_internal_connections_normalized_with_target():
    p = app._normalize_profile({"internal": ["ftp_check", {"id": "web_internal", "target": "web-1"}]})
    assert "internal" not in p  # folded into unified connections
    entries = {e["id"]: e["target"] for e in p["connections"]}
    assert entries == {"ftp_check": "", "web_internal": "web-1"}


def test_connections_interval_override_preserved():
    p = app._normalize_profile({"connections": [{"id": "wikipedia", "interval": "*/2 * * * *"}]})
    assert p["connections"] == [{"id": "wikipedia", "target": "", "interval": "*/2 * * * *"}]


def test_repeats_expansion_unique_names_and_ips():
    topology = {
        "name": "r",
        "networks": [{
            "id": "n", "cidr": "10.77.1.0/24", "internet": True, "hosts": [
                {"id": "s1", "name": "slips-1", "type": "normal-user", "repeats": 3,
                 "profile": {"slips_variant": "weak", "services": [], "connections": [], "internal": []}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }
    valid = app.validate_topology(topology)
    valid["id"] = "rep"
    comp = app.generate_compose(valid)
    assert "n-s1" in comp["services"]
    assert "n-s1-2" in comp["services"]
    assert "n-s1-3" in comp["services"]
    peers = app.peer_names_of(valid)
    assert peers == ["slips-1", "slips-1-2", "slips-1-3"]


def test_internal_target_resolves_to_explicit_device():
    topology = {
        "name": "t",
        "networks": [{
            "id": "n", "cidr": "10.77.1.0/24", "internet": True,
            "hosts": [
                {"id": "c1", "name": "client", "type": "normal-user",
                 "profile": {"slips_variant": "none", "services": ["ftp"], "connections": [], "internal": []}},
                {"id": "s1", "name": "scanner", "type": "normal-user", "repeats": 2,
                 "profile": {"slips_variant": "none", "services": [], "connections": [],
                             "internal": [{"id": "ftp_check", "target": "client"}]}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }
    valid = app.validate_topology(topology)
    valid["id"] = "t"
    host = valid["networks"][0]["hosts"][1]
    cron = app._connection_cron_lines(valid, host["profile"])
    assert any("check-ftp.sh client" in line for line in cron)


# --------------------------------------------------------------------------
# Docker multiplication (repeats): specs -> compose + node.conf baking
# --------------------------------------------------------------------------
def _repeat_topology():
    return {
        "name": "scale",
        "networks": [{
            "id": "fed", "cidr": "172.20.1.0/24", "internet": True,
            "hosts": [
                {"id": "s1", "name": "slips-1", "type": "normal-user", "repeats": 3,
                 "profile": {"slips_variant": "weak", "services": [], "connections": [
                     {"id": "wikipedia", "interval": "*/5 * * * *"}]}},
                {"id": "f1", "name": "ftp-1", "type": "normal-user",
                 "profile": {"slips_variant": "none", "services": ["ftp"], "connections": []}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }


def test_repeats_yield_one_docker_per_replica():
    valid = app.validate_topology(_repeat_topology())
    valid["id"] = "scale"
    comp = app.generate_compose(valid)
    # 3 slips replicas + 1 ftp + 1 router
    slips_services = [k for k in comp["services"] if k.startswith("fed-s1")]
    assert len(slips_services) == 3
    for name in ("fed-s1", "fed-s1-2", "fed-s1-3"):
        assert name in comp["services"]
        assert comp["services"][name]["image"] == app.SLIPS_RUNTIME_IMAGE
        ep = " ".join(comp["services"][name]["entrypoint"])
        assert app.NODE_CONFIG_PATH in ep  # baked, not env
        assert "environment" not in comp["services"][name]


def test_repeats_each_replica_gets_unique_ip():
    valid = app.validate_topology(_repeat_topology())
    valid["id"] = "scale"
    comp = app.generate_compose(valid)
    net_key = "topo_fed"
    ips = []
    for k in ("fed-s1", "fed-s1-2", "fed-s1-3"):
        ips.append(comp["services"][k]["networks"][net_key]["ipv4_address"])
    assert len(set(ips)) == 3, f"replicas share IPs: {ips}"
    # sequential allocation: .11, .12, .13
    assert ips == ["172.20.1.11", "172.20.1.12", "172.20.1.13"], ips


def test_repeats_peers_include_all_replicas():
    valid = app.validate_topology(_repeat_topology())
    valid["id"] = "scale"
    peers = app.peer_names_of(valid)
    assert peers == ["slips-1", "slips-1-2", "slips-1-3"]
    # each replica's node.conf has the full peer list
    for replica in ("slips-1", "slips-1-2", "slips-1-3"):
        host = valid["networks"][0]["hosts"][0]
        cfg = app.node_config(valid, {**host, "name": replica}, host["profile"], peers)
        assert f"SLIPS_PEERS='slips-1,slips-1-2,slips-1-3'" in cfg, cfg


def test_repeats_replica_cron_baked_everywhere():
    valid = app.validate_topology(_repeat_topology())
    valid["id"] = "scale"
    peers = app.peer_names_of(valid)
    for replica in ("slips-1", "slips-1-2", "slips-1-3"):
        host = valid["networks"][0]["hosts"][0]
        cfg = app.node_config(valid, {**host, "name": replica}, host["profile"], peers)
        assert "*/5 * * * * internet-traffic.sh wikipedia" in cfg, cfg


def test_repeats_replicas_are_never_attacker_pivot():
    valid = app.validate_topology({
        "name": "p",
        "networks": [{"id": "n", "cidr": "10.77.1.0/24", "internet": True, "hosts": [
            {"id": "h", "name": "h", "type": "normal-user", "repeats": 2,
             "profile": {"slips_variant": "weak", "attacker_pivot": True, "services": [], "connections": []}},
        ]}],
        "routers": [{"id": "r1", "name": "core"}],
    })
    # original keeps attacker_pivot, its replica does not
    assert valid["networks"][0]["hosts"][0]["profile"]["attacker_pivot"] is True
    expanded = app.expand_repeats(valid["networks"][0]["hosts"])
    assert expanded[0]["profile"]["attacker_pivot"] is True
    assert expanded[1]["profile"]["attacker_pivot"] is False


def test_egress_defaults_to_on():
    topology = {"name": "e", "networks": [{"id": "n", "cidr": "10.77.1.0/24", "hosts": [
        {"id": "h", "name": "h1", "type": "normal-user", "profile": {}}]}]}
    valid = app.validate_topology(topology)
    assert valid["networks"][0]["internet"] is True


def test_repeats_default_to_1():
    topology = {"name": "d", "networks": [{"id": "n", "cidr": "10.77.1.0/24", "hosts": [
        {"id": "h", "name": "h1", "type": "normal-user"}]}]}
    valid = app.validate_topology(topology)
    assert valid["networks"][0]["hosts"][0]["repeats"] == 1
