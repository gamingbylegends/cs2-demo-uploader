#!/usr/bin/env python3
"""
CS2 Demo Uploader
-----------------
Fetches .dem files from one or more Dathost game servers and uploads any new
ones to per-server Google Drive folders. Designed to run on a schedule via
GitHub Actions, but works locally too.

Deduplication is done against the Drive folder itself (the uploader lists the
files it has already put there and skips them), so there is no state file to
maintain and nothing to commit back to the repo.

All configuration comes from environment variables:
  DATHOST_EMAIL          Dathost login email
  DATHOST_PASSWORD       Dathost login password
  GOOGLE_CLIENT_ID       OAuth client ID (Desktop app)
  GOOGLE_CLIENT_SECRET   OAuth client secret
  GOOGLE_REFRESH_TOKEN   OAuth refresh token (see get_token.py)
  SERVERS_CONFIG         JSON array of servers (see servers.example.json)
"""

import json
import os
import sys
import tempfile
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

DATHOST_API = "https://dathost.net/api/0.1"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def env(name):
    """Return a required environment variable or exit with a clear message."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"❌ Missing required environment variable: {name}")
    return value


def load_servers():
    """Parse SERVERS_CONFIG into a list of server dicts."""
    raw = env("SERVERS_CONFIG")
    try:
        servers = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"❌ SERVERS_CONFIG is not valid JSON: {exc}")
    if not isinstance(servers, list) or not servers:
        sys.exit("❌ SERVERS_CONFIG must be a non-empty JSON array.")
    return servers


def drive_service():
    """Build an authenticated Google Drive client from the refresh token."""
    creds = Credentials(
        token=None,
        refresh_token=env("GOOGLE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env("GOOGLE_CLIENT_ID"),
        client_secret=env("GOOGLE_CLIENT_SECRET"),
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_demos(auth, server_id, demo_path=""):
    """Return a list of .dem file paths on a Dathost server."""
    params = {}
    if demo_path:
        params["path"] = demo_path
    resp = requests.get(
        f"{DATHOST_API}/game-servers/{server_id}/files",
        auth=auth,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()

    demos = []
    for item in resp.json():
        path = item.get("path") or item.get("name")
        if not path:
            continue
        # Skip directories (field name varies across API responses).
        if item.get("directory") or item.get("is_dir"):
            continue
        if path.lower().endswith(".dem"):
            demos.append(path)
    return demos


def existing_drive_files(service, folder_id):
    """Return the set of file names already present in a Drive folder."""
    names = set()
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        for file in resp.get("files", []):
            names.add(file["name"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return names


def download_demo(auth, server_id, path, dest):
    """Stream a demo file from Dathost to a local path."""
    url = f"{DATHOST_API}/game-servers/{server_id}/files/{quote(path, safe='/')}"
    with requests.get(url, auth=auth, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def upload_to_drive(service, folder_id, name, local_path):
    """Upload a local file into a Drive folder and return its file ID."""
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(
        body={"name": name, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    return file.get("id")


def process_server(auth, service, srv):
    """Handle a single server entry. Returns the number of demos uploaded."""
    name = srv.get("name", "unnamed")
    server_id = srv.get("server_id")
    folder_id = srv.get("drive_folder_id")
    demo_path = srv.get("demo_path", "")

    print(f"🖥️  {name} ({server_id})")
    if not server_id or not folder_id:
        print("   ⚠️  Skipping — missing server_id or drive_folder_id.\n")
        return 0
    print(f"   Drive folder: {folder_id}")

    try:
        demos = list_demos(auth, server_id, demo_path)
    except requests.HTTPError as exc:
        print(f"   ❌ Could not list files on Dathost: {exc}\n")
        return 0

    try:
        already = existing_drive_files(service, folder_id)
    except Exception as exc:  # noqa: BLE001 - report and continue to next server
        print(f"   ❌ Could not read Drive folder: {exc}\n")
        return 0

    new_demos = [d for d in demos if os.path.basename(d) not in already]
    print(f"   📋 {len(new_demos)} new demo(s) (of {len(demos)} total)")

    uploaded = 0
    for path in new_demos:
        filename = os.path.basename(path)
        tmp_path = None
        try:
            print(f"      ⬇️  Downloading {filename} ...")
            with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as tmp:
                tmp_path = tmp.name
            download_demo(auth, server_id, path, tmp_path)

            print(f"      ☁️  Uploading {filename} to Google Drive ...")
            file_id = upload_to_drive(service, folder_id, filename, tmp_path)
            print(f"      ✅ Uploaded! (ID: {file_id})")
            uploaded += 1
        except Exception as exc:  # noqa: BLE001 - one bad demo shouldn't stop the rest
            print(f"      ❌ Error on {filename}: {exc}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    if not new_demos:
        print("   ✨ No new demos.")
    print()
    return uploaded


def main():
    auth = HTTPBasicAuth(env("DATHOST_EMAIL"), env("DATHOST_PASSWORD"))
    service = drive_service()
    servers = load_servers()

    print("🎮 CS2 Demo Uploader starting...")
    print(f"   Processing {len(servers)} server(s)\n")

    total = sum(process_server(auth, service, srv) for srv in servers)

    print(f"🏁 Done! {total} demo(s) uploaded in total.")


if __name__ == "__main__":
    main()
