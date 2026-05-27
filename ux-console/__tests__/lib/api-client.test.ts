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
import { apiFetch, ApiError } from '@/lib/api-client'

const API_BASE = 'http://localhost:4000'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('apiFetch', () => {
  it('calls the correct URL', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    )
    await apiFetch('/api/users/me', {}, 'token')
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/api/users/me`)
  })

  it('sets Authorization header when token provided', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    )
    await apiFetch('/api/test', {}, 'my-token')
    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer my-token')
  })

  it('omits Authorization header when token is null', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    )
    await apiFetch('/api/test', {}, null)
    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>
    expect(Object.keys(headers)).not.toContain('Authorization')
  })

  it('parses and returns JSON body on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 1, name: 'test' }), { status: 200 })
    )
    const result = await apiFetch<{ id: number; name: string }>('/api/test')
    expect(result).toEqual({ id: 1, name: 'test' })
  })

  it('returns null on 204 No Content', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    const result = await apiFetch('/api/test')
    expect(result).toBeNull()
  })

  it('returns null when content-length is 0', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 200, headers: { 'content-length': '0' } })
    )
    const result = await apiFetch('/api/test')
    expect(result).toBeNull()
  })

  it('throws ApiError on non-2xx response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'Not found' }), { status: 404 })
    )
    await expect(apiFetch('/api/missing')).rejects.toThrow(ApiError)
  })

  it('ApiError carries status code and parsed body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'gone' }), { status: 410 })
    )
    try {
      await apiFetch('/api/gone')
      expect.fail('should have thrown')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).status).toBe(410)
      expect((e as ApiError).body).toEqual({ error: 'gone' })
    }
  })

  it('ApiError body is null when response body is not JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Internal Server Error', { status: 500 })
    )
    try {
      await apiFetch('/api/err')
      expect.fail('should have thrown')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).status).toBe(500)
      expect((e as ApiError).body).toBeNull()
    }
  })
})
