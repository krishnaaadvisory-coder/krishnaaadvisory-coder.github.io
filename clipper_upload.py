#!/usr/bin/env python3
"""Clipper: the complete YouTube upload script used by the Clipper tool.

Uploads one vertical clip to the owner's own channel with the YouTube Data API
(videos.insert, resumable upload). Scope: youtube.upload only.

  python3 clipper_upload.py auth                      # one-time Google sign-in
  python3 clipper_upload.py upload clip.mp4 "Title" "Description"

Credentials come from environment variables (never hard-coded):
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET   (OAuth "Desktop app" client)
The refresh token is stored in ./tokens.json with owner-only permissions.
"""
import json
import os
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKENS = Path(__file__).with_name("tokens.json")
CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")


def auth():
    """Installed-app OAuth flow with a loopback redirect."""
    port, state = 8765, secrets.token_urlsafe(16)
    redirect = f"http://127.0.0.1:{port}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state})
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            got.update({k: v[0] for k, v in urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query).items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Connected. You can close this tab.")

        def log_message(self, *a):
            pass

    print("Open this link and sign in with the channel's Google account:\n\n" + url + "\n")
    server = HTTPServer(("127.0.0.1", port), Handler)
    while "code" not in got and "error" not in got:
        server.handle_request()
    if got.get("state") != state or "code" not in got:
        sys.exit(f"Sign-in failed: {got}")
    tok = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "code": got["code"], "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "redirect_uri": redirect, "grant_type": "authorization_code"}).json()
    TOKENS.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    TOKENS.chmod(0o600)
    print("Connected.")


def access_token():
    rt = json.loads(TOKENS.read_text())["refresh_token"]
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": rt, "grant_type": "refresh_token"}).json()
    if "access_token" not in r:
        sys.exit(f"Token refresh failed (access revoked?): {r}")
    return r["access_token"]


def upload(path, title, description):
    """videos.insert, resumable upload. Returns the new video id."""
    tok = access_token()
    if "#shorts" not in title.lower():
        title = title[:90] + " #shorts"
    meta = {"snippet": {"title": title[:100], "description": description[:4900], "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    size = Path(path).stat().st_size
    start = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    start.raise_for_status()
    with open(path, "rb") as f:
        done = requests.put(start.headers["Location"], data=f, timeout=1800,
                            headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4"})
    done.raise_for_status()
    vid = done.json()["id"]
    print(f"Uploaded: https://www.youtube.com/shorts/{vid}")
    return vid


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        sys.exit("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET.")
    if sys.argv[1:2] == ["auth"]:
        auth()
    elif sys.argv[1:2] == ["upload"] and len(sys.argv) == 5:
        upload(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
