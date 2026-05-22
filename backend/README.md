# Mock test backend (FastAPI)

## Run locally

From **this folder** (`mock_test/backend`), not from a copied `app` folder elsewhere:

```powershell
cd D:\backup_harishcriticalcareclasses_website_20-01-2026\mock_test\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If you see `No module named 'app'`, you are not in `mock_test/backend` (the directory that contains the `app` package).

## Note

`query_test` and `admin_debug` routers were removed from `main.py` because those modules are not present in this backup. Add them back if you restore the files.

## `403` on email-only login (“not approved” / “payment required”)

With **strict** mode (default `EMAIL_ONLY_LOGIN_STRICT=true`), mock login **without a password** only succeeds if the user row has `payment_status` matching **Credit** (any case) and `approve` meaning **approved** (`1` as string or integer from MySQL).

- **One account fails, others work:** that user is probably not approved or not marked paid in the DB. Fix in your admin panel or SQL, e.g. set `approve = '1'` (and payment as needed) for that email.
- **Local dev — skip those checks:** copy `.env.example` to `.env` in this folder (it sets `EMAIL_ONLY_LOGIN_STRICT=false`), then restart uvicorn.

## New migration endpoints

- `POST /auth/login` -> returns session payload with `access_token`
- `GET /dashboard/summary` -> feature access flags (Video + Mock Test)
- `GET /videos/folders`
- `GET /videos?folder_id=&title=`
- `GET /videos/{video_id}`
- `POST /videos/{video_id}/questions`
- `GET /registration/batches`
- `POST /registration/payable-amount`
- `POST /registration/init`
- `POST /registration/payment/order`
- `POST /registration/payment/callback`
- `POST /registration/payment/webhook`
- `GET /registration/{registration_id}/status`
- `POST /registration/upload-document`

Use `Authorization: Bearer <access_token>` for protected routes.
