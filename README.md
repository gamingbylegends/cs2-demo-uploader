# CS2 Demo Uploader → Google Drive

Automatically pull `.dem` files from your [Dathost](https://dathost.net) CS2
servers and archive them in Google Drive — one folder per server — on a
schedule, for free, using GitHub Actions.

No server to run, no database, no local machine that has to stay on. GitHub
runs the job every 10 minutes; new demos land in Drive within minutes of a
match ending.

- ✅ Multiple servers, each with its own Drive folder
- ✅ Skips demos it has already uploaded (no duplicates)
- ✅ All credentials kept in GitHub Secrets, never in the code
- ✅ A one-click **status check** that shows which servers are online and
  whether every server is covered by the uploader

---

## How it works

```
Dathost servers ──(Dathost API)──► GitHub Actions runner ──(Drive API)──► Google Drive
                                     runs upload_demos.py                 one folder / server
```

Every 10 minutes, `upload_demos.py`:

1. Reads your list of servers from the `SERVERS_CONFIG` secret.
2. For each server, lists the `.dem` files via the Dathost API.
3. Lists the files it has already put in that server's Drive folder and skips
   those — so only genuinely new demos are transferred.
4. Downloads each new demo from Dathost and uploads it to Drive.

Deduplication is done against Drive itself, so there is no state file to keep
in sync and nothing gets committed back to the repo.

---

## What you need

- A **Dathost account** with one or more CS2 servers.
- A **Google account** where the demos will be stored.
- A **GitHub account**. A private repo is fine. Scheduled Actions are free on
  public repos and included in the monthly free minutes on private repos.
- **Python 3** on your own computer for a single one-time step (generating the
  Google token).

---

## Setup

There are four parts: Google, the token, your server list, and GitHub. Take
them in order — the [pitfalls](#pitfalls-read-this) below explain *why* a
couple of the steps matter, so skimming that section first will save you time.

### 1. Google Cloud: project, API, and OAuth client

1. Go to the [Google Cloud Console](https://console.cloud.google.com) and
   create a new project (top-left project picker → **New project**).
2. Enable the Drive API: **APIs & Services → Library → Google Drive API →
   Enable**.
3. Configure the consent screen: **APIs & Services → OAuth consent screen** (in
   newer consoles this lives under **Google Auth Platform → Audience**).
   - User type: **External**.
   - Fill in the required app name and support email.
4. **Publish the app.** On the Audience/consent screen, set **Publishing
   status** to **In production** (click **Publish app**). This is the single
   most important step — see [pitfalls](#pitfalls-read-this). You do **not**
   need Google verification while you are the only user.
5. Create the credential: **APIs & Services → Credentials → Create
   credentials → OAuth client ID → Application type: Desktop app**. Copy the
   **Client ID** and **Client secret** — you'll need them next.

### 2. Generate a refresh token

The uploader authenticates to Drive with a long-lived *refresh token*. Generate
one once, locally:

```bash
pip install google-auth-oauthlib
```

Open `get_token.py`, paste your **Client ID** and **Client secret** into the two
variables at the top, then run:

```bash
python get_token.py
```

A browser opens. Sign in with the Google account that owns the target Drive
folders and approve the access. If you see *"Google hasn't verified this app"*,
click **Advanced → Go to … (unsafe)** — that warning is expected for your own
unverified app. The terminal then prints your **refresh token**. Keep it handy
for step 4.

### 3. Create your Drive folders and build the server list

1. In Google Drive, create one folder per server. Open each folder and copy the
   **folder ID** from the URL — it's the part after `/folders/`:
   `https://drive.google.com/drive/folders/`**`THIS_IS_THE_ID`**.
2. Get each server's **Dathost server ID**. You can read it from the control
   panel URL, or just run the status check (step 5) once it's set up — it lists
   every server with its ID.
3. Build a JSON array like `servers.example.json`:

   ```json
   [
     {
       "name": "Main Server",
       "server_id": "your-dathost-server-id",
       "drive_folder_id": "your-drive-folder-id"
     }
   ]
   ```

   `name` is only for readable logs. Add an optional `"demo_path"` per server if
   your demos live in a subfolder rather than the server's root (see
   [pitfalls](#pitfalls-read-this)). This whole JSON becomes one secret — keep
   it on a single line or multi-line, both work.

### 4. Add the GitHub secrets

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add all six:

| Secret name            | Value                                             |
|------------------------|---------------------------------------------------|
| `DATHOST_EMAIL`        | Your Dathost login email                          |
| `DATHOST_PASSWORD`     | Your Dathost login password                       |
| `GOOGLE_CLIENT_ID`     | OAuth client ID from step 1                        |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret from step 1                    |
| `GOOGLE_REFRESH_TOKEN` | The token printed in step 2                        |
| `SERVERS_CONFIG`       | The JSON array from step 3                          |

### 5. Turn it on

Push this repo to GitHub (or use it as a template). Go to the **Actions** tab
and enable workflows if prompted. The uploader then runs automatically every 10
minutes.

To test immediately instead of waiting: **Actions → Upload CS2 Demos to Google
Drive → Run workflow**. Expand the **Upload new demos to Google Drive** step and
you should see `✅ Uploaded!` lines and a final `🏁 Done!` count.

---

## Checking server status and coverage

Want to confirm all your servers are online *and* that none are silently
missing from the uploader? Run the second workflow: **Actions → Check CS2
Server Status → Run workflow**.

It lists every server on your Dathost account and marks each one:

```
🟢 ON   ✅ covered     Main Server  [cs2]  (abc123...)
🔴 OFF  ✅ covered     Scrim Server [cs2]  (def456...)
🟢 ON   ❌ not covered  New Server   [cs2]  (ghi789...)
```

Anything `❌ not covered` (and running CS2) is **not** being uploaded — add its
ID to `SERVERS_CONFIG`. Non-CS2 servers also show `❌`; ignore those.

---

## Adding (or removing) servers later

You are **not** locked into the servers you start with. The uploader reads
`SERVERS_CONFIG` fresh on every run, so adding a server is just editing that one
secret — **no code changes, no redeploy, and nothing else to touch.** The token
and all other secrets stay exactly as they are.

To add a server:

1. **Create a Drive folder** for it and copy the folder ID from the URL
   (`.../folders/`**`THIS_ID`**).
2. **Find its Dathost server ID.** Easiest way: run **Actions → Check CS2 Server
   Status → Run workflow**. Every server on your account is listed with its ID,
   and the new one will show up as `❌ not covered` — copy that ID.
3. **Add an entry** to your `SERVERS_CONFIG` JSON. For example, going from one
   server to two:

   ```json
   [
     {
       "name": "Main Server",
       "server_id": "existing-server-id",
       "drive_folder_id": "existing-folder-id"
     },
     {
       "name": "Scrim Server",
       "server_id": "new-server-id",
       "drive_folder_id": "new-folder-id"
     }
   ]
   ```

   You can add several at once — just append more objects to the array. Add
   `"demo_path"` to an entry only if that server keeps its demos in a subfolder.
4. **Update the secret:** **Settings → Secrets and variables → Actions →
   `SERVERS_CONFIG` → Update secret** → paste the new JSON.
5. **Done.** The next scheduled run picks it up automatically (or trigger the
   uploader manually to start immediately). Re-run the status check to confirm
   the new server now shows `✅ covered`.

To **remove** a server, delete its object from `SERVERS_CONFIG` and update the
secret. Demos already archived in Drive are left untouched — removing a server
just stops future uploads from it.

> Tip: keep a master copy of your `SERVERS_CONFIG` JSON somewhere safe (a
> password manager or private note). GitHub hides a secret's value once saved,
> so you can't read it back to edit it — you always paste a fresh full value.

---

## Pitfalls (read this)

These are the two things that trip everyone up. Both produce confusing
symptoms, so they're worth understanding up front.

### 1. An OAuth app in "Testing" kills your refresh token after 7 days

If your consent screen is left in **Testing**, Google expires refresh tokens
for that app after **7 days**. Everything works for a week, then uploads start
failing with `invalid_grant: Bad Request` — and, crucially, **GitHub Actions
still shows the run as green**, because the script catches the error per-demo
and finishes "successfully" while uploading nothing.

**Fix:** set the consent screen to **In production**. As the sole user of your
own app you don't need Google verification. After switching, tokens no longer
expire.

### 2. Rotating the client secret means updating two secrets, not one

A refresh token is bound to the exact **client ID + client secret** it was
created with. Newer Google consoles also **no longer let you view a client
secret after creation** — you can only add a new one. So if you ever create a
fresh secret, you must update **both** `GOOGLE_CLIENT_SECRET` **and**
`GOOGLE_REFRESH_TOKEN` in GitHub, and regenerate the token against the new
secret. Updating only one of them gives you `invalid_grant` again.

### Also worth knowing

- **GitHub disables scheduled workflows after 60 days of repo inactivity.** If
  nothing is committed for two months, your cron job quietly stops. A single
  commit re-enables it; or open the workflow and it'll offer to re-enable.
- **`drive.file` scope** means the app can only see files *it* created. That's
  exactly why dedup works, and it's the least-privilege scope for this job — the
  app never gets access to the rest of your Drive.
- **Demo location.** Most CS2 setups store demos at the server's file-manager
  root, which is the default. If yours are in a subfolder, set `"demo_path"` for
  that server in `SERVERS_CONFIG`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Run is green but 0 demos in Drive; log shows `invalid_grant` | Refresh token expired (app in Testing) or client secret/token mismatch | Set app to In production, regenerate the token, update `GOOGLE_REFRESH_TOKEN` (and `GOOGLE_CLIENT_SECRET` if you rotated it) |
| `invalid_client` / `unauthorized_client` | Wrong `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, or they point at a different Google project | Copy them again from the correct project's OAuth client |
| `📋 0 new demo(s) (of 0 total)` for a server that has demos | Demos are in a subfolder | Set `"demo_path"` for that server |
| Uploads go somewhere unexpected | Wrong `drive_folder_id` | Recopy the folder ID from the Drive URL |
| Scheduled runs stopped happening | 60-day inactivity disable | Commit anything, or re-enable in the Actions tab |
| `401 Unauthorized` from Dathost | Wrong `DATHOST_EMAIL` / `DATHOST_PASSWORD` | Recheck the secrets |

---

## Security notes

- **Never commit secrets.** Everything sensitive lives in GitHub Secrets. The
  included `.gitignore` blocks `.env`, `servers.json`, and credential files if
  you experiment locally.
- The Dathost password used here is your account password. Treat the repo's
  secret settings accordingly, and prefer a private repo if that matters to you.
- `drive.file` is a deliberately narrow scope; this app cannot read or touch
  files it didn't upload.

---

## License

MIT — see [LICENSE](LICENSE). Do what you like with it.
