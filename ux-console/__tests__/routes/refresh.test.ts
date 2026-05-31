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
import { GET } from '@/app/api/auth/refresh/route'
import * as auth from '@/lib/auth'

vi.mock('@/lib/auth')

const BASE = 'http://localhost:3000'

function makeRequest(path: string, cookieHeader = '') {
  return new NextRequest(`${BASE}${path}`, {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  })
}

const VALID_TOKENS = {
  accessToken: 'new-at',
  refreshToken: 'new-rt',
  idToken: 'new-it',
  expiresIn: 3600,
}

beforeEach(() => {
  vi.resetAllMocks()
})

// ── No refresh token ──────────────────────────────────────────────────────

describe('no refresh token', () => {
  it('redirects to /login?error=session_expired when sid_rt cookie is absent', async () => {
    const res = await GET(makeRequest('/api/auth/refresh'))
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/login')
    expect(res.headers.get('location')).toContain('error=session_expired')
  })

  it('clears all session cookies when sid_rt is absent', async () => {
    const res = await GET(makeRequest('/api/auth/refresh'))
    // NextResponse.cookies.delete() sets value='' with Max-Age=0
    expect(res.cookies.get('sid_at')?.value).toBe('')
    expect(res.cookies.get('sid_rt')?.value).toBe('')
    expect(res.cookies.get('sid_it')?.value).toBe('')
  })

  it('does not call refreshAccessToken when there is no refresh cookie', async () => {
    await GET(makeRequest('/api/auth/refresh'))
    expect(vi.mocked(auth.refreshAccessToken)).not.toHaveBeenCalled()
  })
})

// ── Refresh token rejected ────────────────────────────────────────────────

describe('refresh token rejected', () => {
  beforeEach(() => {
    vi.mocked(auth.refreshAccessToken).mockResolvedValue(null)
  })

  it('redirects to /login?error=session_expired when OIDC rejects the token', async () => {
    const res = await GET(makeRequest('/api/auth/refresh', 'sid_rt=invalid-rt'))
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/login')
    expect(res.headers.get('location')).toContain('error=session_expired')
  })

  it('clears all session cookies on rejected refresh', async () => {
    const res = await GET(makeRequest('/api/auth/refresh', 'sid_rt=invalid-rt'))
    expect(res.cookies.get('sid_at')?.value).toBe('')
    expect(res.cookies.get('sid_rt')?.value).toBe('')
    expect(res.cookies.get('sid_it')?.value).toBe('')
  })
})

// ── Successful refresh ────────────────────────────────────────────────────

describe('successful refresh', () => {
  beforeEach(() => {
    vi.mocked(auth.refreshAccessToken).mockResolvedValue(VALID_TOKENS)
  })

  it('redirects to /dashboard by default when no next param', async () => {
    const res = await GET(makeRequest('/api/auth/refresh', 'sid_rt=old-rt'))
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/dashboard')
  })

  it('redirects to the safe next param destination', async () => {
    const res = await GET(makeRequest('/api/auth/refresh?next=/dashboard/agentlets', 'sid_rt=old-rt'))
    expect(res.headers.get('location')).toContain('/dashboard/agentlets')
  })

  it('falls back to /dashboard for a protocol-relative next param', async () => {
    const res = await GET(makeRequest('/api/auth/refresh?next=//evil.com', 'sid_rt=old-rt'))
    const loc = res.headers.get('location')!
    expect(loc).toContain('/dashboard')
    expect(loc).not.toContain('evil.com')
  })

  it('falls back to /dashboard for a next param without a leading slash', async () => {
    const res = await GET(makeRequest('/api/auth/refresh?next=noSlash', 'sid_rt=old-rt'))
    expect(res.headers.get('location')).toContain('/dashboard')
  })

  it('sets sid_at, sid_rt, and sid_it cookies with the new tokens', async () => {
    const res = await GET(makeRequest('/api/auth/refresh', 'sid_rt=old-rt'))
    expect(res.cookies.get('sid_at')?.value).toBe('new-at')
    expect(res.cookies.get('sid_rt')?.value).toBe('new-rt')
    expect(res.cookies.get('sid_it')?.value).toBe('new-it')
  })

  it('passes the sid_rt cookie value to refreshAccessToken', async () => {
    await GET(makeRequest('/api/auth/refresh', 'sid_rt=my-refresh-token'))
    expect(vi.mocked(auth.refreshAccessToken)).toHaveBeenCalledWith('my-refresh-token')
  })
})
