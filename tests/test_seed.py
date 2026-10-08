# Bundled topologies seed into the data volume on startup, absent-only.
import json

import app


def _bundle(tmp_path, tid="medium"):
    d = tmp_path / "bundle" / tid
    d.mkdir(parents=True)
    (d / "topology.json").write_text(json.dumps({
        "id": tid, "name": "Medium experiment",
        "networks": [{"id": "fed", "name": "Federation", "cidr": "172.20.1.0/24",
                      "internet": True, "hosts": [
                          {"id": "s1", "name": "slips-1",
                           "profile": {"slips_variant": "strong", "services": [],
                                       "connections": [{"id": "news", "interval": "*/4 * * * *"}]}}]}],
        "routers": [{"id": "r1", "name": "core"}],
    }))
    return tmp_path / "bundle"


def test_seed_creates_absent_topology(tmp_path, monkeypatch):
    vol = tmp_path / "vol"; vol.mkdir()
    monkeypatch.setattr(app, "TOPOLOGIES_DIR", vol)
    monkeypatch.setattr(app, "BUNDLED_TOPOLOGIES_DIR", _bundle(tmp_path))
    app.seed_topologies()
    assert (vol / "medium" / "topology.json").exists()
    assert (vol / "medium" / "docker-compose.yml").exists()
    inv = (vol / "medium" / "inventory.md").read_text()
    assert "Topology inventory — Medium experiment" in inv
    assert "BBC News" in inv  # the news connection surfaced in the doc


def test_seed_does_not_overwrite_existing(tmp_path, monkeypatch):
    vol = tmp_path / "vol"; (vol / "medium").mkdir(parents=True)
    (vol / "medium" / "topology.json").write_text('{"id":"medium","name":"LOCAL EDIT"}')
    monkeypatch.setattr(app, "TOPOLOGIES_DIR", vol)
    monkeypatch.setattr(app, "BUNDLED_TOPOLOGIES_DIR", _bundle(tmp_path))
    app.seed_topologies()
    assert json.loads((vol / "medium" / "topology.json").read_text())["name"] == "LOCAL EDIT"


def test_bundled_topologies_are_small_medium_large():
    ids = sorted(p.name for p in app.BUNDLED_TOPOLOGIES_DIR.glob("*") if (p / "topology.json").exists())
    assert ids == ["large", "medium", "small"]
