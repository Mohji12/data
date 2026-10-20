# ZeptoMail bounce webhooks

Campaign analytics treat **Accepted** as SMTP acceptance only. Hard/soft bounces and spam complaints arrive later from ZeptoMail. Configure the Agent webhook so those events update `mail_suppression` and `delivery_status`.

This is not complete until a live Agent test bounce is received in the target environment.

## Endpoint

`POST https://<API_PUBLIC_HOST>/mail/zepto/webhook`

No admin JWT. Authentication is the Zepto Agent webhook secret (below).

## Agent setup

1. ZeptoMail → Agents → your sending Agent → **Webhooks**.
2. Add webhook URL: `https://<API_PUBLIC_HOST>/mail/zepto/webhook`.
3. Enable at least: **Hard bounced**, **Soft bounced**, **Feedback loop**, **Delivered**.
4. Optional: set a per-webhook **Authorization** header (name + value). Put the same values in `.env`.
5. On the Webhooks page, set **Authentication Key**. Store it as `ZEPTOMAIL_WEBHOOK_AUTH_KEY`. Zepto signs requests with HMAC-SHA256 in the `producer-signature` header.

If HMAC is not enabled on the Agent, Authorization-header-only still works. If **neither** secret is set, the API returns 401 and does not ingest events.

## Backend `.env`

```
ZEPTOMAIL_WEBHOOK_AUTH_KEY=
ZEPTOMAIL_WEBHOOK_AUTHORIZATION_HEADER=Authorization
ZEPTOMAIL_WEBHOOK_AUTHORIZATION_VALUE=
ZEPTOMAIL_WEBHOOK_MAX_SKEW_SEC=900
MAIL_SOFT_BOUNCE_SUPPRESS_AFTER=3
MAIL_DNS_TIMEOUT_SEC=2
```

Restart the API after changing these. Schema is created/altered on boot (`mail_provider_event` table and extra suppression/campaign columns). No Alembic.

## Behaviour

- `hardbounce` → suppress `hard_bounce`, never send again.
- `softbounce` → recorded; suppress `soft_bounce` after 3 events for that address.
- Feedback loop → suppress `complaint` (always skipped, even if “Skip previously bounced” is off).
- `delivered` → recipient `delivery_status=delivered` unless already bounced/complaint.
- Duplicate `webhook_request_id` is ignored (200).
- Campaign link uses SMTP header `X-TM-CLIENT-REF` = `{campaign_id}:{recipient_id}`. If missing, the latest accepted recipient with that email is used.

## Rollback

Drop `mail_provider_event`. Extra columns on `mail_suppression`, `mail_campaign`, and `mail_campaign_recipient` can stay; older campaign send still works if they are left in place.
