# Redis for the API (EC2 local or Upstash)

## Option A — Upstash (managed, TLS)

From the Upstash console, copy the **Redis URL** (user `default`). In `backend/.env` on the API server:

```env
REDIS_ENABLED=true
REDIS_URL=rediss://default:YOUR_TOKEN@YOUR-ENDPOINT.upstash.io:6379
```

`redis://` URLs for `*.upstash.io` are auto-upgraded to `rediss://` by the app. You do **not** need `redis-server` on EC2 when using Upstash. Still run the **RQ worker** (`criticalcare-worker`) on EC2 so WhatsApp bulk and **email campaign** jobs execute there.

Email campaigns enqueue on the `email` RQ queue. The API starts a 60s poller for IST schedules when Redis is enabled. Keep `REDIS_ENABLED=true` in production.

Test from your machine:

```bash
redis-cli --tls -u "rediss://default:YOUR_TOKEN@YOUR-ENDPOINT.upstash.io:6379" ping
```

Restart API + worker after changing `.env`.

---

## Option B — Redis on the API EC2 instance

Run these steps on the Ubuntu API server (same host as `criticalcare-api`).

## Install

```bash
sudo apt update
sudo apt install -y redis-server
```

## Secure (localhost + password)

Edit `/etc/redis/redis.conf`:

- `bind 127.0.0.1 ::1`
- `requirepass YOUR_STRONG_PASSWORD`
- `maxmemory 256mb` (optional)
- `maxmemory-policy allkeys-lru` (optional)

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
redis-cli -a YOUR_STRONG_PASSWORD ping   # expect PONG
```

Do **not** open TCP 6379 in the AWS security group.

## Backend `.env`

```env
REDIS_ENABLED=true
REDIS_URL=redis://:YOUR_STRONG_PASSWORD@127.0.0.1:6379/0
```

## Worker (WhatsApp bulk + email campaign queues)

The unit listens on `default`, `whatsapp`, and `email`:

```
rq worker --url ${REDIS_URL} default whatsapp email
```

Install units from this repo:

```bash
sudo cp deploy/criticalcare-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now criticalcare-worker
```

## Verify

```bash
curl -s http://127.0.0.1:8000/health | jq
```
