# Authentication & Security Architecture

## Token & Session Model

CargoPulse uses a **dual-token architecture** designed to mitigate XSS and CSRF risks:

1. **Short-Lived Access Token (JWT, HS256)**
   - Default lifetime: `15 minutes` (`ACCESS_TOKEN_EXPIRE_MINUTES=15`).
   - Stored **strictly in React memory** (`inMemoryAccessToken` in `frontend/src/lib/api-client.ts`) — never written to `localStorage` or `sessionStorage`.
2. **HttpOnly Refresh Token Cookie**
   - Cookie name: `cargopulse_refresh_token` (`HttpOnly=True`).
   - Default lifetime: `7 days` (`REFRESH_TOKEN_EXPIRE_DAYS=7`).
   - Stored hashed in PostgreSQL with rotation on `/api/v1/auth/refresh` and revocation on `/api/v1/auth/logout`.
3. **Double-Submit CSRF Protection**
   - Non-HttpOnly cookie `cargopulse_csrf_token` is paired with the refresh cookie and sent automatically by Axios as `X-CSRF-Token` on `POST`, `PUT`, `PATCH`, and `DELETE` requests.

## Password Hashing & Rate Limiting

- Passwords are hashed using **Argon2** (`argon2-cffi`).
- Sensitive auth endpoints are protected by sliding-window rate limiters (`backend/app/core/rate_limit.py`):
  - `POST /api/v1/auth/login`: 10 requests / 60s per client IP.
  - `POST /api/v1/auth/forgot-password`: 5 requests / 300s per client IP.

## Production Security Checklist

- `ENVIRONMENT=production`, `DEBUG=false`
- `COOKIE_SECURE=true` (enforces `Secure` flag over HTTPS) and `COOKIE_SAMESITE=lax`
- `SECRET_KEY` generated via `openssl rand -hex 32` (startup fails fast if dev secret is detected in production)
- `ALLOWED_ORIGINS` restricted to exact HTTPS frontend origins (no `*` wildcard)
- Security headers enforced on both FastAPI and Nginx: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Strict-Transport-Security`
- RBAC permissions enforced per endpoint (`ORGANIZATION_ADMIN`, `OPS_MANAGER`, `DISPATCHER`, `VIEWER`, etc.) with `organization_id` tenant scoping.
