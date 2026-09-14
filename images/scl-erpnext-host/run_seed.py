#!/usr/bin/env python3
"""Run seed_erpnext.run() inside a Frappe site context.

`bench execute <file>:<func>` does NOT work (bench evals the method string as a
dotted Python path, so `file.py:func` is a SyntaxError). This wrapper is the
robust equivalent: init frappe for the site, run the seed, commit. Invoked by
erpnext-app-start.sh as:

    env/bin/python /usr/local/bin/run_seed.py <site>     # cwd = bench sites/
"""
import sys

sys.path.insert(0, "/usr/local/bin")
import frappe  # noqa: E402

site = sys.argv[1] if len(sys.argv) > 1 else "erpnext.localhost"
frappe.init(site=site)
frappe.connect()
import seed_erpnext  # noqa: E402

seed_erpnext.run()
frappe.db.commit()
print("[run_seed] done")
