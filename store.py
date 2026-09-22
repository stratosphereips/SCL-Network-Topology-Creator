import json
import re
import shutil

import app


def topology_dir(topology_id):
    return app.TOPOLOGIES_DIR / topology_id


def topology_path(topology_id):
    return topology_dir(topology_id) / 'topology.json'


def compose_path(topology_id):
    return topology_dir(topology_id) / 'docker-compose.yml'


def read_json(path):
    with open(path, 'r', encoding='utf8') as file:
        return json.load(file)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf8') as file:
        json.dump(payload, file, indent=2, sort_keys=True)
        file.write('\n')


def delete_topology(topology_id):
    """Delete a saved topology and all generated files in its directory.

    Topology IDs are normalized when they are saved. Enforcing that same shape
    here keeps the recursive removal confined to a direct child of
    TOPOLOGIES_DIR.
    """
    topology_id = str(topology_id or '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', topology_id):
        raise ValueError('Invalid topology id.')

    directory = topology_dir(topology_id)
    if not topology_path(topology_id).is_file():
        return False
    shutil.rmtree(directory)
    return True
