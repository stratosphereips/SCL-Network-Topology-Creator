# Federation image build: SLIPS is built from an exact commit of the SLIPS
# repo (its own docker/Dockerfile) plus the plugin's federation layer, and the
# strong/middle/weak configs are rendered from the branch's own slips.yaml.
# Hermetic: docker and GitHub are stubbed.
import importlib.util
import os
import subprocess

import pytest
import yaml

import app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIGS_DIR = os.path.join(REPO_ROOT, "federation", "slips", "configs")
SHA = "0123456789abcdef0123456789abcdef01234567"


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "render_configs", os.path.join(CONFIGS_DIR, "render_configs.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render_configs = _load_renderer()

MODULE_DIRS = ["arp", "brute_force_detector", "federated_network_module",
               "network_discovery", "template", "ml_online_model"]
BASE = {
    "parameters": {"time_window_width": 3600},
    "detection": {"risk_accumulated_threat_level": 5},
    "modules": {"disable": ["template"]},
    "federated_network_module": {"mode": "train"},
}
VARIANTS = {"default": "strong",
            "variants": {"strong": ["template"], "weak": ["brute_force", "ml_online"]}}


# --------------------------------------------------------------------------
# render_configs
# --------------------------------------------------------------------------
def test_render_merges_overrides_and_sets_variant_disables():
    out = render_configs.render(
        BASE, {"parameters": {"time_window_width": 7200},
               "federated_network_module": {"time_window_width": 300}},
        VARIANTS, MODULE_DIRS)
    weak = out["slips_p2p_weak.yaml"]
    assert weak["parameters"]["time_window_width"] == 7200
    assert weak["federated_network_module"] == {"mode": "train", "time_window_width": 300}
    assert weak["modules"]["disable"] == ["brute_force", "ml_online"]
    assert out["slips_p2p.yaml"] == out["slips_p2p_strong.yaml"]
    # the base is never mutated
    assert BASE["parameters"]["time_window_width"] == 3600


@pytest.mark.parametrize("overrides, message", [
    ({"nosuchsection": {"a": 1}}, "section 'nosuchsection'"),
    ({"parameters": {"evidence_detection_threshold": 0.2}},
     "'parameters.evidence_detection_threshold'"),
])
def test_render_rejects_stale_or_unknown_override_locations(overrides, message):
    with pytest.raises(ValueError, match=message):
        render_configs.render(BASE, overrides, VARIANTS, MODULE_DIRS)


@pytest.mark.parametrize("disable, message", [
    (["brute_forse"], "matches no SLIPS module"),
    (["network"], "would disable federated_network_module"),
])
def test_render_rejects_bad_disable_names(disable, message):
    variants = {"default": "strong", "variants": {"strong": disable}}
    with pytest.raises(ValueError, match=message):
        render_configs.render(BASE, {}, variants, MODULE_DIRS)


def test_variant_config_overlay_is_applied_without_mutating_base():
    variants = {"default": "strong", "variants": {
        "strong": {"disable": ["template"]},
        "weak": {"disable": ["brute_force"],
                 "config": {"arp": {"scan_detection_rate": 0.4}}},
    }}
    out = render_configs.render(BASE, {}, variants, MODULE_DIRS)
    assert out["slips_p2p_weak.yaml"]["arp"] == {"scan_detection_rate": 0.4}
    assert out["slips_p2p_weak.yaml"]["modules"]["disable"] == ["brute_force"]
    # strong has no overlay -> no arp section (module defaults to full strength)
    assert "arp" not in out["slips_p2p_strong.yaml"]
    # the overlay is a module-dir section, not a base section, and base stays put
    assert "arp" not in BASE


def test_variant_config_rejects_unknown_section():
    variants = {"default": "strong", "variants": {
        "strong": {"disable": ["template"],
                   "config": {"nosuchsection": {"a": 1}}}}}
    with pytest.raises(ValueError, match="variant config section 'nosuchsection'"):
        render_configs.render(BASE, {}, variants, MODULE_DIRS)


def test_shipped_variants_grade_arp_detection_rate():
    with open(os.path.join(CONFIGS_DIR, "variants.yaml")) as f:
        variants = yaml.safe_load(f)["variants"]

    def rate(v):
        spec = variants[v]
        cfg = spec.get("config", {}) if isinstance(spec, dict) else {}
        return cfg.get("arp", {}).get("scan_detection_rate", 1.0)

    assert rate("strong") == 1.0 > rate("middle") > rate("weak") > 0.0


def test_shipped_variants_keep_arp_poisoner_off_and_leave_blocking_to_p():
    # blocking loads only under -p (SLIPS_BLOCKING=1); arp_poisoner would
    # ARP-spoof blocked IPs for the whole LAN, so every variant disables it
    with open(os.path.join(CONFIGS_DIR, "variants.yaml")) as f:
        variants = yaml.safe_load(f)["variants"]
    for name, spec in variants.items():
        disable = spec["disable"] if isinstance(spec, dict) else spec
        assert "arp_poisoner" in disable, name
        assert "blocking" not in disable, name


def test_entrypoint_adds_p_only_when_run_conf_asks_for_blocking(tmp_path):
    # the runner writes SLIPS_BLOCKING=1 into run.conf: node.conf is rewritten
    # by the compose start command at every container start, so a flag kept
    # there would be gone after the runner's restart
    path = os.path.join(REPO_ROOT, "federation", "slips", "slips-entrypoint.sh")
    with open(path) as f:
        text = f.read()
    blocks = "\n".join(_entrypoint_if_block(text, marker) for marker in (
        "-f /opt/network-setup/node.conf ]]", "-f /opt/network-setup/run.conf ]]",
        "SLIPS_BLOCKING:-0"))
    node, run = tmp_path / "node.conf", tmp_path / "run.conf"
    blocks = (blocks.replace("/opt/network-setup/node.conf", str(node))
              .replace("/opt/network-setup/run.conf", str(run)))
    assert "/opt/" not in blocks
    script = ("SLIPS_ARGS=(-c config/slips_p2p.yaml -i eth0 -o /var/log/slips_output)\n"
              + blocks + '\necho "$MANAGED ${SLIPS_ARGS[@]}"')
    node.write_text("SLIPS_PROFILE=weak\nGATEWAY_IP=10.77.1.254\n")
    for run_conf, want in ((None, False), ("SLIPS_BLOCKING=0\n", False),
                           ("SLIPS_BLOCKING=1\n", True)):
        if run_conf is None:
            run.unlink(missing_ok=True)
        else:
            run.write_text(run_conf)
        out = subprocess.run(["bash", "-c", script], env={"PATH": os.environ["PATH"]},
                             capture_output=True, text=True, check=True).stdout
        managed, *args = out.strip().splitlines()[-1].split()
        assert ("-p" in args) is want, run_conf
        assert managed == "1"  # run.conf never changes the managed mode
        assert args[:6] == ["-c", "config/slips_p2p.yaml", "-i", "eth0",
                            "-o", "/var/log/slips_output"]
    assert 'python3 slips.py "${SLIPS_ARGS[@]}"' in text
    assert text.index("run.conf ]]") < text.index("SLIPS_BLOCKING:-0")


def _entrypoint_if_block(text, marker):
    """The entrypoint's `if [[ ... ]]; then ... fi` block whose first line
    contains `marker`, verbatim."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if marker in l and l.startswith("if "))
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "fi")
    return "\n".join(lines[start:end + 1])


def test_shipped_overrides_and_variants_are_consistent():
    with open(os.path.join(CONFIGS_DIR, "overrides.yaml")) as f:
        overrides = yaml.safe_load(f)
    with open(os.path.join(CONFIGS_DIR, "variants.yaml")) as f:
        variants = yaml.safe_load(f)
    assert set(variants["variants"]) == set(app.SLIPS_PROFILES) - {"none"}
    assert variants["default"] in variants["variants"]
    # every overridden section is a real slips.yaml section or module-owned
    assert "federated_network_module" in overrides


def test_rendered_yaml_has_no_blank_lines_inside_sections():
    # the runner's per-run patcher treats a blank line as a section end
    text = render_configs.dump(render_configs.render(BASE, {}, VARIANTS, MODULE_DIRS)["slips_p2p_weak.yaml"])
    assert "\n\n" not in text


# --------------------------------------------------------------------------
# image build commands
# --------------------------------------------------------------------------
class _Recorder:
    def __init__(self, have_base):
        self.calls = []
        self.have_base = have_base

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        code = 0
        if cmd[:3] == ["docker", "image", "inspect"] and cmd[-1].startswith(app.SLIPS_BASE_IMAGE):
            code = 0 if self.have_base else 1
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")


def _builds(calls):
    return [c for c in calls if c[:2] == ["docker", "build"]]


def test_slips_build_uses_exact_commit_and_branch_dockerfile(monkeypatch):
    rec = _Recorder(have_base=False)
    monkeypatch.setattr(app.subprocess, "run", rec)
    assert app._docker_build_slips("fl_module_jan_rebased", SHA) == SHA
    base, layer = _builds(rec.calls)
    assert base[-1] == f"{app.SLIPS_REPO}#{SHA}"
    assert base[base.index("-f") + 1] == "docker/Dockerfile"
    assert f"SLIPS_GIT_REF={SHA}" in base
    assert f"BASE_IMAGE={app.SLIPS_BASE_IMAGE}:{SHA[:12]}" in layer
    assert f"SLIPS_COMMIT={SHA}" in layer
    assert layer[-1] == str(app.BUILD_SOURCES)
    assert ["docker", "tag", "scl-custom_challenge-slips", app.SLIPS_RUNTIME_IMAGE] in rec.calls


def test_slips_build_reuses_existing_base_for_same_commit(monkeypatch):
    rec = _Recorder(have_base=True)
    monkeypatch.setattr(app.subprocess, "run", rec)
    app._docker_build_slips("fl_module_jan_rebased", SHA)
    builds = _builds(rec.calls)
    assert len(builds) == 1 and "BASE_IMAGE=" + f"{app.SLIPS_BASE_IMAGE}:{SHA[:12]}" in builds[0]


def test_resolve_slips_commit_passes_full_sha_through():
    assert app.resolve_slips_commit(SHA) == SHA


def test_build_sources_ship_with_the_plugin():
    for rel in ("slips/Dockerfile", "slips/slips-entrypoint.sh", "service/Dockerfile",
                "service/service-entrypoint.sh", "services.json",
                "slips/configs/render_configs.py"):
        assert (app.BUILD_SOURCES / rel).is_file(), rel


@pytest.mark.parametrize("entrypoint", ["slips/slips-entrypoint.sh", "service/service-entrypoint.sh"])
def test_entrypoints_route_via_gateway(entrypoint):
    text = (app.BUILD_SOURCES / entrypoint).read_text()
    assert 'ip route replace default via "$GATEWAY_IP"' in text
