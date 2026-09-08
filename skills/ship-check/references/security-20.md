# The 20 — vibe-coded app vulnerabilities, made checkable

Every item carries a **class**, a **method**, an **expected result**, and the
**evidence** that closes it. A checklist without a check is a vibe.

- **AUTOMATED** — a tool returns a verdict
- **SEMI** — a defined procedure you must actually run
- **MANUAL** — requires reasoning about intent; a scanner cannot answer it

**Roughly half are AUTOMATED. The other half are where real breaches live.**

---

## 1. `.env` committed to the repository

**Class:** AUTOMATED

- **Method:** `gitleaks detect` (scans history, not just the working tree) plus `git log --all --full-history -- '**/.env*'`
- **Expected:** no matches in any commit
- **Evidence:** gitleaks exit code; the git log output
- **Prevention in this harness:** the write guard blocks env-file writes, and Layer 0 denies reads
- **If found:** rotate every credential *first*. Removing the file does not un-leak it — history is public the moment it is pushed.

## 2. API keys in the frontend bundle

**Class:** AUTOMATED / SEMI

- **Method:** grep the **built** output, not the source: `grep -rE "(sk-|AKIA|ghp_|AIza)" dist/ .next/ build/`. In Next.js, check every `NEXT_PUBLIC_*` var.
- **Expected:** no credentials in shipped assets
- **Evidence:** grep over the build directory
- **The trap:** `NEXT_PUBLIC_` and `VITE_` prefixes are *inlined into the bundle by design*. A service-role key behind one is public.
- **Fix:** the key moves server-side — a route handler, an edge function, a BFF. There is no client-side way to hide a secret.

## 3. No Row Level Security

**Class:** MANUAL

- **Method:** for every table, confirm RLS is enabled *and* a policy exists. Enabled with no policy denies all; a permissive policy (`using (true)`) enables all. Query `pg_policies`.
- **Expected:** every table with user data has RLS on and a policy scoped to the requesting user
- **Evidence:** the policy list, per table
- **Why MANUAL:** a scanner sees a policy exists. Only you know whether it expresses the right rule.
- **Test that actually proves it:** authenticate as user A, request user B's row. You should get nothing — not a permission error, nothing.

## 4. Authorization enforced only in the frontend

**Class:** MANUAL

- **Method:** for each privileged action, find the **server-side** check. Hiding a button is not authorization.
- **Expected:** every mutation re-checks permission on the server, independently of what the client sent
- **Evidence:** the file:line of the server-side check for each privileged route
- **Test:** call the endpoint directly with a non-privileged token. `curl` does not render your UI.
- **Why MANUAL:** this is the single most commonly exploited item on the list and no tool finds it.

## 5. No rate limiting

**Class:** SEMI

- **Method:** send 100 requests to the most expensive unauthenticated endpoint (login, signup, password reset, search, any AI-backed route)
- **Expected:** `429` after a documented threshold
- **Evidence:** status-code log across the run
- **Priority order:** login and password reset first — those are credential-stuffing targets. AI endpoints next; they cost real money per call.

## 6. SQL built by string concatenation

**Class:** AUTOMATED

- **Method:** `semgrep --config auto`; grep for template literals and `+` inside query calls
- **Expected:** parameterised queries everywhere
- **Evidence:** semgrep output
- **Note:** an ORM is not automatic safety — raw escape hatches (`knex.raw`, `db.execute`, `$queryRawUnsafe`) reintroduce it.

## 7. No input validation

**Class:** SEMI

- **Method:** confirm every route parses input through a schema (zod, pydantic, valibot) at the boundary
- **Expected:** unparsed request data never reaches business logic
- **Evidence:** the schema per route; a list of routes with none
- **Test:** send a wrong-typed field, an oversized string, and a negative number where a positive is assumed.

## 8. User content rendered as raw HTML

**Class:** AUTOMATED

