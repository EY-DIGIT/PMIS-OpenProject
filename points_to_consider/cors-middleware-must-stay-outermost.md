# `CORSMiddleware` must stay OUTERMOST + security boundaries the doc-39 fix relies on

## What the fix actually does (and what it depends on)

After doc 39, monolith's middleware stack is ordered so `CORSMiddleware` is the **outermost** wrapper (added LAST in [app/main.py](../app/main.py)). This is **load-bearing**: the proxy middlewares (`UserServiceProxyMiddleware`, `NotificationServiceProxyMiddleware`) short-circuit response delivery by calling `await response(scope, receive, send)` directly without going through `self.app`. Any middleware mounted *inside* the proxy never sees the response, so it can't add headers on the way out.

If `CORSMiddleware` is moved back inside the proxy stack, every proxied response (login, RBAC, master/notification_templates) loses its `Access-Control-Allow-Origin` header. The FE breaks with "Failed to fetch" exactly as it did before doc 39.

The regression tests in `tests/test_doc37_user_service_proxy.py::TestCorsPreflightBypass` and `tests/test_doc38_notification_service_proxy.py::TestCorsPreflightBypass` will fail loudly if anyone reorders the middleware. The error message points at the cause.

## Security implications worth knowing

### 1. `allow_credentials=True` + the allowlist is a CSRF-relevant trust boundary

Monolith runs `CORSMiddleware(allow_origins=settings.CORS_ORIGINS, allow_credentials=True, ...)`. With credentials enabled, the browser will:

- Echo back the calling origin in `Access-Control-Allow-Origin` (Starlette switches to specific-origin mode automatically).
- Allow the JS code on that origin to **read** authenticated responses.
- Allow that JS to **send** cookies / auth headers in subsequent calls.

So `CORS_ORIGINS` is **the FE-trust allowlist**. Anything in there can issue authenticated requests on behalf of a logged-in user. Concretely:

- ❌ Never put `"*"` in `CORS_ORIGINS` while `allow_credentials=True` is set. Starlette will refuse to combine them anyway, but the wrong fix is to drop credentials — the FE needs cookies/Authorization to flow.
- ❌ Never add a third-party domain to `CORS_ORIGINS` "for testing". A site embedded under that origin can quietly mount API calls against the user's session.
- ✅ Keep `CORS_ORIGINS` to the actual FE deploys: dev (`http://localhost:3000`), staging, production (`http://10.1.131.199:3000`). One line per origin.

If a new FE host gets stood up (mobile, embedded view, white-label), that origin must be added explicitly — and reviewed before merge. Treat additions to `CORS_ORIGINS` as a security-sensitive change.

### 2. The proxy `OPTIONS` early-return is defense in depth — keep it

After doc 39, with `CORSMiddleware` outermost, preflights never reach the proxy in normal operation. The proxy's `OPTIONS` early-return is now technically redundant — but it's still in the code (3 lines per middleware) for two reasons:

- **Reorder defence.** Anyone who later moves `CORSMiddleware` back inside the proxy will be saved from the "preflight 405s on every request" symptom by the proxy's own bypass. They'll still hit the missing-response-headers half of the bug, but at least preflight works and the issue is much more localised to debug.
- **Backstop for non-CORS `OPTIONS`.** Some HTTP clients send `OPTIONS` for service-discovery (`OPTIONS /api/v3/users` to learn allowed methods). The early-return lets monolith's local routing handle that consistently, regardless of proxy state.

Don't remove the early-return as "dead code." It's a 3-line guard with zero hot-path cost.

### 3. Upstream response bodies are now CORS-exposed via the gateway

`CORSMiddleware` outermost wraps **every** response — local handler responses AND proxied responses from user-mgmt / notification-service. That's the entire point of the fix. But it also means:

- A response from user-mgmt that contains, say, a user profile is now exposed to the FE origin via CORS. That's intended — the FE asked for it.
- If the proxy ever forwarded a path that returns secrets *not* intended for the FE (admin-only diagnostics, internal-only fields), CORS would expose them anyway. The gate against this isn't CORS — it's the upstream service's auth + permission checks.
- The proxy strips most response headers from the upstream response (only `content-type` + `x-request-id` pass through). It does NOT forward `Set-Cookie`. If user-mgmt or notification-service ever starts setting cookies that should reach the browser, the proxy's `forwarded_headers` allowlist in `_proxy_request_sync` must be extended — and that's a security review.

### 4. If `pmis-usermanagement` or `pmis-notification` ever face public ingress, they need their own CORS

Today both services live on the internal network. Browsers never talk to them directly; everything goes through the monolith gateway. They have no `CORSMiddleware` configured (and don't need one). The doc-39 fix relies on this: CORS only happens at the gateway.

If a future deploy puts either service behind a public ingress — for example, a CDN that calls notification-service's `/api/v1/notifications/dispatch` directly without the monolith hop — that service will need its own `CORSMiddleware` and its own allowlist. The current "no CORS in microservices" posture is correct *only* while they're internal-only. Re-evaluate when network topology changes. See also [points_to_consider/dispatch-endpoint-internal-network-only.md](https://github.com/EY-DIGIT/PMIS-notification-service/blob/dev/points_to_consider/dispatch-endpoint-internal-network-only.md) in PMIS-notification-service.

### 5. Auth runs INSIDE CORS — that's correct, not a bug

`AuthenticationMiddleware` is mounted inside `CORSMiddleware` (added before it). This means CORS preflights are answered without any auth. That's by design: browsers can't send `Authorization` on preflight, so requiring auth on `OPTIONS` would break every CORS-using FE. It's not a leak — preflight responses contain only CORS metadata, not application data.

## Quick reference — when reading `app/main.py`

```python
# request order (outermost -> innermost):
#   1. CORSMiddleware       (added LAST)
#   2. NotificationServiceProxyMiddleware
#   3. UserServiceProxyMiddleware
#   4. AuthenticationMiddleware
#   5. LoggingMiddleware    (added FIRST)
```

The OUTERMOST item is the one added LAST. The middleware stack is LIFO. Anyone adding new middleware needs to decide:

- **Outside the proxy** (added after the proxies) → wraps proxied responses too. Use for response-decoration (CORS, custom headers, response-time stamping).
- **Inside the proxy** (added before the proxies) → only runs for non-proxied paths. Use for monolith-local concerns (auth, request-state hydration, anything that depends on the local DB session).
