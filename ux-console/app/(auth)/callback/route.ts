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
import { exchangeCodeForTokens } from '@/lib/auth'
import { appOrigin } from '@/lib/config'
import {
  PKCE_VERIFIER_COOKIE,
  OAUTH_STATE_COOKIE,
  NEXT_REDIRECT_COOKIE,
  isSafeRedirect,
  setSessionCookies,
} from '@/lib/auth-constants'

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const error = searchParams.get('error')

  if (error) {
    const KNOWN_OIDC_ERRORS = new Set([
      'access_denied', 'invalid_request', 'unauthorized_client',
      'unsupported_response_type', 'invalid_scope', 'server_error',
      'temporarily_unavailable',
    ])
    const safeError = KNOWN_OIDC_ERRORS.has(error) ? error : 'auth_error'
    return NextResponse.redirect(new URL(`/login?error=${safeError}`, appOrigin))
  }

  const storedState = req.cookies.get(OAUTH_STATE_COOKIE)?.value
  const codeVerifier = req.cookies.get(PKCE_VERIFIER_COOKIE)?.value

  if (!code || !state || !storedState || state !== storedState || !codeVerifier) {
    return NextResponse.redirect(new URL('/login?error=invalid_state', appOrigin))
  }

  try {
    const tokens = await exchangeCodeForTokens(code, codeVerifier)

    const nextPath = req.cookies.get(NEXT_REDIRECT_COOKIE)?.value
    const destination = nextPath && isSafeRedirect(nextPath) ? nextPath : '/dashboard'

    const response = NextResponse.redirect(new URL(destination, appOrigin))
    setSessionCookies(response, tokens)
    response.cookies.delete(PKCE_VERIFIER_COOKIE)
    response.cookies.delete(OAUTH_STATE_COOKIE)
    response.cookies.delete(NEXT_REDIRECT_COOKIE)

    return response
  } catch {
    return NextResponse.redirect(new URL('/login?error=token_exchange_failed', appOrigin))
  }
}
