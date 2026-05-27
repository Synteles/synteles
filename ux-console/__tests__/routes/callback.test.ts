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
import { GET } from '@/app/(auth)/callback/route'
import * as auth from '@/lib/auth'

vi.mock('@/lib/auth')

const BASE = 'http://localhost:3000'

function makeRequest(path: string, cookieHeader = '') {
  return new NextRequest(`${BASE}${path}`, {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
  })
}

const VALID_TOKENS = {
  accessToken: 'at-value',
  refreshToken: 'rt-value',
  idToken: 'it-value',
  expiresIn: 3600,
}

beforeEach(() => {
  vi.resetAllMocks()
})

// ── Error param from Cognito ───────────────────────────────────────────────

describe('Cognito error param', () => {
  it.each([
    'access_denied',
    'invalid_request',
    'unauthorized_client',
    'server_error',
    'temporarily_unavailable',
  ])('passes known error %s through unchanged', async (error) => {
    const res = await GET(makeRequest(`/callback?error=${error}`))
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain(`error=${error}`)
  })

  it('maps unknown Cognito errors to auth_error', async () => {
    const res = await GET(makeRequest('/callback?error=something_weird'))
    expect(res.headers.get('location')).toContain('error=auth_error')
    expect(res.headers.get('location')).not.toContain('something_weird')
  })
})

// ── CSRF / state validation ────────────────────────────────────────────────

describe('state validation', () => {
  it('rejects when code is missing', async () => {
    const res = await GET(makeRequest('/callback?state=xyz', 'oauth_state=xyz; pkce_verifier=v'))
    expect(res.headers.get('location')).toContain('error=invalid_state')
  })

  it('rejects when state param is missing', async () => {
    const res = await GET(makeRequest('/callback?code=abc', 'oauth_state=xyz; pkce_verifier=v'))
    expect(res.headers.get('location')).toContain('error=invalid_state')
  })

  it('rejects when stored state cookie is missing', async () => {
    const res = await GET(makeRequest('/callback?code=abc&state=xyz', 'pkce_verifier=v'))
    expect(res.headers.get('location')).toContain('error=invalid_state')
  })

  it('rejects when state param does not match stored state', async () => {
    const res = await GET(
      makeRequest('/callback?code=abc&state=wrong', 'oauth_state=correct; pkce_verifier=v')
    )
    expect(res.headers.get('location')).toContain('error=invalid_state')
  })

  it('rejects when pkce_verifier cookie is missing', async () => {
    const res = await GET(makeRequest('/callback?code=abc&state=xyz', 'oauth_state=xyz'))
    expect(res.headers.get('location')).toContain('error=invalid_state')
  })
})

// ── Happy path ─────────────────────────────────────────────────────────────

describe('successful token exchange', () => {
  beforeEach(() => {
    vi.mocked(auth.exchangeCodeForTokens).mockResolvedValue(VALID_TOKENS)
  })

  it('sets sid_at, sid_rt, sid_it cookies', async () => {
    const res = await GET(
      makeRequest('/callback?code=c&state=s', 'pkce_verifier=v; oauth_state=s')
    )
    expect(res.cookies.get('sid_at')?.value).toBe('at-value')
    expect(res.cookies.get('sid_rt')?.value).toBe('rt-value')
    expect(res.cookies.get('sid_it')?.value).toBe('it-value')
  })

  it('clears pkce_verifier, oauth_state, and auth_next cookies', async () => {
    const res = await GET(
      makeRequest(
        '/callback?code=c&state=s',
        'pkce_verifier=v; oauth_state=s; auth_next=/dashboard/chat'
      )
    )
    // NextResponse.cookies.delete() sets value='' with Max-Age=0
    expect(res.cookies.get('pkce_verifier')?.value).toBe('')
    expect(res.cookies.get('oauth_state')?.value).toBe('')
    expect(res.cookies.get('auth_next')?.value).toBe('')
  })

  it('redirects to /dashboard by default', async () => {
    const res = await GET(
      makeRequest('/callback?code=c&state=s', 'pkce_verifier=v; oauth_state=s')
    )
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('/dashboard')
  })

  it('redirects to NEXT_REDIRECT_COOKIE path when safe', async () => {
    const res = await GET(
      makeRequest(
        '/callback?code=c&state=s',
        'pkce_verifier=v; oauth_state=s; auth_next=/dashboard/agentlets'
      )
    )
    expect(res.headers.get('location')).toContain('/dashboard/agentlets')
  })

  it('falls back to /dashboard for unsafe auth_next values', async () => {
    const res = await GET(
      makeRequest(
        '/callback?code=c&state=s',
        'pkce_verifier=v; oauth_state=s; auth_next=//evil.com'
      )
    )
    const loc = res.headers.get('location')!
    expect(loc).toContain('/dashboard')
    expect(loc).not.toContain('evil.com')
  })

  it('falls back to /dashboard when auth_next is a relative path with no leading slash', async () => {
    const res = await GET(
      makeRequest(
        '/callback?code=c&state=s',
        'pkce_verifier=v; oauth_state=s; auth_next=noSlash'
      )
    )
    expect(res.headers.get('location')).toContain('/dashboard')
  })
})

// ── Token exchange failure ─────────────────────────────────────────────────

describe('token exchange failure', () => {
  it('redirects to /login?error=token_exchange_failed when exchange throws', async () => {
    vi.mocked(auth.exchangeCodeForTokens).mockRejectedValue(new Error('Cognito down'))
    const res = await GET(
      makeRequest('/callback?code=c&state=s', 'pkce_verifier=v; oauth_state=s')
    )
    expect(res.status).toBe(307)
    expect(res.headers.get('location')).toContain('error=token_exchange_failed')
  })
})
