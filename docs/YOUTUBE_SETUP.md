# YouTube Data API v3
1. console.cloud.google.com → new project → enable **YouTube Data API v3**.
2. OAuth consent screen (External, add yourself as a test user) → Credentials → OAuth client ID → **Web application**, redirect URI `http://localhost:8000/api/youtube/oauth/callback` (or your domain).
3. Download the JSON to a path outside git, set `YOUTUBE_CLIENT_SECRETS=/path/client_secret.json` and `YOUTUBE_REDIRECT_URI`.
4. Dashboard → YouTube → *Connect*. The token is stored with 0600 permissions in `storage/youtube_token.json` (gitignored).
Notes: unverified API projects upload as **private only** until Google audits the project; that matches this app's default. Quota: an upload costs ~1600 units of the 10,000/day default. Videos are flagged `containsSyntheticMedia`. Shorts (9:16) have a Remotion `Short` composition but no automated 60-second cut-down pipeline yet.