- **Method:** grep `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, `|safe`, `mark_safe`
- **Expected:** none over user-supplied content, or sanitised through DOMPurify with an allowlist
- **Evidence:** grep results with the source of each value traced
- **Test payload:** store `<img src=x onerror=alert(1)>` in a profile field and view it as another user.

## 9. Passwords stored in plaintext or with a weak hash

**Class:** SEMI

- **Method:** read the storage path. Look for argon2id or bcrypt (cost ≥ 12). Reject MD5, SHA-1, SHA-256, and any unsalted digest.
- **Expected:** argon2id preferred; bcrypt acceptable
- **Evidence:** the hashing call, file:line
- **See:** [auth.md](auth.md)

## 10. Auth tokens in `localStorage`

**Class:** AUTOMATED / SEMI

- **Method:** grep `localStorage` and `sessionStorage` near token, jwt, session, auth
- **Expected:** session tokens in `httpOnly` + `Secure` + `SameSite` cookies
- **Evidence:** grep results; the cookie flags actually set on the response
- **Why it matters:** `localStorage` is readable by any script on the page. One XSS or one bad dependency and every session is exfiltrated. `httpOnly` makes that impossible from JS.

## 11. Admin panel behind OAuth with no authorization

**Class:** MANUAL

- **Method:** find the admin route's authorization check. **Authentication is not authorization** — "signed in with Google" only proves someone has a Google account.
- **Expected:** an explicit role or allowlist check, server-side, on every admin route
- **Evidence:** the check, file:line, plus how role is assigned
- **Test:** sign in with an unrelated account and request the admin route directly.

## 12. CORS set to `*`

**Class:** AUTOMATED

- **Method:** grep CORS config for `*`, and for reflecting `Origin` back
- **Expected:** an explicit allowlist of origins
- **Evidence:** the config
- **The dangerous combination:** `Access-Control-Allow-Origin` reflected **plus** `Allow-Credentials: true` lets any site make authenticated requests as your user. Browsers forbid literal `*` with credentials — reflection is the bypass people reach for.

## 13. No email verification

**Class:** SEMI

- **Method:** sign up with an address you do not control; try to use the account
- **Expected:** unverified accounts cannot perform meaningful actions
- **Evidence:** the signup flow result
- **Impact:** account takeover by pre-registration, and your domain used for spam.

## 14. Predictable / sequential identifiers

**Class:** MANUAL

- **Method:** look at IDs in URLs and API responses. Sequential integers mean every record is enumerable.
- **Expected:** UUIDv4/v7, or a strict authorization check on every lookup
- **Evidence:** the ID scheme, and the ownership check per endpoint
- **Nuance:** sequential IDs are not themselves a vulnerability — they are an *amplifier* for item 4. With correct authorization they are merely untidy. Without it, they turn one leak into a full export. This is IDOR.
- **Test:** fetch your record, then decrement the ID.

## 15. Persisting the whole request body

**Class:** MANUAL

- **Method:** grep for spread-into-persistence: `{...req.body}`, `Object.assign(user, req.body)`, `Model(**data)`
- **Expected:** explicit allowlisted fields (a DTO)
- **Evidence:** the persistence call per route
- **The attack:** mass assignment. Post `{"email":"...","role":"admin"}` to profile-update and grant yourself a role the UI never offered.

## 16. Webhooks accepted without signature verification

**Class:** SEMI

- **Method:** POST a forged payload to the webhook endpoint with no signature
- **Expected:** `401`
- **Evidence:** the response, plus the verification call
- **Two requirements:** verify against the **raw** body (JSON parsing changes bytes and breaks the HMAC), and compare in **constant time**.
- **Impact:** forged payment-succeeded events are free products.

## 17. Stack traces in production responses

**Class:** AUTOMATED

- **Method:** confirm the error handler branches on environment; grep for `debug: true`, `app.debug`, `DEBUG=True`
- **Expected:** generic message plus a correlation id to the client; detail to logs only
- **Evidence:** the error handler, and a 500 response from a production-like build
- **What leaks:** file paths, library versions, SQL fragments, sometimes credentials in a connection string.

## 18. Outdated dependencies

**Class:** AUTOMATED

- **Method:** `npm audit --omit=dev --audit-level=high`, `pip-audit`
- **Expected:** no high or critical advisories reachable from your code
- **Evidence:** the audit output
- **Judgement:** reachability matters. A critical in a dev-only transitive dependency is not the same risk as one in your request path. Say which you have.

## 19. No password strength requirements

**Class:** SEMI

- **Method:** try to register with `password`, `12345678`, and the site's own name
- **Expected:** rejected against a breach list
- **Evidence:** the registration attempts
- **Modern guidance:** minimum length (≥ 8, ideally 12) plus a breached-password check beats composition rules. Forced symbols and rotation produce `Password1!` and reuse. See [auth.md](auth.md).

## 20. No file-upload validation

**Class:** SEMI / MANUAL

- **Method:** upload a file with a mismatched extension, an oversized file, and a `.svg` containing a script
- **Expected:** type checked by **content** (magic bytes) not extension; size capped; stored off the app domain; served with `Content-Disposition: attachment` and a non-executable content type
- **Evidence:** each upload attempt and its result
- **Three separate failures here:** stored XSS via SVG or HTML, resource exhaustion via size, and remote code execution when uploads land somewhere executable. Check all three.

---

## Reporting template

```
AUTOMATED   — <n> checked, <n> findings
SEMI        — <n> performed, <n> not performed (say which)
MANUAL      — <n> reviewed; NONE of these can be reported as "passed"
```

## The thing to say out loud

Items **3, 4, 11, 14, 15** — RLS, server-side authorization, admin access,
identifier enumeration, mass assignment — are where real breaches happen, and
**not one of them is caught by a scanner.** They need someone who understands
what the application is supposed to permit.

If a report claims all twenty are clear, it is wrong. Say what was reasoned
about versus what was measured.
