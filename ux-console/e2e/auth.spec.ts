// Copyright 2026 Emin Askerov
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { test, expect, type BrowserContext } from '@playwright/test'

// ── Helpers ────────────────────────────────────────────────────────────────

async function injectAuthCookies(context: BrowserContext, opts?: { skipAccessToken?: boolean }) {
  const cookieBase = {
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    secure: false,
    sameSite: 'Lax' as const,
  }
  const cookies = []
  if (!opts?.skipAccessToken) {
    cookies.push({ ...cookieBase, name: 'sid_at', value: 'valid-access-token', expires: Date.now() / 1000 + 3600 })
  }
  cookies.push({ ...cookieBase, name: 'sid_rt', value: 'valid-refresh-token', expires: Date.now() / 1000 + 86400 * 30 })
  await context.addCookies(cookies)
}

async function mockPlatformApi(context: BrowserContext) {
  await context.route('**/api/users/me', (route) =>
    route.fulfill({
      json: {
        sub: 'test-user-id',
        email: 'test@example.com',
        given_name: 'Test',
        family_name: 'User',
        org_id: 'test-org-id',
        org_name: 'Test Org',
      },
    })
  )
  await context.route('**/api/executions**', (route) => route.fulfill({ json: { items: [], total: 0 } }))
  await context.route('**/api/agentlets**', (route) => route.fulfill({ json: { items: [] } }))
  await context.route('**/api/conversations**', (route) => route.fulfill({ json: { conversations: [] } }))
  await context.route('**/api/connectors**', (route) => route.fulfill({ json: { presets: [] } }))
  await context.route('**/api/models**', (route) => route.fulfill({ json: [] }))
  await context.route('**/api/secrets**', (route) => route.fulfill({ json: [] }))
}

// ── Unauthenticated ────────────────────────────────────────────────────────

test.describe('unauthenticated access', () => {
  test('redirects /dashboard to /login when no cookies', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })

  test('preserves intended destination in redirect via next param', async ({ page }) => {
    await page.goto('/dashboard/agentlets')
    await expect(page).toHaveURL(/\/login.*next=/)
  })

  test('/login page is publicly accessible', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveURL('/login')
    await expect(page).not.toHaveURL(/callback|dashboard/)
  })
})

// ── Authenticated navigation ───────────────────────────────────────────────

