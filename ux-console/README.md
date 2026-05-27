# ux-console

Next.js (App Router) frontend for Synteles — replacing the Streamlit/EC2 UX.
Deployed as a Docker container via the `frontend-ui` Terraform module (EC2 + CloudFront).

## Stack

- **Framework:** Next.js 16, TypeScript, App Router
- **UI:** Tailwind CSS + shadcn/ui
- **Auth:** Cognito Authorization Code + PKCE + client_secret (confidential client, server-side)
- **Server state:** TanStack Query
- **Hosting:** EC2 t3.micro + CloudFront

## Local development

```bash
cp .env.example .env.local   # fill in Cognito + API values
pnpm install
pnpm dev                     # http://localhost:3000
```

Required env vars — see `.env.example`.

## Build

```bash
pnpm build   # produces .next/standalone for Docker
```

## Project structure

```
app/
├── (auth)/           # login, callback, logout — no dashboard layout
└── (dashboard)/      # protected routes — requires valid sid_at cookie
lib/
├── config.ts         # all env var references in one place
├── auth.ts           # token exchange, refresh, cookie helpers
├── auth-constants.ts # shared cookie names and TTLs
├── pkce.ts           # PKCE verifier/challenge (Web Crypto SHA-256)
└── api-client.ts     # typed fetch wrapper with Bearer token
proxy.ts              # Next.js 16 proxy (guards /dashboard/*, silent token refresh)
```

## Testing

### Unit tests (Vitest)

```bash
pnpm test            # run all unit tests once
pnpm test:watch      # watch mode — reruns on file change
pnpm test:coverage   # generate v8 coverage report
```

No setup required — env vars are injected by `vitest.config.ts` and `next/headers` / `next/navigation` are mocked globally in `vitest.setup.ts`.

Test files live in `__tests__/`:

| File | What it covers |
|------|----------------|
| `__tests__/proxy.test.ts` | All 6 proxy branches + matcher config |
| `__tests__/routes/callback.test.ts` | CSRF validation, Cognito error passthrough, token exchange, cookie lifecycle |
| `__tests__/lib/auth.test.ts` | `exchangeCodeForTokens`, `getServerToken`, `getUser` |
| `__tests__/lib/api-client.test.ts` | `apiFetch` — headers, 204, errors, `ApiError` shape |
| `__tests__/lib/pkce.test.ts` | PKCE derivation, state uniqueness |
| `__tests__/lib/utils.test.ts` | `cn()` merging + Tailwind conflict resolution |

### E2E tests (Playwright)

```bash
pnpm test:e2e        # launch Chromium + start dev server automatically
```

Playwright config is at `e2e/playwright.config.ts`. It starts `pnpm dev` automatically (reuses an existing server if already running outside CI). Tests cover protected route redirects, logout, CSRF rejection, PKCE initiation, and dashboard smoke tests — no live Cognito connection needed.

Token refresh E2E tests are marked `test.fixme()` because Playwright only intercepts browser-initiated requests, not Next.js server-side fetches.

### MSW mock server

`mocks/handlers.ts` + `mocks/server.ts` define a [MSW](https://mswjs.io/) node server used by integration tests. It can also be loaded during `pnpm dev` for fully offline development.
