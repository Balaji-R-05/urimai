# Deploying Urimai

Both services are in `compose.yml` (`server/Dockerfile`, `bot/Dockerfile`). The bot uses Telegram **long
polling**, so nothing needs an inbound webhook or a public URL for the bot. The server only needs to be
reachable *from the bot* — it has no authentication, so **don't give it a public route** unless you add one.

## Prerequisites

- A `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY` (see [.env.example](.env.example))
- Optional: a MongoDB Atlas cluster for the scheme catalogue and vector search (`MONGODB_URI`). Without it,
  the server uses the bundled JSON seed and an in-memory retrieval backend — fine for a demo, fine for low
  traffic, but catalogue edits need a redeploy instead of a database update.
- Docker + Docker Compose on whatever you deploy to

## Option A — a single VM (simplest, recommended for a hackathon demo)

Any always-on VM works (Oracle Cloud's free tier, a $5 DigitalOcean/Lightsail droplet, a GCP/AWS free-tier
instance, …). Both containers run on it; `server` is never exposed to the internet.

```bash
# on the VM
git clone https://github.com/Balaji-R-05/urimai.git
cd urimai
cp .env.example .env
nano .env                       # fill in TELEGRAM_BOT_TOKEN, GROQ_API_KEY, MONGODB_URI if using Atlas
docker compose up --build -d
docker compose logs -f          # watch both services start; Ctrl+C to stop watching (containers keep running)
```

- Don't open port 8000 in the VM's firewall/security group — `compose.yml` only needs it for your own
  `curl http://localhost:8000/api/health` from inside the VM. The bot reaches the server over the compose
  network at `http://server:8000` regardless of whether the port is published.
- **Updating:** `git pull && docker compose up --build -d`. The named volumes (`models`, `server_logs`,
  `bot_logs`) survive this — only `docker compose down -v` deletes them.
- **Restart on reboot:** both services already have `restart: unless-stopped`; also enable Docker's own
  service (`sudo systemctl enable docker`) so containers come back after a VM reboot.
- **Logs:** `docker compose logs -f server` / `bot`, or read the rotating files inside the volumes:
  `docker compose exec server cat logs/feedback.log`.

## Option B — managed container platforms (Railway, Render, Fly.io)

These platforms build each service from its own Dockerfile and give every service a private address the
others can reach without a public URL.

1. Create **two services from this one repo**: one with build context `.` / Dockerfile `server/Dockerfile`,
   one with build context `.` / Dockerfile `bot/Dockerfile`.
2. Give the server service its env vars (`GROQ_API_KEY`, `MONGODB_URI`, …) and **do not expose a public
   domain/ingress for it** — only internal/private networking between your two services.
3. Give the bot service `TELEGRAM_BOT_TOKEN` and set `BACKEND_URL` to the server's *internal* address the
   platform assigns (e.g. Railway's private networking hostname, Render's internal service URL, Fly.io's
   `.flycast` address).
4. These platforms' ephemeral filesystems reset on redeploy, so `server/logs/feedback.log` won't survive a
   redeploy unless you attach a persistent volume (Railway and Fly.io both support one; mount it at
   `/app/server/logs`). Without that, treat user-reported feedback as best-effort until you add one, or point
   `LOG_DB_CALLS`-style logging at an external sink instead.
5. Health check path for the server service: `/api/health`.

## MongoDB Atlas (optional)

Needed only for a shared/updatable scheme catalogue and real vector search instead of the in-memory fallback.

1. Create a free Atlas cluster, add a database user, and allow network access from your deployment (its VM's
   IP, or `0.0.0.0/0` if the platform doesn't give static egress IPs — Atlas still requires the correct
   credentials).
2. Set `MONGODB_URI` in `.env`.
3. Load the catalogue once: `docker compose exec server python -m app.catalogue.seed data/schemes.json`. This
   also builds the `scheme_chunks` collection and its Atlas Search/Vector Search indexes (see
   [server/data/SCHEMES.md](server/data/SCHEMES.md)).

## Checklist before going live

- [ ] `.env` has `TELEGRAM_BOT_TOKEN` and `GROQ_API_KEY`; `.env` is never committed
- [ ] Server is not reachable from the public internet (no auth on its endpoints)
- [ ] `docker compose config` resolves with no errors
- [ ] `server_logs` / `bot_logs` volumes are either persistent on your platform, or you've accepted that
      `feedback.log` resets on redeploy
- [ ] `curl http://<host>/api/health` (from inside the network) reports the expected scheme count and
      catalogue source (`mongodb` or `seed`)