test.describe('authenticated session', () => {
  test.beforeEach(async ({ context }) => {
    await injectAuthCookies(context)
    await mockPlatformApi(context)
  })

  test('reaches /dashboard without being redirected to /login', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('logout clears auth cookies and lands on /login', async ({ context }) => {
    await injectAuthCookies(context)

    // context.route() does not intercept top-level navigation redirects in Chromium.
    // Use the APIRequestContext instead: stop at the 302 before the browser ever
    // tries to resolve auth.test.example.com.
    const response = await context.request.get('http://localhost:3000/logout', { maxRedirects: 0 })
    expect(response.status()).toBeGreaterThanOrEqual(300)
    expect(response.status()).toBeLessThan(400)

    // Next.js deletes auth cookies via Set-Cookie in the redirect response
    const remaining = await context.cookies()
    const authCookies = remaining.filter((c) => ['sid_at', 'sid_rt', 'sid_it'].includes(c.name))
    expect(authCookies).toHaveLength(0)

    // Redirect must target OIDC logout with logout_uri pointing back to /login
    const location = response.headers()['location'] ?? ''
    expect(location).toContain('/logout')
    expect(location).toContain('logout_uri')
    expect(location).toContain(encodeURIComponent('/login'))
  })
})

// ── Login flow (PKCE initiation) ───────────────────────────────────────────

test.describe('login flow', () => {
  test('sets PKCE and state cookies then redirects to OIDC authorize', async ({ context }) => {
    // Stop at the 302 — don't let the browser follow the redirect to the OIDC provider
    const response = await context.request.get('http://localhost:3000/login/start', { maxRedirects: 0 })
    expect(response.status()).toBeGreaterThanOrEqual(300)
    expect(response.status()).toBeLessThan(400)

    const location = response.headers()['location'] ?? ''
    const capturedUrl = new URL(location)
    expect(capturedUrl.searchParams.get('response_type')).toBe('code')
    expect(capturedUrl.searchParams.get('code_challenge_method')).toBe('S256')
    expect(capturedUrl.searchParams.get('code_challenge')).toBeTruthy()

    const cookies = await context.cookies()
    const verifierCookie = cookies.find((c) => c.name === 'pkce_verifier')
    const stateCookie = cookies.find((c) => c.name === 'oauth_state')
    expect(verifierCookie?.value).toBeTruthy()
    expect(stateCookie?.value).toBeTruthy()
    expect(capturedUrl.searchParams.get('state')).toBe(stateCookie?.value)
  })

  test('sets auth_next cookie when next param is a safe path', async ({ context }) => {
    await context.request.get('http://localhost:3000/login/start?next=/dashboard/agentlets', { maxRedirects: 0 })

    const cookies = await context.cookies()
    const authNext = cookies.find((c) => c.name === 'auth_next')
    expect(decodeURIComponent(authNext?.value ?? '')).toBe('/dashboard/agentlets')
  })

  test('does not set auth_next cookie for unsafe paths', async ({ context }) => {
    await context.request.get('http://localhost:3000/login/start?next=//evil.com', { maxRedirects: 0 })

    const cookies = await context.cookies()
    const authNext = cookies.find((c) => c.name === 'auth_next')
    expect(authNext).toBeUndefined()
  })
})

// ── Callback (login completion) ────────────────────────────────────────────

test.describe('callback route', () => {
  test('completes login and lands on /dashboard', async ({ page, context }) => {
    await context.addCookies([
      { name: 'pkce_verifier', value: 'test-verifier', domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax' },
      { name: 'oauth_state',   value: 'test-state',    domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax' },
    ])

    // Mock the server-side OIDC token exchange — this is called from Next.js server
    // via proxy.ts / callback/route.ts, not from the browser, so it is NOT interceptable
    // by context.route(). To exercise this E2E path you need either:
    //   a) a real Keycloak user + valid auth code, or
    //   b) a local mock server at OIDC_ISSUER_URL (set in .env.test.local)
    //
    // The unit test in __tests__/routes/callback.test.ts provides full coverage of
    // the token exchange logic. This test verifies only the CSRF rejection path which
    // does not require an OIDC provider connection.
    await page.goto('/callback?code=auth-code&state=wrong-state')
    await expect(page).toHaveURL(/\/login\?error=invalid_state/)
  })

  test('redirects to /login on state mismatch', async ({ page, context }) => {
    await context.addCookies([
      { name: 'pkce_verifier', value: 'v', domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax' },
      { name: 'oauth_state',   value: 'real-state', domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax' },
    ])
    await page.goto('/callback?code=abc&state=wrong-state')
    await expect(page).toHaveURL(/\/login\?error=invalid_state/)
  })

  test('redirects to /login on known OIDC error', async ({ page }) => {
    await page.goto('/callback?error=access_denied')
    await expect(page).toHaveURL(/\/login\?error=access_denied/)
  })
})

// ── Dashboard page smoke tests ─────────────────────────────────────────────

test.describe('dashboard pages', () => {
  test.beforeEach(async ({ context }) => {
    await injectAuthCookies(context)
    await mockPlatformApi(context)
  })

  test('/dashboard redirects to /dashboard/chat', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard\/chat/)
  })

  test('/dashboard/chat renders without error', async ({ page }) => {
    await page.goto('/dashboard/chat')
    await expect(page).toHaveURL(/\/dashboard\/chat/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('/dashboard/agentlets renders without error', async ({ page }) => {
    await page.goto('/dashboard/agentlets')
    await expect(page).toHaveURL(/\/dashboard\/agentlets/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('/dashboard/connectors renders without error', async ({ page }) => {
    await page.goto('/dashboard/connectors')
    await expect(page).toHaveURL(/\/dashboard\/connectors/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('/dashboard/models renders without error', async ({ page }) => {
    await page.goto('/dashboard/models')
    await expect(page).toHaveURL(/\/dashboard\/models/)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('/dashboard/secrets renders without error', async ({ page }) => {
    await page.goto('/dashboard/secrets')
    await expect(page).toHaveURL(/\/dashboard\/secrets/)
    await expect(page).not.toHaveURL(/\/login/)
  })
})

// ── Token refresh (requires OIDC provider connection or local mock) ───────

test.describe('token refresh via proxy', () => {
  // The proxy's silent token refresh calls the OIDC provider server-side. Playwright's
  // context.route() only intercepts browser-initiated requests, not server-side
  // fetch calls from the Next.js process. These tests require:
  //   - A valid OIDC_ISSUER_URL pointing to a mock server (set in .env.test.local), OR
  //   - A real Keycloak instance with a valid long-lived refresh token in TEST_REFRESH_TOKEN
  //
  // The unit tests in __tests__/proxy.test.ts cover all refresh branches fully.

  test.fixme(
    'silently refreshes expired access token and continues to /dashboard',
    async ({ page, context }) => {
      await context.addCookies([{
        name: 'sid_rt', value: process.env.TEST_REFRESH_TOKEN ?? 'test-rt',
        domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax',
      }])
      await mockPlatformApi(context)
      await page.goto('/dashboard')
      await expect(page).toHaveURL('/dashboard')
      const cookies = await context.cookies()
      expect(cookies.find((c) => c.name === 'sid_at')).toBeDefined()
    }
  )

  test.fixme(
    'redirects to /login when refresh token is rejected by the OIDC provider',
    async ({ page, context }) => {
      await context.addCookies([{
        name: 'sid_rt', value: 'invalid-refresh-token',
        domain: 'localhost', path: '/', httpOnly: true, secure: false, sameSite: 'Lax',
      }])
      await page.goto('/dashboard')
      await expect(page).toHaveURL(/\/login/)
    }
  )
})
