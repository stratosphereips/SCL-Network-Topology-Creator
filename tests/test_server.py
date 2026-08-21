# Basic smoke tests: does the control plane start and serve the UI + API?
# These run the real HTTP handler in-process (on a random port) against a
# throwaway data directory, so nothing touches /app/data or runs Docker.
import json
import threading
import urllib.parse
import urllib.request

import pytest

import app


@pytest.fixture()
def server(tmp_path):
    # Redirect storage to a throwaway dir for the duration of the test.
    original_data = app.DATA_DIR
    original_topo = app.TOPOLOGIES_DIR
    app.DATA_DIR = tmp_path
    app.TOPOLOGIES_DIR = tmp_path / "topologies"
    app.TOPOLOGIES_DIR.mkdir(parents=True, exist_ok=True)

    srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.TopologyHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"

    def request(method, path, body=None):
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return status, parsed, raw

    yield request

    srv.shutdown()
    srv.server_close()
    app.DATA_DIR = original_data
    app.TOPOLOGIES_DIR = original_topo


def test_ui_serves_and_injects_types(server):
    status, parsed, html = server("GET", "/")
    assert status == 200
    assert "<title>Network Topology Builder</title>" in html
    # __<REGISTRY>__ placeholders replaced at serve time; a connection id should
    # now be visible in the injected JS.
    assert "__SLIPS_PROFILES__" not in html
    assert "ftp_check" in html
    assert 'data-field="profile.slips_variant"' in html


def test_list_topologies_is_json(server):
    status, parsed, html = server("GET", "/api/topologies")
    assert status == 200
    assert "topologies" in parsed
    assert parsed["topologies"] == []


def test_create_then_get_roundtrip(server):
    body = {
        "name": "Smoke",
        "networks": [
            {
                "id": "net-a",
                "cidr": "10.77.1.0/24",
                "hosts": [{"id": "h1", "name": "slips-1", "type": "slips-peer"}],
            }
        ],
        "routers": [{"id": "r1", "name": "core"}],
    }
    status, parsed, _ = server("POST", "/api/topologies", body)
    assert status == 200
    topology_id = parsed["topology"]["id"]
    assert topology_id

    status, parsed, _ = server("GET", f"/api/topologies/{topology_id}")
    assert status == 200
    assert parsed["topology"]["name"] == "Smoke"
    assert parsed["running"] is False

    # compose file must have been generated on save
    compose = app.compose_path(topology_id)
    assert compose.exists()


def test_delete_topology_removes_files(server):
    body = {
        "name": "ToDelete",
        "networks": [
            {
                "id": "net-a",
                "cidr": "10.77.1.0/24",
                "hosts": [{"id": "h1", "name": "web-1", "type": "normal-user"}],
            }
        ],
        "routers": [{"id": "r1", "name": "core"}],
    }
    status, parsed, _ = server("POST", "/api/topologies", body)
    assert status == 200
    topology_id = parsed["topology"]["id"]

    # file + compose exist before delete
    assert app.topology_path(topology_id).exists()
    assert app.compose_path(topology_id).exists()

    status, parsed, _ = server("DELETE", f"/api/topologies/{topology_id}")
    assert status == 200
    assert parsed["status"] == "deleted"
    assert not app.topology_path(topology_id).exists()
    assert not app.compose_path(topology_id).exists()

    # deleting a missing topology -> 404
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        server("DELETE", "/api/topologies/does-not-exist")
    assert exc_info.value.code == 404
