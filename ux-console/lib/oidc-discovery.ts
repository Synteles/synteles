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

interface OidcConfig {
  authorization_endpoint: string
  token_endpoint: string
  end_session_endpoint?: string
}

const TTL_MS = 5 * 60 * 1000

let cached: Promise<OidcConfig> | null = null
let cachedAt = 0

// When running inside Docker, OIDC_ISSUER_URL points to the internal Keycloak
// address so the discovery fetch succeeds. Keycloak in dev mode returns its own
// host in the discovery doc, so we rewrite endpoints explicitly:
//   - authorization_endpoint / end_session_endpoint → OIDC_PUBLIC_BASE  (browser redirects)
//   - token_endpoint                                → OIDC_INTERNAL_BASE (server-side fetch)
function rewriteOrigin(url: string, newBase: string | undefined): string {
  if (!newBase) return url
  try {
    const src = new URL(url)
    const base = new URL(newBase)
    src.protocol = base.protocol
    src.host = base.host
    return src.toString()
  } catch {
    return url
  }
}

export function getOidcConfig(): Promise<OidcConfig> {
  if (cached && Date.now() - cachedAt < TTL_MS) return cached
  cached = null
  cached = fetch(
    `${process.env.OIDC_ISSUER_URL}/.well-known/openid-configuration`
  )
    .then(async (res) => {
      if (!res.ok) {
        cached = null
        throw new Error(`OIDC discovery failed: ${res.status}`)
      }
      const data = await res.json()
      if (
        typeof data.authorization_endpoint !== 'string' ||
        typeof data.token_endpoint !== 'string'
      ) {
        cached = null
        throw new Error('OIDC discovery: invalid document shape')
      }
      cachedAt = Date.now()
      return {
        authorization_endpoint: rewriteOrigin(data.authorization_endpoint, process.env.OIDC_PUBLIC_BASE),
        token_endpoint: rewriteOrigin(data.token_endpoint, process.env.OIDC_INTERNAL_BASE),
        end_session_endpoint: data.end_session_endpoint
          ? rewriteOrigin(data.end_session_endpoint, process.env.OIDC_PUBLIC_BASE)
          : undefined,
      } as OidcConfig
    })
    .catch((err) => {
      cached = null
      throw err
    })
  return cached
}
