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

import { NextRequest, NextResponse } from 'next/server'
import { generatePkce, generateState } from '@/lib/pkce'
import { config as appConfig } from '@/lib/config'
import { getOidcConfig } from '@/lib/oidc-discovery'
import { PKCE_VERIFIER_COOKIE, OAUTH_STATE_COOKIE, NEXT_REDIRECT_COOKIE } from '@/lib/auth-constants'

export async function GET(req: NextRequest) {
  const { codeVerifier, codeChallenge } = await generatePkce()
  const state = generateState()
  const { authorization_endpoint } = await getOidcConfig()

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: appConfig.oidcClientId,
    redirect_uri: appConfig.redirectUri,
    scope: 'openid email profile',
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  })
  const authUrl = `${authorization_endpoint}?${params}`

  const response = NextResponse.redirect(authUrl)
  const cookieOpts = {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    path: '/',
    maxAge: 60 * 10,
  }
  response.cookies.set(PKCE_VERIFIER_COOKIE, codeVerifier, cookieOpts)
  response.cookies.set(OAUTH_STATE_COOKIE, state, cookieOpts)

  const next = req.nextUrl.searchParams.get('next')
  if (next && next.startsWith('/') && !next.startsWith('//')) {
    response.cookies.set(NEXT_REDIRECT_COOKIE, next, cookieOpts)
  }

  return response
}
