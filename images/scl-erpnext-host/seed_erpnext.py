#!/usr/bin/env python3
"""Seed ERPNext with known demo users (one per privilege level, weak passwords =
the username — the cred-attack surface, by design) + a small set of sample business
records, so the pentest target has realistic data and role-tiered logins.

Run at first boot via:
    bench --site erpnext.localhost execute /usr/local/bin/seed_erpnext.py:run

Defensive: every step is wrapped so a single failure (a renamed doctype, a missing
default) never aborts the whole seed. The USERS are the priority; business data is
best-effort. Idempotent: re-running is safe (skip-if-exists everywhere).
"""
import frappe


def _log(msg):
    print(f"[seed_erpnext] {msg}", flush=True)


def _set_password(email, password):
    """Set a known password for a Frappe user (writes the hashed __Auth row).

    Uses frappe.utils.password.update_password(user, pwd) directly so the weak,
    dictionary-word demo passwords bypass the User doctype's password-strength
    validator (which would reject `admin`, `salesuser`, ... as 'common words').
    """
    try:
        from frappe.utils.password import update_password
        update_password(user=email, pwd=password)
    except Exception as exc:  # pragma: no cover
        _log(f"WARNING: could not set password for {email}: {exc!r}")


def ensure_user(email, full_name, password, roles):
    """Create-or-update a user with a known password + roles. Idempotent."""
    try:
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)
            user.enabled = 1
            user.first_name = full_name
            user.save(ignore_permissions=True)
        else:
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": full_name,
                "enabled": 1,
                "send_welcome_email": 0,
            })
            user.insert(ignore_permissions=True)
        _set_password(email, password)
        for role in roles:
            if frappe.db.exists("Role", role):
                user.add_roles(role)
            else:
                _log(f"role '{role}' not installed — skipping for {email}")
        _log(f"user {email} / {password}  roles={roles}")
        return user
    except Exception as exc:  # pragma: no cover
        _log(f"WARNING: ensure_user({email}) failed: {exc!r}")
        return None


def ensure_company():
    """Create the default Company + minimal defaults (ERPNext new-site does NOT run
    the Setup Wizard, so no Company exists until we make one). Company insert builds
    the chart of accounts, default warehouses, cost centers, etc."""
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if company and frappe.db.exists("Company", company):
        return company
    name = "SCL Industries"
    if not frappe.db.exists("Company", name):
        # ERPNext Company insert builds a transit warehouse of type "Transit"; that
        # Warehouse Type isn't seeded until the Setup Wizard runs (which we skip).
        # Warehouse Type uses `autoname: Prompt` (no name field) → set the name via
        # set_name=, not a field, or insert fails with "Please set the document name".
        for wt in ("Transit",):
            if not frappe.db.exists("Warehouse Type", wt):
                try:
                    frappe.get_doc({"doctype": "Warehouse Type"}).insert(
                        set_name=wt, ignore_permissions=True)
                    _log(f"created Warehouse Type {wt}")
                except Exception as exc:  # pragma: no cover
                    _log(f"WARNING: warehouse type {wt} failed: {exc!r}")
        try:
            doc = frappe.get_doc({
                "doctype": "Company",
                "company_name": name,
                "abbr": "SCL",
                "default_currency": "USD",
                "country": "United States",
                "chart_of_accounts": "Standard",
                "enable_perpetual_inventory": 1,
            })
            doc.insert(ignore_permissions=True)
            company = doc.name
            _log(f"created company {company}")
        except Exception as exc:  # pragma: no cover
            _log(f"WARNING: company create failed: {exc!r}")
    else:
        company = name
    try:
        gd = frappe.get_doc("Global Defaults")
        gd.default_company = company
        gd.save(ignore_permissions=True)
    except Exception as exc:  # pragma: no cover
        _log(f"WARNING: set default company failed: {exc!r}")
    return company


def ensure_viewer_role():
    """A minimal custom role (Desk access only, no doctype perms) for the low-priv
    'guest' account — loginable but effectively read-only."""
    role = "Viewer"
    try:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
                "disabled": 0,
            }).insert(ignore_permissions=True)
            _log(f"created role {role}")
    except Exception as exc:  # pragma: no cover
        _log(f"WARNING: viewer role create failed: {exc!r}")
    return role


