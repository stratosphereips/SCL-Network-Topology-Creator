#!/usr/bin/env python3
"""Seed demo data into the Leosac websock-api (first boot of leosac-server).

Talks the same WebSocket JSON protocol as the Ember UI / leosacpy: envelope
{type, uuid, content}; replies echo the uuid and carry status_code +
content. `create_auth_token {username, password}` marks the connection
authenticated, so subsequent CRUD requests need no token. CRUD messages are
`<resource>.create` with content {attributes: {...}} and `<resource>.read`
with {<resource>_id: 0} for "list all".

Attribute shapes mirror the C++ serializers (src/core/**/serializers/*.cpp):
  user        {username, firstname, lastname, email, password, rank}
              rank: 0 USER / 1 VIEWER / 2 MANAGER / 3 SUPERVISOR / 4 ADMIN
  group       {name, description}
  membership  {group_id, user_id, rank}    rank: 0 MEMBER / 1 OPERATOR / 2 ADMIN
  credential  {credential-type: rfid-card, attributes: {alias, description,
              owner_id, card-id, nb-bits}}
  schedule    {name, description, timeframes: [{start-time, end-time, day}]}
              day 0 = monday; times "H:M"
  door        {alias, description}
  zone        {alias, description, doors: [ids], children: []}
(access_point has no in-tree backend module, so it cannot be created; doors
stand alone.)

`--check` lists object counts for the E2E verification. Every create step is
individually guarded (skip-if-exists + try/except), mirroring seed_erpnext.py.
"""

import asyncio
import json
import sys
import uuid

import websockets

WS_URL = "ws://127.0.0.1:8888/websocket"

# Weak demo users: one per privilege level, password = username (house style).
USERS = [
    # username, firstname, lastname, rank
    ("security", "Sam", "Silva", 2),      # MANAGER
    ("reception", "Rita", "Reyes", 1),    # VIEWER
    ("hr", "Hana", "Rojas", 2),           # MANAGER
    ("maintenance", "Milo", "Mora", 1),   # VIEWER
    ("guard1", "Gus", "Gomez", 0),        # USER
    ("auditor", "Ada", "Aguilar", 3),     # SUPERVISOR
]

GROUPS = [
    ("staff", "Building staff"),
    ("security-team", "Security guards and supervisors"),
    ("visitors", "Escorted visitors"),
]

MEMBERSHIPS = [
    # username, group, rank
    ("security", "security-team", 2),
    ("guard1", "security-team", 0),
    ("auditor", "security-team", 1),
    ("reception", "staff", 0),
    ("hr", "staff", 1),
    ("maintenance", "staff", 0),
]

DOORS = [
    ("main_entrance", "Main building entrance"),
    ("server_room", "Server room (restricted)"),
    ("garage", "Vehicle garage door"),
    ("lab", "Engineering lab"),
]

SCHEDULES = [
    ("business_hours", "Weekdays 08:00-18:00",
     [{"start-time": "8:0", "end-time": "18:0", "day": d} for d in range(5)]),
    ("weekend_off", "Empty schedule (denies on weekends)", []),
]

# RFID card credentials: alias, card number, bit count, owner username.
CREDENTIALS = [
    ("card_security_master", 424242, 32, "security"),
    ("card_guard1", 1001, 26, "guard1"),
    ("card_reception", 1002, 26, "reception"),
    ("card_hr", 1003, 26, "hr"),
    ("card_maintenance", 1004, 26, "maintenance"),
    ("card_auditor", 1005, 26, "auditor"),
    ("badge_contractor_a", 900001, 32, None),   # unassigned (owner-less)
    ("badge_contractor_b", 900002, 32, None),
]

ZONES = [
    ("lobby", "Public lobby (main entrance)", ["main_entrance"]),
    ("restricted", "Restricted wing (server room + lab)", ["server_room", "lab"]),
    ("facility", "Whole facility", ["garage"]),
]


class LeosacClient:
    def __init__(self, ws):
        self.ws = ws
        self.pending = {}

    async def request(self, msg_type, content):
        mid = uuid.uuid4().hex
        await self.ws.send(json.dumps(
            {"type": msg_type, "uuid": mid, "content": content}))
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("uuid") == mid:
                if msg.get("status_code", 0) != 0:
                    raise RuntimeError(
                        f"{msg_type}: transport status "
                        f"{msg.get('status_code')}: {msg.get('status_string')}")
                return msg.get("content") or {}
            # Server-initiated messages (ws-notifier style) — ignore.

    async def crud(self, resource, verb, content):
        return await self.request(f"{resource}.{verb}", content)


async def find_user_id(c, username):
    data = (await c.crud("user", "read", {"user_id": 0})).get("data", [])
    for u in data:
        if u.get("attributes", {}).get("username") == username:
            return u["id"]
    return None


async def find_group_id(c, name):
    data = (await c.crud("group", "read", {"group_id": 0})).get("data", [])
    for g in data:
        if g.get("attributes", {}).get("name") == name:
            return g["id"]
    return None


