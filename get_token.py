#!/usr/bin/env python3
"""
One-time helper: generate a Google OAuth2 refresh token for the uploader.
-------------------------------------------------------------------------
Run this on your own machine (it opens a browser). Paste the printed token
into the GOOGLE_REFRESH_TOKEN GitHub secret.

    pip install google-auth-oauthlib
    python get_token.py

IMPORTANT:
  * The OAuth consent screen must be set to "In production" first, otherwise
    the token Google gives you will expire after 7 days. See the README.
  * SCOPES below must match the scope the uploader uses.
  * Sign in with the Google account that owns the target Drive folders.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

# Must match the scope used by upload_demos.py.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# From Google Cloud Console -> Clients -> your OAuth "Desktop" client.
CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

print("\n" + "=" * 60)
print("YOUR NEW REFRESH TOKEN:")
print(creds.refresh_token)
print("=" * 60)
print("\nPaste this into the GOOGLE_REFRESH_TOKEN secret in your GitHub repo.")
