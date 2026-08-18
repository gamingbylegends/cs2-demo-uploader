#!/usr/bin/env python3
"""
Check CS2 server status and uploader coverage.
-----------------------------------------------
Lists every server on the Dathost account and shows, for each one:
  * whether it is currently online, and
  * whether it is covered by the uploader (present in SERVERS_CONFIG).

Any server marked ❌ is NOT being uploaded — add it to SERVERS_CONFIG to fix.
Non-CS2 servers will also show ❌; ignore those (see the [game] column).

Environment variables:
  DATHOST_EMAIL     Dathost login email
  DATHOST_PASSWORD  Dathost login password
  SERVERS_CONFIG    (optional) uploader config, used only for the coverage column
"""

import json
import os
import sys

import requests
from requests.auth import HTTPBasicAuth

DATHOST_API = "https://dathost.net/api/0.1"


def env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"❌ Missing required environment variable: {name}")
    return value


def covered_ids():
    """Return the set of server IDs the uploader is configured to handle."""
    raw = os.environ.get("SERVERS_CONFIG", "").strip()
    if not raw:
        return set()
    try:
        servers = json.loads(raw)
        return {s.get("server_id") for s in servers if s.get("server_id")}
    except json.JSONDecodeError:
        print("⚠️  SERVERS_CONFIG is not valid JSON — coverage column disabled.\n")
        return set()


def main():
    auth = HTTPBasicAuth(env("DATHOST_EMAIL"), env("DATHOST_PASSWORD"))
    covered = covered_ids()

    resp = requests.get(f"{DATHOST_API}/game-servers", auth=auth, timeout=30)
    resp.raise_for_status()
    servers = resp.json()

    print(f"🖥️  Found {len(servers)} server(s) on the Dathost account:\n")

    not_covered = []
    for srv in servers:
        sid = srv.get("id")
        name = srv.get("name", "?")
        game = srv.get("game", "?")
        online = "🟢 ON " if srv.get("on") else "🔴 OFF"
        mark = "✅ covered   " if sid in covered else "❌ not covered"
        if covered and sid not in covered:
            not_covered.append((name, game, sid))
        print(f"   {online}  {mark}  {name}  [{game}]  ({sid})")

    if covered:
        print()
        if not_covered:
            print(f"⚠️  {len(not_covered)} server(s) NOT covered by the uploader:")
            for name, game, sid in not_covered:
                print(f"   - {name} [{game}] ({sid})")
        else:
            print("🎉 Every server on the account is covered by the uploader.")


if __name__ == "__main__":
    main()
