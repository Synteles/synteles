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

vi.mock('@/lib/oidc-discovery', () => ({
  getOidcConfig: () =>
    Promise.resolve({
      authorization_endpoint: 'http://auth.test.dev/protocol/openid-connect/auth',
      token_endpoint: 'http://auth.test.dev/protocol/openid-connect/token',
      end_session_endpoint: 'http://auth.test.dev/protocol/openid-connect/logout',
    }),
}))

// ── Matcher ────────────────────────────────────────────────────────────────

describe('proxy matcher', () => {
  it('matches /dashboard and sub-routes', () => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard' })).toBe(true)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard/agentlets' })).toBe(true)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/dashboard/chat' })).toBe(true)
  })

  it('does not match public or API paths', () => {
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/login' })).toBe(false)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/callback' })).toBe(false)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/' })).toBe(false)
    expect(unstable_doesMiddlewareMatch({ config, nextConfig: {}, url: '/api/health' })).toBe(false)
  })
})

// ── Proxy function ─────────────────────────────────────────────────────────

describe('proxy function', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

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

  it('passes through when sid_at cookie is present', async () => {
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_at=valid-access-token' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(200)
    expect(res.headers.get('location')).toBeNull()
  })

  it('silently refreshes when sid_rt present but sid_at missing', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'new-at', refresh_token: 'new-rt', expires_in: 3600 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=old-refresh-token' },
    })
    const res = await proxy(req)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://auth.test.dev/protocol/openid-connect/token',
      expect.objectContaining({ method: 'POST' })
    )
    expect(res.status).toBe(200)
    expect(res.cookies.get('sid_at')?.value).toBe('new-at')
    expect(res.cookies.get('sid_rt')?.value).toBe('new-rt')
  })

  it('preserves existing refresh token when OIDC does not rotate it', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'new-at', expires_in: 3600 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=original-rt' },
    })
    const res = await proxy(req)
    expect(res.cookies.get('sid_rt')?.value).toBe('original-rt')
  })

  it('sets id_token cookie when OIDC returns one on refresh', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'at', refresh_token: 'rt', id_token: 'new-id', expires_in: 3600 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=some-rt' },
    })
    const res = await proxy(req)
    expect(res.cookies.get('sid_it')?.value).toBe('new-id')
  })

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

  it('redirects to /login when OIDC refresh returns non-ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('invalid_grant', { status: 400 })
    )
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=expired-token' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/login')
  })

  it('redirects to /login when fetch throws', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network error'))
    const req = new NextRequest('http://localhost/dashboard', {
      headers: { cookie: 'sid_rt=some-token' },
    })
    const res = await proxy(req)
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/login')
  })
})
