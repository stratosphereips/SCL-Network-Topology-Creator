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


def test_node_image_static_attacker():
    assert app.node_image({"role": "attacker"}) == app.STATIC_ATTACKER_IMAGE
    assert app.node_entrypoint({"role": "attacker"}) == '/usr/local/bin/static-attacker-entrypoint.sh'


def test_static_attacker_type_maps_to_attacker_image():
    payload = {
        "name": "Att", "networks": [
            {
                "id": "net1", "name": "Att", "cidr": "10.77.1.0/24",
                "hosts": [
                    {"id": "a1", "name": "attack-1", "type": "static-attacker",
                     "profile": {"services": [], "connections": [], "internal": []}},
                ],
            }
        ],
        "routers": [{"id": "r1", "name": "core"}],
    }
    valid = app.validate_topology(payload)
    valid["id"] = "att-topo"
    svc = app.generate_compose(valid)["services"]["net1-a1"]
    # type static-attacker -> role attacker -> attacker image + raw-socket caps
    assert svc["image"] == app.STATIC_ATTACKER_IMAGE
    assert "NET_RAW" in svc["cap_add"]
    assert "NET_ADMIN" in svc["cap_add"]
    # it must never be treated as a slips peer
    peers = [h["name"] for net in valid["networks"] for h in net["hosts"]
             if (h.get("profile") or {}).get("slips_variant", "none") != "none"]
    assert "attack-1" not in peers


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
        # no env vars
        assert "environment" not in svc


def test_generate_compose_sensors_mount_only_runtime_logs():
    # Live runtime logs only: slips peers bind-mount exactly /var/log/slips and
    # /var/log/slips_output into EXPERIMENTS_ROOT/<experiment>/<peer> — nothing
    # else from the container is mounted.
    comp = _generate()
    for name in ("slip-net-s1", "slip-net-s2"):
        svc = comp["services"][name]
        vol = svc.get("volumes") or []
        assert len(vol) == 2
        assert any(v.endswith('/slips:/var/log/slips') for v in vol)
        assert any(v.endswith('/slips_output:/var/log/slips_output') for v in vol)
        assert all(v.startswith(app.EXPERIMENTS_ROOT) for v in vol)
    # non-sensor managed nodes (services) get no bind-mounts
    for name in ("slip-net-f1", "slip-net-n1"):
        assert "volumes" not in comp["services"][name]


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
def test_services_are_not_mutually_exclusive():
    # Any combination of services is allowed on one node (the snmp+web
    # port-8000 overlap is benign: same /www content, second server fails to
    # bind while the daemons keep running).
    p = app._normalize_profile({"services": ["snmp", "ftp"]})
    assert p["services"] == ["snmp", "ftp"]

    p = app._normalize_profile({"services": ["web", "snmp"]})
    assert p["services"] == ["web", "snmp"]

    p = app._normalize_profile({"services": ["ftp", "snmp", "web", "sqlite"]})
    assert p["services"] == ["ftp", "snmp", "web", "sqlite"]


def test_new_connection_types_registered():
    assert "reddit" in app.CONNECTION_TYPES
    assert app.CONNECTION_TYPES["reddit"]["scope"] == "external"
    assert app.CONNECTION_TYPES["reddit"]["command"] == "/scripts/internet-traffic.sh reddit"

    assert "sqlite_check" in app.CONNECTION_TYPES
    sqlite_check = app.CONNECTION_TYPES["sqlite_check"]
    assert sqlite_check["scope"] == "internal"
    assert sqlite_check["target_role"] == "sqlite"
    assert sqlite_check["command"] == "/scripts/check-sqlite.sh {target}"


def test_connection_commands_use_absolute_script_paths():
    # The images bake the scripts into /scripts and cron's default PATH does
    # not include it, so bare names would never resolve.
    for spec in app.CONNECTION_TYPES.values():
        assert "/scripts/" in spec["command"], spec


