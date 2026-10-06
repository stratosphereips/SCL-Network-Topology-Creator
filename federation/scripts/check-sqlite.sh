#!/bin/bash
# check-sqlite.sh - Fetch the SQLite DB from the sqlite service and query it
# Usage: ./check-sqlite.sh <host> [port]

HOST="${1:-ubuntu-1}"
PORT="${2:-8010}"

curl -sf --connect-timeout 5 "http://${HOST}:${PORT}/companies.db" -o /tmp/companies.db || exit 1

# Verify it is a real SQLite database and run a sample query against it.
python3 - <<'EOF' || exit 1
import sqlite3
import sys

with open('/tmp/companies.db', 'rb') as fh:
    if fh.read(16) != b'SQLite format 3\x00':
        sys.exit(1)
db = sqlite3.connect('/tmp/companies.db')
db.execute('SELECT COUNT(*) FROM companies').fetchone()
EOF
exit 0
