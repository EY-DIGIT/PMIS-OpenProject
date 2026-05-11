# Doc 38: monolith's local notification renderer + master endpoints are dead code in proxy-on prod

## What it means

When **both** proxy flags are on (the production target):

- `USER_SERVICE_PROXY_ENABLED=true` → all `/api/v3/users/*` and `/api/v3/master/{roles,permissions}/*` traffic forwards to PMIS-user-management. Monolith's local handlers in [app/api/v3/users/](../app/api/v3/users/) and the corresponding master_data handlers never execute.
- `NOTIFICATION_SERVICE_PROXY_ENABLED=true` → all `/api/v3/master/notification_templates/*` traffic forwards to PMIS-notification-service. Monolith's local notification_template CRUD handlers never execute.

That means the following monolith files are loaded but **never invoked at runtime** in this configuration:

- [app/shared/notifications.py](../app/shared/notifications.py) — the local `_render_email` / `_render_sms` / `_lookup_template` renderer + `HttpNotificationClient` that POSTs pre-rendered bodies to notification-service's `/email/send` and `/sms/send`.
- The `notification_templates` slice of [app/api/v3/master_data/routes.py](../app/api/v3/master_data/routes.py) — list / get / create / update / delete / restore.
- The `NotificationTemplateModel` import path is still alive because [app/shared/notifications.py](../app/shared/notifications.py) imports it; if that file is deleted, the model becomes a passive participant in `Base.metadata` only.

## Why it's still here

Strangler-fig. The local code is a fallback for two cases:

1. **Rollback** — flipping either proxy flag back to `false` in an environment where the standalone service has issues. The local code path is still functionally correct; it's the pre-doc-38 behavior.
2. **Internal monolith jobs** — if any future scheduled task / worker inside the monolith dispatches a notification without going through an HTTP route, it would call `HttpNotificationClient.send` directly. As of this writing, no such caller exists in the monolith — every dispatch site is reachable from an `/api/v3/users/*` route, and those are proxied off.

## Implications for future work

- **Don't fix bugs in the local renderer.** If a placeholder / template behavior needs to change, change it in PMIS-notification-service (`app/services/template_service.py`). The monolith's copy will not be exercised in prod.
- **Don't add new template kinds here.** Add them in PMIS-notification-service's `ALLOWED_PLACEHOLDERS` and seed loop. Monolith and user-mgmt are pure dispatch callers.
- **Don't extend the master_data routes for notification_templates.** Any new admin field / endpoint goes on the canonical handlers in PMIS-notification-service (`app/routes/master_data_routes.py`). The proxy will surface it transparently.
- **A future Phase-2-on-monolith commit can delete this code.** Hygiene only; not a correctness fix. The order would mirror what was done for user-mgmt: switch `HttpNotificationClient.send` to call `/api/v1/notifications/dispatch`, then drop the local renderer + master endpoints + model. See PMIS-user-management commit `7dae3b5` for the template.

## Verifying state

To confirm the proxy actually intercepts the path on a deployed monolith:

    curl -i -H 'Authorization: Bearer <token>' http://monolith:8000/api/v3/master/notification_templates

The response body should originate from notification-service (look for the `request_id` shape and the `_links.self.href` value `/api/v3/master/notification_templates` matching notification-service's handler). If the same path returns rows from monolith's local DB query, the proxy flag is off — that's a config issue, not a code issue.
