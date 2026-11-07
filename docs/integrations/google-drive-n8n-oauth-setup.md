# Google Drive OAuth2 Setup Guide for DocAnalyser + n8n

This guide walks you through configuring Google Drive OAuth2 credentials so that
the n8n automation workflow can monitor a Google Drive folder and automatically
ingest new documents into the DocAnalyser Hybrid RAG Platform.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| A Google account | The same account that owns the Drive folder to monitor |
| A running n8n instance | Local (`http://localhost:5678`) or cloud-hosted (Fly.io / Railway) |
| `N8N_ENCRYPTION_KEY` set | Must be set **before** first run; changing it later invalidates stored credentials |
| Spring Boot backend reachable from n8n | Either via Docker Compose internal DNS or a public HTTPS URL |

---

## Step 1 — Open Google Cloud Console

Go to [https://console.cloud.google.com](https://console.cloud.google.com) and
sign in with the Google account you want to use for Drive integration.

---

## Step 2 — Create or Select a Google Cloud Project

1. Click the project drop-down at the top of the page.
2. Click **New Project** (or select an existing project).
3. Give it a name such as `docanalyser-drive` and click **Create**.
4. Make sure the new project is selected before proceeding.

---

## Step 3 — Enable the Google Drive API

1. Navigate to **APIs & Services → Library**.
2. Search for **Google Drive API**.
3. Click the result, then click **Enable**.

---

## Step 4 — Configure the OAuth Consent Screen

1. Navigate to **APIs & Services → OAuth consent screen**.
2. Select **External** (allows any Google account to authorize in production;
   required for personal accounts).
3. Click **Create**.
4. Fill in the required fields:
   - **App name**: `DocAnalyser`
   - **User support email**: your email address
   - **Developer contact information**: your email address
5. Click **Save and Continue**.

### Add Scopes

1. On the **Scopes** step, click **Add or Remove Scopes**.
2. In the filter box, search for `drive`.
3. Select **`https://www.googleapis.com/auth/drive.readonly`** — this is the
   minimum scope needed to list, watch, and download Drive files.
4. Click **Update**, then **Save and Continue**.

### Add Test Users (required while in Testing mode)

> **Important**: While the OAuth consent screen is in **Testing** mode, only
> explicitly listed test users can authorize the application. You **must** add
> your own Google account as a test user, otherwise authorization will fail.

1. On the **Test users** step, click **Add Users**.
2. Enter your Google email address and click **Add**.
3. Click **Save and Continue**, then **Back to Dashboard**.

---

## Step 5 — Create OAuth 2.0 Client Credentials

1. Navigate to **APIs & Services → Credentials**.
2. Click **Create Credentials → OAuth 2.0 Client ID**.
3. For **Application type**, select **Web application**.
4. Give it a name, e.g. `DocAnalyser n8n Client`.

### Add the n8n Redirect URI

You need to get the exact callback URL from your running n8n instance **before**
creating the credential.

**How to get the redirect URI from n8n:**
1. Open your n8n instance (e.g. `http://localhost:5678`).
2. Go to **Settings → Credentials → Add Credential → Google Drive OAuth2 API**.
3. n8n will display the **OAuth Redirect URL** at the top of the credential
   form. It looks like:
   - Local: `http://localhost:5678/rest/oauth2-credential/callback`
   - Cloud: `https://your-n8n-domain.com/rest/oauth2-credential/callback`
4. Copy that exact URL.

**Back in Google Cloud Console:**
1. Under **Authorized redirect URIs**, click **Add URI**.
2. Paste the exact redirect URI from n8n.
3. Click **Create**.

> ⚠️ **Never guess or invent the redirect URI.** Google will reject any
> authorization request that uses a URI not listed here.

---

## Step 6 — Copy Client ID and Secret into n8n

After clicking **Create**, Google will display your **Client ID** and
**Client Secret**.

1. Copy the **Client ID**.
2. Copy the **Client Secret**.
3. Keep this window open or download the JSON — you will need both values.

In n8n:
1. Go to **Settings → Credentials → Add Credential → Google Drive OAuth2 API**.
2. Paste the **Client ID** and **Client Secret** into the corresponding fields.
3. Click **Sign in with Google** — a browser window will open.
4. Select the Google account you added as a test user.
5. Grant the requested permissions.
6. n8n will redirect back and display **"Account connected"**.
7. Save the credential with a name like `Google Drive DocAnalyser`.

---

## Step 7 — Get Your Target Google Drive Folder ID

1. Open [Google Drive](https://drive.google.com) in your browser.
2. Navigate to (or create) the folder you want to monitor for new documents.
3. The folder ID is in the URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```
   Copy the `FOLDER_ID_HERE` portion.

---

## Step 8 — Configure n8n Environment Variables

Set these environment variables in your n8n deployment **before** importing the
workflow:

| Variable | Description | Example |
|---|---|---|
| `N8N_INGESTION_TOKEN` | Shared secret matching Spring Boot's `app.internal.api-token` | `openssl rand -hex 32` output |
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID to monitor | `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs` |
| `SPRING_BOOT_URL` | Base URL of Spring Boot backend | `https://docanalyser-backend.onrender.com` or `http://backend:8080` |
| `N8N_ENCRYPTION_KEY` | 32+ character key for credential encryption (set once, never change) | `openssl rand -hex 32` output |
| `N8N_HOST` | Public hostname of n8n instance | `n8n.yourdomain.com` |
| `N8N_PROTOCOL` | `https` for production, `http` for local | `https` |

**Generate secure random tokens:**
```bash
# On Linux/macOS:
openssl rand -hex 32

# On Windows (PowerShell):
[System.Web.HttpUtility]::UrlEncode([System.Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 } | ForEach-Object { [byte]$_ })))
```

> ⚠️ **Never commit these values to version control.**  
> Use `.env` files (gitignored), Render Dashboard secrets, or Fly.io secrets.

---

## Step 9 — Import the Workflow into n8n

1. In n8n, go to **Workflows → Import from File**.
2. Select `infrastructure/n8n/google_drive_ingestion_workflow.json`.
3. After import, open the workflow.
4. Click the **Google Drive Trigger** node and set:
   - **Credential**: select the credential you created in Step 6.
   - **Folder**: enter the folder ID from Step 7, or use `{{ $env.GOOGLE_DRIVE_FOLDER_ID }}`.
5. Click the **Download Drive File** node and verify the same credential is selected.
6. Save the workflow.

---

## Step 10 — Activate and Test the Workflow

1. Click the **Active** toggle in the top-right of the workflow editor to activate it.
2. Upload a test PDF file to your Google Drive folder.
3. Within 1–2 minutes (polling interval), n8n should trigger the workflow.
4. Check the **Execution Log** in n8n to verify all nodes completed successfully.
5. Open DocAnalyser and confirm the document appears in the document list.
6. Ask a question about the document in the chat interface.

### Manual Test (without waiting for the trigger)

You can test immediately using the **Manual / Test Webhook Trigger** node:

1. In the n8n workflow editor, click **Execute Workflow**.
2. The **Manual** trigger fires. Because no actual Drive file data is present,
   the validation node will reject it — this confirms the validation logic works.
3. To do a full end-to-end manual test, temporarily switch to the
   **HTTP Request** node and send a test payload directly.

---

## Step 11 — Supported File Types and Size Limits

The workflow validates files before sending to Spring Boot:

| Format | MIME Type | Supported |
|---|---|---|
| PDF | `application/pdf` | ✅ |
| Plain Text | `text/plain` | ✅ |
| Markdown | `text/markdown` | ✅ |
| Word (DOCX) | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | ❌ |
| Excel | `application/vnd.ms-excel` | ❌ |
| Images | `image/*` | ❌ |

**Maximum file size:** 50 MB (configurable in the workflow's `Validate Format & Size` node).

---

## Troubleshooting

### "redirect_uri_mismatch" error
The redirect URI in Google Cloud Console does not exactly match what n8n sends.
Get the exact URI from n8n (Step 5 → "How to get the redirect URI from n8n"),
update it in Google Cloud Console under **Credentials → Your OAuth Client →
Authorized redirect URIs**.

### "Access blocked: This app's request is invalid"
The OAuth consent screen is in Testing mode and your Google account is not in
the **Test users** list. Add it (Step 4 → "Add Test Users").

### n8n trigger not firing
- Confirm the workflow is **Active** (toggle in the editor).
- The trigger polls every minute. Wait up to 2 minutes after uploading a file.
- Check that the folder ID is correct and the credential has access to that folder.
- Verify the Google Drive API is enabled in Google Cloud Console.

### "401 Unauthorized" from Spring Boot
- `N8N_INGESTION_TOKEN` in n8n does not match `app.internal.api-token` in Spring Boot.
- Verify both values are identical and that Spring Boot restarted after the change.

### File too large / format rejected
The validation node rejects files > 50 MB or with unsupported MIME types.
Check the n8n execution log for the `Validate Format & Size` node output.

### Document not appearing in DocAnalyser after n8n reports success
- Check Spring Boot logs for ingestion errors.
- Check the FastAPI RAG service logs for pipeline errors.
- Verify Qdrant is reachable from the RAG service.

---

## Security Notes

1. **`N8N_INGESTION_TOKEN`** is a shared secret between n8n and Spring Boot.
   Use `openssl rand -hex 32` to generate a strong value. Never use the default
   `docanalyser-n8n-internal-token-secret` value in production.

2. **`N8N_ENCRYPTION_KEY`** is used by n8n to encrypt all stored credentials
   (including your Google OAuth tokens). Set it once before the first run and
   **never change it** — doing so will permanently invalidate all stored
   credentials and require re-authorization of every credential.

3. **Google OAuth tokens** are stored encrypted in n8n's SQLite database (or
   external database if configured). Do not expose the n8n data directory.

4. Use **`drive.readonly`** scope only — DocAnalyser never writes to Google
   Drive.

5. Keep the OAuth consent screen in **Testing** mode until you are ready to
   submit for Google verification. In testing mode, tokens expire after 7 days
   and must be re-authorized. In production mode (after verification), tokens
   auto-refresh.

---

## n8n Deployment Options (for Production)

### Option A: Render (Recommended — Included in Blueprint)
n8n is configured directly in `render.yaml` as the `docanalyser-n8n` web service backed by Render PostgreSQL (`docanalyser-postgres`).

Because n8n uses PostgreSQL for credential, workflow, and execution storage instead of local SQLite files, **no persistent disk is required**, making it 100% compatible with Render's Free tier.

1. Push your latest code containing `render.yaml` to GitHub.
2. In the Render Dashboard, open your Blueprint / Environment.
3. Render automatically provisions the `docanalyser-n8n` service at:
   `https://docanalyser-n8n.onrender.com`
4. Set the `N8N_INGESTION_TOKEN` environment variable in the Render Dashboard (matching Spring Boot's token).
5. Render automatically generates and persists `N8N_ENCRYPTION_KEY`.

### Option B: Fly.io
```bash
# Install Fly CLI
# https://fly.io/docs/hands-on/install-flyctl/

fly launch --name docanalyser-n8n --image n8nio/n8n --region ord
fly volumes create n8n_data --size 1 --region ord
fly secrets set N8N_ENCRYPTION_KEY="$(openssl rand -hex 32)"
fly secrets set N8N_INGESTION_TOKEN="your-token-here"
fly secrets set SPRING_BOOT_URL="https://docanalyser-backend.onrender.com"
fly secrets set GOOGLE_DRIVE_FOLDER_ID="your-folder-id"
fly deploy
```

Configure the volume mount in `fly.toml`:
```toml
[mounts]
  source = "n8n_data"
  destination = "/home/node/.n8n"
```

### Option C: Railway
1. Create a new project on [Railway](https://railway.app).
2. Add a service from the Docker image `n8nio/n8n`.
3. Add a persistent volume mounted at `/home/node/.n8n`.
4. Set the same environment variables listed above.

### Option D: Local Docker Compose (Development Only)
The `infrastructure/docker-compose.yml` already includes an n8n service.
Run:
```bash
cd infrastructure
docker compose up -d n8n
```
n8n will be available at `http://localhost:5678`.

> **Note**: Local n8n cannot receive Google OAuth2 callbacks unless you expose
> it via a tool like [ngrok](https://ngrok.com/) and add the ngrok HTTPS URL as
> an authorized redirect URI in Google Cloud Console.

---

## Related Files

| File | Description |
|---|---|
| `infrastructure/n8n/google_drive_ingestion_workflow.json` | The n8n workflow to import |
| `infrastructure/docker-compose.yml` | Local development environment with n8n |
| `docs/integrations/google-drive-n8n.md` | Architecture and API reference |
| `backend/.../controller/IngestionController.java` | Spring Boot ingestion endpoint |
| `backend/.../service/RagServiceClient.java` | File transfer to FastAPI RAG service |

