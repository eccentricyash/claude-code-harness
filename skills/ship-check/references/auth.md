# Authentication and session handling

Covers items 9, 10, 11, 13, 19 of [security-20.md](security-20.md) in depth.

**The rule that prevents most of this:** do not build authentication yourself.
Use the platform's provider (Supabase Auth, Auth.js, Clerk, Django's auth,
Rails' `has_secure_password`). Almost every item below is already correct in a
maintained library and almost never correct in a hand-rolled one.

---

## Password storage

| Use | Do not use |
|---|---|
| **argon2id** — preferred | MD5, SHA-1, SHA-256 — fast by design, which is exactly wrong here |
| **bcrypt**, cost ≥ 12 — acceptable, well-supported | any unsalted digest |
| **scrypt** — acceptable | your own construction |

Salting is not optional and is handled for you by all three. If you can see a
salt column you are managing manually, look closer.

**bcrypt's 72-byte limit is real:** input past 72 bytes is silently ignored, so
a long passphrase can be truncated. Pre-hash to a fixed length, or use argon2id.

**Method:** find the hashing call, file:line. **Evidence:** the algorithm and
cost parameter.

---

## Password policy — modern guidance

Composition rules produce `Password1!` and reuse. Length plus a breach check
does more.

| Do | Do not |
|---|---|
| Minimum 8, prefer 12 | Require symbols/mixed case/digits |
| Check against a breach corpus (k-anonymity range API — you never send the password) | Force rotation on a schedule |
| Allow up to at least 64 chars | Cap length at 16 |
| **Allow paste** and password managers | Block paste on password or OTP fields |
| Allow all Unicode, spaces included | Strip characters silently |

Forced rotation is actively harmful: it drives `Summer2024!` → `Summer2025!`.
Rotate on evidence of compromise, not on a timer.

**Blocking paste also fails WCAG 3.3.8** (Accessible Authentication), so it is
an accessibility defect as well as a security one.

---

## Session storage — cookies, not `localStorage`

```
Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=...
```

| Flag | Why |
|---|---|
| `HttpOnly` | JavaScript cannot read it. This is the whole point — it converts "one XSS" from "every session stolen" into "no session stolen". |
| `Secure` | never sent over plaintext HTTP |
| `SameSite=Lax` | blocks the common CSRF shapes; `Strict` if no cross-site entry flows |
| `Path=/` | scope deliberately |

**`localStorage` is readable by any script on the page** — including every
dependency you did not audit. There is no configuration that fixes this. If a
token must be in JS memory (a SPA calling a separate API), keep it in a closure
variable, never persisted, with a short lifetime and a refresh token in an
`HttpOnly` cookie.

**Method:** grep `localStorage` near token/jwt/session/auth, and read the actual
`Set-Cookie` response header. **Evidence:** the flags that are really set.

---

## Tokens

- **Short-lived access tokens** (minutes), long-lived refresh tokens that rotate on use
- **Rotation with reuse detection:** if an old refresh token is presented again, revoke the whole family — that is the signal a token was stolen
- **Verify the signature and the algorithm.** Pin the expected algorithm; never trust the token's own `alg` header. `alg: none` and RS256→HS256 confusion are both live attack classes.
- **Check `exp`, `iss`, `aud`** — a valid signature from the wrong issuer is still wrong
- **JWTs cannot be revoked.** If you need logout-everywhere or instant ban, you need server-side session state or a short TTL plus a denylist. "Stateless" and "revocable" do not coexist.

---

## Authentication is not authorization

The distinction behind items 4 and 11, and the most exploited gap on the list.

- **Authentication:** who is this? → "signed in with Google" proves someone has a Google account. Nothing more.
- **Authorization:** may they do this, to this object? → checked **server-side, on every request**.

Two checks, every privileged route:

1. **Can this role do this action?** (RBAC)
2. **Does this user own this specific object?** (ownership / tenancy)

The second is skipped constantly. `GET /invoices/123` with a valid session that
returns someone else's invoice is IDOR, and it passes every authentication check
you have.

**Never trust the client for identity.** A `userId` in a request body, a query
param, or a decoded-but-unverified token is an assertion by the caller. Derive
identity from the verified session, server-side, always.

---

## Account lifecycle

| Flow | Requirement |
|---|---|
| **Email verification** | Unverified accounts cannot perform meaningful actions. Single-use, expiring token. |
| **Password reset** | Single-use, short expiry (≤ 1h), invalidated on use and on password change. **Revoke all sessions after a reset.** |
| **Enumeration** | Login, signup, and reset must return the same response and take similar time for existing and non-existing accounts. Differing error text or timing enumerates your user list. |
| **Lockout** | Rate-limit and back off rather than hard-locking — hard lockout is a denial-of-service against your own users. |
| **OAuth callback** | Validate `state` (CSRF) and PKCE. Never trust an unverified `email` claim to link accounts — that is account takeover by registration. |

---

## Verification checklist

| # | Check | Class |
|---|---|---|
| 1 | Hashing is argon2id or bcrypt ≥ 12 | SEMI |
| 2 | Sessions in `HttpOnly` + `Secure` + `SameSite` cookies | SEMI |
| 3 | Breach check on registration; paste allowed | SEMI |
| 4 | Every privileged route has a server-side role check | **MANUAL** |
| 5 | Every object lookup has an ownership check | **MANUAL** |
| 6 | Reset tokens single-use and expiring; sessions revoked after reset | SEMI |
| 7 | No user enumeration via message or timing | SEMI |
| 8 | Token algorithm pinned; `exp`/`iss`/`aud` verified | SEMI |
| 9 | Identity derived from session, never from request input | **MANUAL** |

**4, 5 and 9 cannot be reported as passing** from code reading alone. State what
you checked and what you could not determine.
