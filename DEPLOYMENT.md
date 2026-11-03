# Deploying Urimai

Both services are in `compose.yml` (`server/Dockerfile`, `bot/Dockerfile`). The bot uses Telegram **long polling**, so nothing needs an inbound webhook or a public URL for the bot. The server only needs to be reachable *from the bot* — it has no authentication, so **don't give it a public route** unless you add one.

## Prerequisites

- A `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY` (see [.env.example](.env.example))
- Optional: a MongoDB Atlas cluster for the scheme catalogue and vector search (`MONGODB_URI`). Without it, the server uses the bundled JSON seed and an in-memory retrieval backend — fine for a demo, fine for low traffic, but catalogue edits need a redeploy instead of a database update.
- Docker + Docker Compose on whatever you deploy to

### `.env` gotchas that only show up under Docker

`app/core/config.py` reads `.env` with `python-dotenv`, which tolerates both of these — but Docker's `--env-file` (and `compose.yml`'s `env_file:`, same parser) does not, so a `.env` that works fine when you run the server directly with `uvicorn` can crash the container on boot:

- **Inline `# comments` after a value** (`RETRIEVAL_TIMEOUT_S=8   # seconds...`) become part of the value itself. The server then fails to start with `ValueError: could not convert string to float:
  "8           # seconds..."`. Put comments on their own line above the variable instead.
- **Quoted values** (`MONGODB_URI="mongodb+srv://..."`) keep the literal quote characters — common if you pasted a connection string straight from Atlas's UI, which quotes it for you. pymongo then rejects it with `InvalidURI: URI must begin with 'mongodb://'`. Remove the quotes.

`.env.example` has neither problem; this only bites if you hand-edit your own `.env` afterward. Before
`docker compose up`, a quick sanity check:

```bash
grep -nE '^[A-Z_]+=.*#' .env   # should print nothing
grep -n '="' .env              # should print nothing
```

## Option A — a single VM (simplest, recommended for a hackathon demo)

Any always-on VM works (Oracle Cloud's free tier, a $5 DigitalOcean/Lightsail droplet, a GCP/AWS free-tier instance, …). Both containers run on it; `server` is never exposed to the internet.

```bash
# on the VM
git clone https://github.com/Balaji-R-05/urimai.git
cd urimai
cp .env.example .env
nano .env                       # fill in TELEGRAM_BOT_TOKEN, GROQ_API_KEY, MONGODB_URI if using Atlas
docker compose up --build -d
docker compose logs -f          # watch both services start; Ctrl+C to stop watching (containers keep running)
```

- Don't open port 8000 in the VM's firewall/security group — `compose.yml` only needs it for your own `curl http://localhost:8000/api/health` from inside the VM. The bot reaches the server over the compose network at `http://server:8000` regardless of whether the port is published.
- **Updating:** `git pull && docker compose up --build -d`. The named volumes (`models`, `server_logs`, `bot_logs`) survive this — only `docker compose down -v` deletes them.
- **Restart on reboot:** both services already have `restart: unless-stopped`; also enable Docker's own service (`sudo systemctl enable docker`) so containers come back after a VM reboot.
- **Logs:** `docker compose logs -f server` / `bot`, or read the rotating files inside the volumes: `docker compose exec server cat logs/feedback.log`.

## Option B — managed container platforms (Railway, Render, Fly.io)

These platforms build each service from its own Dockerfile and give every service a private address the others can reach without a public URL.

1. Create **two services from this one repo**: one with build context `.` / Dockerfile `server/Dockerfile`, one with build context `.` / Dockerfile `bot/Dockerfile`.
2. Give the server service its env vars (`GROQ_API_KEY`, `MONGODB_URI`, …) and **do not expose a public domain/ingress for it** — only internal/private networking between your two services.
3. Give the bot service `TELEGRAM_BOT_TOKEN` and set `BACKEND_URL` to the server's *internal* address the platform assigns (e.g. Railway's private networking hostname, Render's internal service URL, Fly.io's `.flycast` address).
4. These platforms' ephemeral filesystems reset on redeploy, so anything written only to `server/logs/` (feedback, server/bot logs) won't survive a redeploy unless you attach a persistent volume (Railway and Fly.io both support one; mount it at `/app/server/logs`). User-reported feedback (`/api/feedback`) and usage counters (`GET /api/metrics`) both switch from the log file to MongoDB automatically once `MONGODB_URI` is set, which sidesteps this on a platform without persistent volumes.
5. Health check path for the server service: `/api/health`.

## MongoDB Atlas (optional)

Needed only for a shared/updatable scheme catalogue and real vector search instead of the in-memory fallback.

1. Create a free Atlas cluster, add a database user, and allow network access from your deployment (its VM's IP, or `0.0.0.0/0` if the platform doesn't give static egress IPs — Atlas still requires the correct credentials).
2. Set `MONGODB_URI` in `.env`.
3. Load the catalogue once: `docker compose exec server python -m app.catalogue.seed data/schemes.json`. This also builds the `scheme_chunks` collection and its Atlas Search/Vector Search indexes (see [server/data/SCHEMES.md](server/data/SCHEMES.md)).

## Checklist before going live

- [ ] `.env` has `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY`; `.env` is never committed
- [ ] `.env` has no inline comments after a value and no quoted values (see "`.env` gotchas" above)
- [ ] Server is not reachable from the public internet (no auth on its endpoints)
- [ ] `docker compose config` resolves with no errors
- [ ] `server_logs` / `bot_logs` volumes are either persistent on your platform, or `MONGODB_URI` is set so feedback and usage metrics survive a redeploy without them
- [ ] `curl http://<host>/api/health` (from inside the network) reports the expected scheme count and catalogue source (`mongodb` or `seed`)
