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

const mockOidcConfig = {
  authorization_endpoint: 'http://kc.test/protocol/openid-connect/auth',
  token_endpoint: 'http://kc.test/protocol/openid-connect/token',
  end_session_endpoint: 'http://kc.test/protocol/openid-connect/logout',
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.resetModules()
})

describe('getOidcConfig', () => {
  it('fetches and returns OIDC discovery document', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockOidcConfig), { status: 200 })
    )
    const { getOidcConfig } = await import('@/lib/oidc-discovery')
    const config = await getOidcConfig()
    expect(config.token_endpoint).toBe('http://kc.test/protocol/openid-connect/token')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/.well-known/openid-configuration')
    )
  })

  it('throws when discovery endpoint returns non-OK', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Not Found', { status: 404 })
    )
    const { getOidcConfig } = await import('@/lib/oidc-discovery')
    await expect(getOidcConfig()).rejects.toThrow('OIDC discovery failed: 404')
  })

  it('caches the result and only calls fetch once', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockOidcConfig), { status: 200 })
    )
    const { getOidcConfig } = await import('@/lib/oidc-discovery')
    await getOidcConfig()
    await getOidcConfig()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
