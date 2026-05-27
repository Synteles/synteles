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
import { cookies } from 'next/headers'
import { exchangeCodeForTokens, getServerToken, getUser } from '@/lib/auth'

vi.mock('@/lib/oidc-discovery', () => ({
  getOidcConfig: () =>
    Promise.resolve({
      authorization_endpoint: 'http://auth.test.dev/protocol/openid-connect/auth',
      token_endpoint: 'http://auth.test.dev/protocol/openid-connect/token',
      end_session_endpoint: 'http://auth.test.dev/protocol/openid-connect/logout',
    }),
}))

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('exchangeCodeForTokens', () => {
  it('returns a TokenSet on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'at',
          refresh_token: 'rt',
          id_token: 'it',
          expires_in: 3600,
          token_type: 'Bearer',
        }),
        { status: 200 }
      )
    )
    const tokens = await exchangeCodeForTokens('code123', 'verifier456')
    expect(tokens).toEqual({ accessToken: 'at', refreshToken: 'rt', idToken: 'it', expiresIn: 3600 })
  })

  it('calls the OIDC token endpoint with correct params', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'a', refresh_token: 'r', id_token: 'i', expires_in: 3600 }),
        { status: 200 }
      )
    )
    await exchangeCodeForTokens('my-code', 'my-verifier')
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('auth.test.dev/protocol/openid-connect/token')
    expect(String(init?.body)).toContain('code=my-code')
    expect(String(init?.body)).toContain('code_verifier=my-verifier')
    expect(String(init?.body)).toContain('grant_type=authorization_code')
  })

  it('throws when the response is not ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('invalid_grant', { status: 400 })
    )
    await expect(exchangeCodeForTokens('bad', 'verifier')).rejects.toThrow('Token exchange failed')
  })

  it('throws when response is missing refresh_token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ access_token: 'at', id_token: 'it', expires_in: 3600 }),
        { status: 200 }
      )
    )
    await expect(exchangeCodeForTokens('code', 'verifier')).rejects.toThrow(
      'did not return a refresh token'
    )
  })
})

describe('getServerToken', () => {
  it('returns null when no sid_at cookie is set', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as never)
    expect(await getServerToken()).toBeNull()
  })

  it('returns the access token value from sid_at cookie', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: 'my-access-token' }),
    } as never)
    expect(await getServerToken()).toBe('my-access-token')
  })
})

describe('getUser', () => {
  it('returns null when there is no access token', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as never)
    expect(await getUser()).toBeNull()
  })

  it('returns null when the API call fails', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: 'token' }),
    } as never)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Unauthorized', { status: 401 })
    )
    expect(await getUser()).toBeNull()
  })

  it('builds full name and initials from given_name + family_name', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: 'token' }),
    } as never)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          sub: 'u-1',
          email: 'alice@example.com',
          given_name: 'Alice',
          family_name: 'Smith',
          org_id: 'org-1',
          org_name: 'Acme',
        }),
        { status: 200 }
      )
    )
    const user = await getUser()
    expect(user).toMatchObject({
      name: 'Alice Smith',
      email: 'alice@example.com',
      initials: 'AS',
      orgId: 'org-1',
      orgName: 'Acme',
      userId: 'u-1',
    })
  })

  it('falls back to email as name when given/family names are absent', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: 'token' }),
    } as never)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ sub: 'u-2', email: 'bob@example.com' }),
        { status: 200 }
      )
    )
    const user = await getUser()
    expect(user?.name).toBe('bob@example.com')
    expect(user?.initials).toBe('B')
  })

  it('uses name field when given/family names are absent but name is present', async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue({ value: 'token' }),
    } as never)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ sub: 'u-3', email: 'c@x.com', name: 'Charlie Brown' }),
        { status: 200 }
      )
    )
    const user = await getUser()
    expect(user?.name).toBe('Charlie Brown')
  })
})
