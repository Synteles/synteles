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

// Minimal OIDC provider stub for Playwright e2e tests.
//
// The Next.js server calls the OIDC token endpoint server-side during the
// /api/auth/refresh and /callback flows. Playwright's context.route() only
// intercepts browser-initiated requests, so we need a real HTTP server that
// the Next.js process can reach.
//
// Token-endpoint behaviour:
//   grant_type=refresh_token, refresh_token=invalid-refresh-token → 400
//   grant_type=refresh_token, anything else                        → 200 with fresh tokens
//   grant_type=authorization_code                                  → 200 with fresh tokens

import * as http from 'node:http'

export const MOCK_OIDC_PORT = 4444
export const MOCK_OIDC_ISSUER = `http://localhost:${MOCK_OIDC_PORT}`

const DISCOVERY = {
  issuer: MOCK_OIDC_ISSUER,
  authorization_endpoint: `${MOCK_OIDC_ISSUER}/auth`,
  token_endpoint: `${MOCK_OIDC_ISSUER}/token`,
  end_session_endpoint: `${MOCK_OIDC_ISSUER}/logout`,
}

const FRESH_TOKENS = {
  access_token: 'mock-at',
  refresh_token: 'mock-rt',
  id_token: 'mock-it',
  expires_in: 3600,
  token_type: 'Bearer',
}

function handleToken(req: http.IncomingMessage, res: http.ServerResponse) {
  let body = ''
  req.on('data', (chunk: Buffer) => { body += chunk.toString() })
  req.on('end', () => {
    const params = new URLSearchParams(body)
    const grantType = params.get('grant_type')

    if (grantType === 'refresh_token' && params.get('refresh_token') === 'invalid-refresh-token') {
      res.writeHead(400, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: 'invalid_grant' }))
      return
    }

    if (grantType === 'refresh_token' || grantType === 'authorization_code') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(FRESH_TOKENS))
      return
    }

    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'unsupported_grant_type' }))
  })
}

export function startOidcMock(): Promise<http.Server> {
  const server = http.createServer((req, res) => {
    const { pathname } = new URL(req.url ?? '/', MOCK_OIDC_ISSUER)

    if (req.method === 'GET' && pathname === '/.well-known/openid-configuration') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(DISCOVERY))
      return
    }

    if (req.method === 'POST' && pathname === '/token') {
      handleToken(req, res)
      return
    }

    // /auth and /logout — tests stop at the 302 before following these redirects,
    // so they never actually reach the stub. Return 200 as a safety net.
    res.writeHead(200)
    res.end()
  })

  return new Promise((resolve, reject) => {
    server.listen(MOCK_OIDC_PORT, '127.0.0.1', () => resolve(server))
    server.once('error', reject)
  })
}
