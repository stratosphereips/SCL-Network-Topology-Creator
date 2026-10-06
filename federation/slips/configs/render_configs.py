#!/usr/bin/env python3
"""Render the federation SLIPS detector configs at image build time.

base (the SLIPS branch's own config/slips.yaml, never edited)
  + overrides.yaml (shared federation deltas)
  + variants.yaml  (per-variant modules.disable)
  -> <out-dir>/slips_p2p_<variant>.yaml, and slips_p2p.yaml = default variant

Fails the build (exit 1) on:
- an override section missing from the base, or an override key missing
  from its base section (stale/typo'd locations), except in sections the
  federated module owns;
- a disable name that matches no module directory (SLIPS matching rule);
- a disable name that would match the federated module itself.

Output is plain block YAML (2-space indent, no blank lines inside
sections) so the runner's line-based per-run patching stays reliable.
"""
import argparse
import os
import sys

import yaml

# Sections whose keys are read by the federated module itself; new keys are
# allowed there (the base only carries the module's defaults).
MODULE_OWNED_SECTIONS = {"federated_network_module"}
FEDERATED_MODULE_DIR = "federated_network_module"


def normalize(name):
    """SLIPS' module-name normalization (config_mixin._normalize_module_name)."""
    return str(name).replace(" ", "").replace("_", "").replace("-", "").lower()


def matching_modules(disable_name, module_dirs):
    """Module dirs a disable entry hits under SLIPS' substring rule."""
    needle = normalize(disable_name)
    return [d for d in module_dirs if needle and needle in normalize(f"modules.{d}.{d}")]


def apply_overrides(base, overrides):
    """Return base with overrides merged in; raise ValueError on bad keys."""
    errors = []
    merged = dict(base)
    for section, values in overrides.items():
        if section not in base or not isinstance(base[section], dict):
            errors.append(f"override section '{section}' not in base config")
            continue
        new_section = dict(base[section])
        for key, value in values.items():
            if key not in base[section] and section not in MODULE_OWNED_SECTIONS:
                errors.append(f"override key '{section}.{key}' not in base config")
                continue
            new_section[key] = value
        merged[section] = new_section
    if errors:
        raise ValueError("; ".join(errors))
    return merged


def validate_disable_list(variant, names, module_dirs):
    """Raise ValueError when a disable entry is unknown or hits our module."""
    errors = []
    for name in names:
        hits = matching_modules(name, module_dirs)
        if not hits:
            errors.append(f"{variant}: '{name}' matches no SLIPS module")
        if FEDERATED_MODULE_DIR in hits:
            errors.append(f"{variant}: '{name}' would disable {FEDERATED_MODULE_DIR}")
    if errors:
        raise ValueError("; ".join(errors))


def render(base, overrides, variants_doc, module_dirs):
    """Return {filename: config_dict} for every variant plus the default."""
    merged = apply_overrides(base, overrides)
    variants = variants_doc["variants"]
    default = variants_doc["default"]
    if default not in variants:
        raise ValueError(f"default variant '{default}' not defined")
    out = {}
    for variant, disable in variants.items():
        validate_disable_list(variant, disable, module_dirs)
        cfg = dict(merged)
        cfg["modules"] = {**(merged.get("modules") or {}), "disable": list(disable)}
        out[f"slips_p2p_{variant}.yaml"] = cfg
    out["slips_p2p.yaml"] = out[f"slips_p2p_{default}.yaml"]
    return out


def dump(cfg):
    return yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--overrides", required=True)
    ap.add_argument("--variants", required=True)
    ap.add_argument("--modules-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    with open(args.base) as f:
        base = yaml.safe_load(f)
    with open(args.overrides) as f:
        overrides = yaml.safe_load(f) or {}
    with open(args.variants) as f:
        variants_doc = yaml.safe_load(f)
    module_dirs = sorted(
        d for d in os.listdir(args.modules_dir)
        if os.path.isdir(os.path.join(args.modules_dir, d)) and not d.startswith("_")
    )
    try:
        rendered = render(base, overrides, variants_doc, module_dirs)
    except ValueError as exc:
        print(f"render_configs: {exc}", file=sys.stderr)
        return 1
    header = "# GENERATED at image build by federation/slips/configs/render_configs.py\n"
    for name, cfg in rendered.items():
        with open(os.path.join(args.out_dir, name), "w") as f:
            f.write(header + dump(cfg))
        print(f"render_configs: wrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
