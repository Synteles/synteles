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

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'
import { proxy, config } from '@/proxy'
import { unstable_doesMiddlewareMatch } from 'next/experimental/testing/server'

// ── Matcher ────────────────────────────────────────────────────────────────

describe('proxy matcher', () => {
  it('matches /dashboard and sub-routes', () => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard' })).toBe(true)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard/agentlets' })).toBe(true)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard/chat' })).toBe(true)
  })

  it('matches /api routes', () => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/api/health' })).toBe(true)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/api/conversations' })).toBe(true)
  })

  it('does not match public page routes', () => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/login' })).toBe(false)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/callback' })).toBe(false)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/' })).toBe(false)
  })
})

// ── Proxy function ─────────────────────────────────────────────────────────

describe('proxy function', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  // ── Unprotected pass-through ─────────────────────────────────────────────

  it('passes through /login without checking cookies', async () => {
    const req = new NextRequest('http://localhost/login')
    const res = await proxy(req)
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  it('passes through /callback', async () => {
    const req = new NextRequest('http://localhost/callback?code=abc&state=xyz')
    const res = await proxy(req)
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  it('passes through /logout', async () => {
    const req = new NextRequest('http://localhost/logout')
    const res = await proxy(req)
    expect(res.status).toBe(200)
  })

  it('passes through /api/auth/refresh', async () => {
    const req = new NextRequest('http://localhost/api/auth/refresh')
    const res = await proxy(req)
    expect(res.status).toBe(200)
  })

  it('passes through /api/health', async () => {
    const req = new NextRequest('http://localhost/api/health')
    const res = await proxy(req)
    expect(res.status).toBe(200)
  })

  // ── Authenticated pass-through ───────────────────────────────────────────

  it('passes through when sid_at cookie is present', async () => {
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_at=valid-access-token' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  // ── Token refresh delegation ─────────────────────────────────────────────

  it('redirects to /api/auth/refresh with next param when sid_rt present but sid_at missing', async () => {
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=some-refresh-token' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(307)
    const location = res.headers.get('location')!
    expect(location).toContain('/api/auth/refresh')
    expect(location).toContain('next=')
    expect(location).toContain('%2Fdashboard')
  })

  it('preserves full path and query string in next param when delegating refresh', async () => {
    const req = new NextRequest('http://localhost/dashboard/agentlets?tab=active', {
      headers: { cookie: 'sid_rt=some-rt' },
    })
    const res = await proxy(req)
    const location = res.headers.get('location')!
    expect(location).toContain('/api/auth/refresh')
    expect(decodeURIComponent(location)).toContain('/dashboard/agentlets?tab=active')
  })

  // ── API 401 ──────────────────────────────────────────────────────────────

  it('returns 401 JSON for API paths when unauthenticated (no cookies)', async () => {
    const req = new NextRequest('http://localhost/api/conversations')
    const res = await proxy(req)
    expect(res.status).toBe(401)
    expect(await res.json()).toEqual({ error: 'Unauthorized' })
  })

  it('returns 401 for API paths even when sid_rt is present', async () => {
    // Client-side 401 handler (client-fetch.ts) does window.location.href to
    // /api/auth/refresh — the proxy must not redirect API calls itself to avoid
    // fetch() silently following a chain to the login page (200 HTML).
    const req = new NextRequest('http://localhost/api/conversations', {
      headers: { cookie: 'sid_rt=some-rt' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(401)
  })

  // ── Unauthenticated page redirect ────────────────────────────────────────

  it('redirects to /login with next param when unauthenticated', async () => {
    const req = new NextRequest('http://localhost/dashboard/agentlets')
    const res = await proxy(req)
    expect(res.status).toBe(307)
    const location = res.headers.get('location')!
    expect(location).toContain('/login')
    expect(location).toContain('next=')
    expect(location).toContain('%2Fdashboard%2Fagentlets')
  })

  it('redirects to /login without next param for unsafe paths', async () => {
    const req = new NextRequest('http://localhost//evil.com')
    const res = await proxy(req)
    expect(res.status).toBe(307)
    const location = res.headers.get('location')!
    expect(location).toContain('/login')
    expect(location).not.toContain('next=')
  })
})
