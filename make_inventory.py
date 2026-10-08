#!/usr/bin/env python3
"""Render a human-readable inventory for a topology (who connects to whom).

Used both by the plugin (to (re)write topologies/<id>/inventory.md when a
topology is saved or seeded) and as a CLI:

    python make_inventory.py topologies/medium/topology.json
"""
import json
import sys

# Short human descriptions of where each external connection goes. Internal
# ones resolve their destination from the host's `target`.
_DEST = {
    'wikipedia': 'en.wikipedia.org — a few random articles, with pauses',
    'google': 'google.com',
    'reddit': 'reddit.com — open feed, read ~30s, reload',
    'github': 'github.com — homepage, trending, a few repos, with pauses',
    'news': 'bbc.com/news — front page then a few articles, with pauses',
    'images': 'wikimedia/wikipedia images, with pauses',
    'web_internal': 'an internal web host (:8000)',
    'ftp_check': 'an internal FTP host',
    'sqlite_check': 'an internal SQLite host',
}


def _role(host):
    p = host.get('profile') or {}
    variant = p.get('slips_variant', 'none')
    if variant != 'none':
        return f'SLIPS sensor ({variant})'
    if p.get('attacker_pivot'):
        return 'Attacker pivot (aracne SSH entry)'
    if p.get('role') == 'attacker':
        return 'Static attacker'
    return 'Host'


def inventory_markdown(topology, connection_types, services):
    """Return the inventory markdown for one topology dict."""
    top = topology.get('topology', topology)
    tid = top.get('id', '?')
    lines = [
        f"# Topology inventory — {top.get('name', tid)}",
        '',
        f"_id: `{tid}`. Generated from topology.json by make_inventory.py; "
        'the Topology Creator is the source of truth._',
        '',
    ]
    nets = top.get('networks', [])
    lines.append('**Networks:** ' + ', '.join(
        f"{n.get('name', n.get('id'))} (`{n.get('cidr', '?')}`, "
        f"internet={'yes' if n.get('internet') else 'no'})" for n in nets))
    lines += ['', '## Hosts', '',
              '| Host | Role | Services | Outbound connections |',
              '|---|---|---|---|']
    all_hosts = []
    for net in nets:
        for host in net.get('hosts', []):
            p = host.get('profile') or {}
            all_hosts.append(host)
            svc = ', '.join(services.get(s, {}).get('label', s)
                            for s in (p.get('services') or [])) or '—'
            conns = []
            for c in (p.get('connections') or []):
                meta = connection_types.get(c['id'], {})
                tgt = f" → {c['target']}" if c.get('target') else ''
                conns.append(f"{meta.get('label', c['id'])}{tgt} ({c.get('interval', '')})")
            lines.append(f"| {host.get('name')} | {_role(host)} | {svc} | "
                         f"{'<br>'.join(conns) if conns else '—'} |")
    used = sorted({c['id'] for h in all_hosts
                   for c in ((h.get('profile') or {}).get('connections') or [])})
    if used:
        lines += ['', '## Connection types used', '']
        for u in used:
            meta = connection_types.get(u, {})
            lines.append(f"- **{meta.get('label', u)}** ({meta.get('scope', '')}) — "
                         f"{_DEST.get(u, '')}")
    browsers = [h.get('name') for h in all_hosts
                if any(c['id'] in ('wikipedia', 'google', 'reddit', 'github', 'news', 'images')
                       for c in ((h.get('profile') or {}).get('connections') or []))]
    lines += ['', '## Notes', '',
              f"- Personal-PC browsers (external web traffic): "
              f"{', '.join(browsers) or 'none'}.",
              '- Hosts with only internal/service connections or none read as '
              'infrastructure (e.g. the DB host).',
              '- The static attacker runs deterministic nmap/hydra against the '
              'subnet; the aracne pivot is the LLM agent’s SSH entry point.', '']
    return '\n'.join(lines) + '\n'


def main(argv):
    import app  # for CONNECTION_TYPES / SERVICES
    for path in argv[1:]:
        topology = json.load(open(path))
        md = inventory_markdown(topology, app.CONNECTION_TYPES, app.SERVICES)
        out = path.rsplit('/', 1)[0] + '/inventory.md'
        open(out, 'w').write(md)
        print('wrote', out)


if __name__ == '__main__':
    main(sys.argv)