def ensure_defaults():
    """Create the Setup-Wizard defaults ERPNext business doctypes link to: the
    root nodes of the Customer Group / Territory / Item Group trees, a Supplier
    Group, and the Nos unit of measure. new-site + Company insert do NOT create
    these (the Setup Wizard does, which we skip)."""
    tree_roots = [
        ("Customer Group", "customer_group_name", "All Customer Groups", "parent_customer_group"),
        ("Territory", "territory_name", "All Territories", "parent_territory"),
        ("Item Group", "item_group_name", "All Item Groups", "parent_item_group"),
    ]
    for doctype, name_field, name, parent_field in tree_roots:
        if not frappe.db.exists(doctype, name):
            for parent in (None, name):  # root node: empty parent, else self-parent
                try:
                    frappe.get_doc({
                        "doctype": doctype,
                        name_field: name,
                        "is_group": 1,
                        parent_field: parent if parent else "",
                    }).insert(ignore_permissions=True)
                    _log(f"created {doctype} root {name}")
                    break
                except Exception:  # pragma: no cover - try the next parent value
                    continue
    simple = [
        ("Supplier Group", "supplier_group_name", "All Supplier Groups"),
        ("UOM", "uom_name", "Nos"),
    ]
    for doctype, name_field, name in simple:
        if not frappe.db.exists(doctype, name):
            try:
                frappe.get_doc({"doctype": doctype, name_field: name}).insert(ignore_permissions=True)
                _log(f"created {doctype} {name}")
            except Exception as exc:  # pragma: no cover
                _log(f"WARNING: {doctype} {name} failed: {exc!r}")

    # Non-group child nodes: business records (Customer) cannot be assigned to a
    # GROUP (root) node, so create a leaf under each tree.
    children = [
        ("Customer Group", "customer_group_name", "Commercial", "parent_customer_group", "All Customer Groups"),
        ("Territory", "territory_name", "United States", "parent_territory", "All Territories"),
    ]
    for doctype, name_field, name, parent_field, parent in children:
        if not frappe.db.exists(doctype, name):
            try:
                frappe.get_doc({
                    "doctype": doctype, name_field: name, "is_group": 0, parent_field: parent,
                }).insert(ignore_permissions=True)
                _log(f"created {doctype} leaf {name}")
            except Exception as exc:  # pragma: no cover
                _log(f"WARNING: {doctype} leaf {name} failed: {exc!r}")


def ensure_sample_data(company):
    """A few Customers, Items, a Supplier — realistic data to enumerate/manipulate.
    Each step best-effort (the ERPNext default groups/warehouses must exist, which
    the install + Company setup provide)."""
    customers = ["Acme Corp", "Globex Inc", "Initech LLC"]
    for c in customers:
        try:
            if not frappe.db.exists("Customer", c):
                frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": c,
                    "customer_group": "Commercial",
                    "territory": "United States",
                    "customer_type": "Company",
                }).insert(ignore_permissions=True)
                _log(f"created customer {c}")
        except Exception as exc:  # pragma: no cover
            _log(f"WARNING: customer {c} failed: {exc!r}")

    supplier = "Umbrella Supplies"
    try:
        if not frappe.db.exists("Supplier", supplier):
            frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier,
                "supplier_group": "All Supplier Groups",
            }).insert(ignore_permissions=True)
            _log(f"created supplier {supplier}")
    except Exception as exc:  # pragma: no cover
        _log(f"WARNING: supplier failed: {exc!r}")

    items = [
        ("Widget Pro", "Products"),
        ("Gadget Lite", "Products"),
        ("Service Hours", "Services"),
    ]
    for item_name, group in items:
        try:
            if not frappe.db.exists("Item", item_name):
                frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_name,
                    "item_name": item_name,
                    "item_group": "All Item Groups",
                    "stock_uom": "Nos",
                    "is_stock_item": 1 if group == "Products" else 0,
                    "company": company,
                }).insert(ignore_permissions=True)
                _log(f"created item {item_name}")
        except Exception as exc:  # pragma: no cover
            _log(f"WARNING: item {item_name} failed: {exc!r}")


def run():
    """Entry point invoked by `bench execute seed_erpnext.py:run`."""
    _log("seeding ERPNext demo users + sample data")
    try:
        frappe.flags.in_install = True  # quieten welcome-email / hooks during seed
        # Administrator is the built-in super-user; (re)confirm its password.
        if frappe.db.exists("User", "Administrator"):
            _set_password("Administrator", "admin")
            _log("user Administrator / admin  (built-in super-user)")
        ensure_user("erpadmin@scl.lab",  "erpadmin",  "erpadmin", ["System Manager"])
        ensure_user("accounts@scl.lab",  "accounts",  "accounts", ["Accounts Manager", "Accounts User"])
        ensure_user("salesmgr@scl.lab",  "salesmgr",  "salesmgr", ["Sales Manager", "Sales User"])
        ensure_user("salesuser@scl.lab", "salesuser", "salesuser", ["Sales User"])
        ensure_user("purchase@scl.lab",  "purchase",  "purchase", ["Purchase Manager", "Purchase User"])
        ensure_user("stock@scl.lab",     "stock",     "stock", ["Stock Manager", "Stock User"])
        ensure_user("hr@scl.lab",        "hr",        "hr", ["HR Manager", "HR User"])
        ensure_user("intern@scl.lab",    "intern",    "intern", ["Sales User"])
        viewer = ensure_viewer_role()
        ensure_user("guest@scl.lab",     "guest",     "guest", [viewer])
    finally:
        frappe.flags.in_install = False

    company = ensure_company()
    if company:
        ensure_defaults()
        ensure_sample_data(company)

    try:
        frappe.db.commit()
    except Exception:  # pragma: no cover
        pass
    _log("seed complete")


if __name__ == "__main__":  # allow direct `python seed_erpnext.py` in a bench shell
    run()