async def find_by_alias(c, resource, alias):
    data = (await c.crud(resource, "read", {f"{resource}_id": 0})).get("data", [])
    for obj in data:
        if obj.get("attributes", {}).get("alias") == alias:
            return obj["id"]
    return None


async def step(c, label, coro_factory):
    try:
        await coro_factory()
        print(f"seed: {label}: ok")
    except Exception as exc:  # noqa: BLE001 — one failed object must not stop
        print(f"seed: {label}: FAILED ({exc})")


async def seed(c):
    # users
    for username, first, last, rank in USERS:
        async def make_user(u=username, f=first, l=last, r=rank):
            if await find_user_id(c, u) is not None:
                return
            await c.crud("user", "create", {"attributes": {
                "username": u, "firstname": f, "lastname": l,
                "email": f"{u}@scl-lab.local", "password": u, "rank": r}})
        await step(c, f"user {username}", make_user)

    # groups
    for name, description in GROUPS:
        async def make_group(n=name, d=description):
            if await find_group_id(c, n) is not None:
                return
            await c.crud("group", "create", {"attributes": {
                "name": n, "description": d}})
        await step(c, f"group {name}", make_group)

    # memberships
    for username, group, rank in MEMBERSHIPS:
        async def make_membership(u=username, g=group, r=rank):
            uid, gid = await find_user_id(c, u), await find_group_id(c, g)
            if not uid or not gid:
                raise RuntimeError(f"missing user/group for {u}/{g}")
            data = (await c.crud(
                "user-group-membership", "read",
                {"user-group-membership_id": 0})).get("data", [])
            for m in data:
                attrs = m.get("attributes", {})
                if attrs.get("user_id") == uid and attrs.get("group_id") == gid:
                    return
            await c.crud("user-group-membership", "create",
                         {"attributes": {"user_id": uid, "group_id": gid,
                                         "rank": r}})
        await step(c, f"membership {username}@{group}", make_membership)

    # doors
    door_ids = {}
    for alias, description in DOORS:
        async def make_door(a=alias, d=description):
            door_ids[a] = (await find_by_alias(c, "door", a)) or (
                (await c.crud("door", "create", {"attributes": {
                    "alias": a, "description": d}}))["data"]["id"])
        await step(c, f"door {alias}", make_door)

    # schedules
    for name, description, timeframes in SCHEDULES:
        async def make_sched(n=name, d=description, tf=timeframes):
            data = (await c.crud("schedule", "read",
                                 {"schedule_id": 0})).get("data", [])
            if any(s.get("attributes", {}).get("name") == n for s in data):
                return
            await c.crud("schedule", "create", {"attributes": {
                "name": n, "description": d, "timeframes": tf}})
        await step(c, f"schedule {name}", make_sched)

    # credentials (rfid cards)
    for alias, card_id, nb_bits, owner in CREDENTIALS:
        async def make_cred(a=alias, cid=card_id, nb=nb_bits, o=owner):
            if await find_by_alias(c, "credential", a) is not None:
                return
            attrs = {"alias": a,
                     "description": f"Demo RFID card {a}",
                     "card-id": str(cid), "nb-bits": nb,
                     "validity": {"enabled": True}}
            if o:
                attrs["owner_id"] = await find_user_id(c, o)
            await c.crud("credential", "create",
                         {"credential-type": "rfid-card", "attributes": attrs})
        await step(c, f"credential {alias}", make_cred)

    # zones (reference doors created above)
    for alias, description, doors in ZONES:
        async def make_zone(a=alias, d=description, drs=doors):
            if await find_by_alias(c, "zone", a) is not None:
                return
            ids = [door_ids[x] for x in drs if x in door_ids]
            await c.crud("zone", "create", {"attributes": {
                "alias": a, "description": d, "doors": ids, "children": []}})
        await step(c, f"zone {alias}", make_zone)


async def check(c):
    counts = {}
    for resource in ("user", "group", "door", "schedule", "credential", "zone"):
        data = (await c.crud(resource, "read",
                             {f"{resource}_id": 0})).get("data", [])
        counts[resource] = len(data)
    print("check:", json.dumps(counts))
    usernames = [u.get("attributes", {}).get("username")
                 for u in (await c.crud("user", "read",
                                        {"user_id": 0})).get("data", [])]
    print("check: users:", ", ".join(sorted(u for u in usernames if u)))


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
    async with websockets.connect(WS_URL) as ws:
        c = LeosacClient(ws)
        rep = await c.request("create_auth_token",
                              {"username": "admin", "password": "admin"})
        if rep.get("status") != 0:
            print("seed: ERROR: admin/admin authentication failed:", rep)
            return 1
        print(f"seed: authenticated as admin (user_id={rep.get('user_id')})")
        if mode == "--check":
            await check(c)
        else:
            await seed(c)
            await check(c)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