def test_sqlite_service_is_a_selectable_role_target():
    assert "sqlite" in app.SERVICES
    assert app.SERVICES["sqlite"]["target_role"] == "sqlite"


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


def test_internal_target_repeats_group_fans_out():
    # A connection pointing at an authored host with repeats=N must produce
    # one cron line per expanded instance (the group), so every clone of the
    # source keeps an identical crontab and every duplicate is contacted.
    topology = {
        "name": "t",
        "networks": [{
            "id": "n", "cidr": "10.77.1.0/24", "internet": True,
            "hosts": [
                {"id": "c1", "name": "ftp-1", "type": "normal-user", "repeats": 3,
                 "profile": {"slips_variant": "none", "services": ["ftp"], "connections": [], "internal": []}},
                {"id": "s1", "name": "scanner", "type": "normal-user", "repeats": 2,
                 "profile": {"slips_variant": "none", "services": [], "connections": [],
                              "internal": [{"id": "ftp_check", "target": "ftp-1"}]}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }
    valid = app.validate_topology(topology)
    valid["id"] = "t"
    host = valid["networks"][0]["hosts"][1]
    cron = app._connection_cron_lines(valid, host["profile"])
    assert cron == [
        "* * * * * /scripts/check-ftp.sh ftp-1",
        "* * * * * /scripts/check-ftp.sh ftp-1-2",
        "* * * * * /scripts/check-ftp.sh ftp-1-3",
    ]


def test_invalid_interval_falls_back_to_default():
    # A malformed interval (e.g. a 6-field typo from the UI) must never reach
    # the crontab: it would make cron reject the whole file and kill the node.
    topology = {
        "name": "t",
        "networks": [{
            "id": "n", "cidr": "10.77.1.0/24", "internet": True,
            "hosts": [
                {"id": "s1", "name": "scanner", "type": "normal-user",
                 "profile": {"slips_variant": "weak", "services": [],
                             "connections": [{"id": "google", "interval": "*/3 * * * * *"},
                                             {"id": "wikipedia", "interval": "garbage"}], "internal": []}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }
    valid = app.validate_topology(topology)
    cron = app._connection_cron_lines(valid, valid["networks"][0]["hosts"][0]["profile"])
    assert cron == ["*/7 * * * * /scripts/internet-traffic.sh google",
                    "*/5 * * * * /scripts/internet-traffic.sh wikipedia"]
    # and no 6-field schedule leaks through anywhere
    assert not any(c.startswith("*/3 * * * * *") for c in cron)


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
        assert "*/5 * * * * /scripts/internet-traffic.sh wikipedia" in cfg, cfg


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


# --------------------------------------------------------------------------
# 'apache' service: the slips-image webpage as a services tickbox
# --------------------------------------------------------------------------
def _apache_topology():
    return {
        "name": "apache",
        "networks": [{
            "id": "n", "cidr": "10.77.1.0/24", "internet": True,
            "hosts": [
                {"id": "s1", "name": "sensor-apache", "type": "normal-user",
                 "profile": {"slips_variant": "strong", "attacker_pivot": False,
                             "services": ["apache"], "connections": []}},
                {"id": "s2", "name": "sensor-plain", "type": "normal-user",
                 "profile": {"slips_variant": "weak", "attacker_pivot": False,
                             "services": [], "connections": []}},
                {"id": "svc1", "name": "svc-both", "type": "normal-user",
                 "profile": {"slips_variant": "none", "attacker_pivot": False,
                             "services": ["snmp", "apache"], "connections": []}},
                {"id": "svc2", "name": "svc-web", "type": "normal-user",
                 "profile": {"slips_variant": "none", "attacker_pivot": False,
                             "services": ["web"], "connections": []}},
            ],
        }],
        "routers": [{"id": "r1", "name": "core"}],
    }


def _apache_valid():
    valid = app.validate_topology(_apache_topology())
    valid["id"] = "apache"
    return valid


def _host(valid, name):
    return next(h for h in valid["networks"][0]["hosts"] if h["name"] == name)


def test_apache_service_is_registered():
    assert "apache" in app.SERVICES
    assert app.SERVICES["apache"]["target_role"] == "web"
    assert app.SERVICES["apache"]["label"] == "Apache webpage"


def test_apache_on_sensor_becomes_run_web_and_no_services_line():
    valid = _apache_valid()
    host = _host(valid, "sensor-apache")
    cfg = app.node_config(valid, host, host["profile"], ["sensor-apache", "sensor-plain"], "10.77.1.254")
    assert "RUN_WEB=1" in cfg
    assert "SERVICES='apache'" not in cfg
    assert "SLIPS_PROFILE=strong" in cfg


def test_sensor_without_apache_has_no_run_web():
    valid = _apache_valid()
    host = _host(valid, "sensor-plain")
    cfg = app.node_config(valid, host, host["profile"], ["sensor-apache", "sensor-plain"], "10.77.1.254")
    assert "RUN_WEB" not in cfg


def test_apache_on_service_host_translates_to_web():
    # 'apache' only exists on the slips image; on a service host it maps to
    # 'web', which serves the same consolidated frontpage from /www.
    valid = _apache_valid()
    host = _host(valid, "svc-both")
    cfg = app.node_config(valid, host, host["profile"], [])
    assert "SERVICES='snmp,web'" in cfg
    assert "apache" not in cfg


def test_apache_web_dedupes_when_web_also_ticked():
    topo = _apache_topology()
    topo["networks"][0]["hosts"][3]["profile"]["services"] = ["web", "apache"]
    valid = app.validate_topology(topo)
    valid["id"] = "apache"
    host = _host(valid, "svc-web")
    cfg = app.node_config(valid, host, host["profile"], [])
    assert "SERVICES='web'" in cfg
    assert "apache" not in cfg


def test_apache_sensors_join_keepalive_targets():
    valid = _apache_valid()
    targets = app.keepalive_targets(valid)
    assert "http://sensor-apache:8000" in targets
    assert "http://svc-web:8000" in targets
    assert "http://svc-both:8000" in targets
    # plain sensor never serves a page
    assert "http://sensor-plain:8000" not in targets


def test_web_internal_role_fallback_finds_apache_host():
    # A web_internal connection with no explicit target falls back to a host
    # providing the 'web' role — including an apache-ticked sensor.
    topo = _apache_topology()
    topo["networks"][0]["hosts"][1]["profile"]["connections"] = [
        {"id": "web_internal", "target": "", "interval": "*/2 * * * *"}
    ]
    valid = app.validate_topology(topo)
    host = valid["networks"][0]["hosts"][1]
    cron = app._connection_cron_lines(valid, host["profile"])
    assert cron == ["*/2 * * * * /scripts/curl-website.sh http://sensor-apache:8000"]


def test_legacy_run_web_migrates_to_apache_service():
    topo = _apache_topology()
    topo["networks"][0]["hosts"][0]["run_web"] = True
    topo["networks"][0]["hosts"][0]["profile"]["services"] = []
    valid = app.validate_topology(topo)
    host = _host(valid, "sensor-apache")
    assert "apache" in host["profile"]["services"]
    cfg = app.node_config(valid, host, host["profile"], ["sensor-apache"], "10.77.1.254")
    assert "RUN_WEB=1" in cfg
    assert "SERVICES='apache'" not in cfg


def test_apache_sensor_with_repeats_serves_on_all_clones():
    topo = _apache_topology()
    topo["networks"][0]["hosts"][0]["repeats"] = 3
    valid = app.validate_topology(topo)
    valid["id"] = "apache"
    comp = app.generate_compose(valid)
    for cid in ("n-s1", "n-s1-2", "n-s1-3"):
        ep = " ".join(comp["services"][cid]["entrypoint"])
        assert "RUN_WEB=1" in ep, cid
