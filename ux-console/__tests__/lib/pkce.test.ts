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

import { describe, it, expect } from 'vitest'
import { generatePkce, generateState } from '@/lib/pkce'

describe('generatePkce', () => {
  it('returns a codeVerifier and codeChallenge', async () => {
    const { codeVerifier, codeChallenge } = await generatePkce()
    expect(typeof codeVerifier).toBe('string')
    expect(typeof codeChallenge).toBe('string')
    expect(codeVerifier.length).toBeGreaterThan(0)
    expect(codeChallenge.length).toBeGreaterThan(0)
  })

  it('produces base64url-safe strings (no +, /, = characters)', async () => {
    const { codeVerifier, codeChallenge } = await generatePkce()
    expect(codeVerifier).toMatch(/^[A-Za-z0-9\-_]+$/)
    expect(codeChallenge).toMatch(/^[A-Za-z0-9\-_]+$/)
  })

  it('codeChallenge is SHA-256 of codeVerifier base64url-encoded', async () => {
    const { codeVerifier, codeChallenge } = await generatePkce()
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(codeVerifier))
    const expected = Buffer.from(digest)
      .toString('base64')
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '')
    expect(codeChallenge).toBe(expected)
  })

  it('generates unique values on each call', async () => {
    const [a, b] = await Promise.all([generatePkce(), generatePkce()])
    expect(a.codeVerifier).not.toBe(b.codeVerifier)
    expect(a.codeChallenge).not.toBe(b.codeChallenge)
  })
})

describe('generateState', () => {
  it('returns a non-empty base64url string', () => {
    const state = generateState()
    expect(state).toMatch(/^[A-Za-z0-9\-_]+$/)
    expect(state.length).toBeGreaterThan(0)
  })

  it('generates unique values on each call', () => {
    expect(generateState()).not.toBe(generateState())
  })
})
