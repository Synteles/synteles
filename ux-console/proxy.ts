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
import { config as appConfig } from '@/lib/config'
import { getOidcConfig } from '@/lib/oidc-discovery'
import { COOKIE_ACCESS, COOKIE_ID, COOKIE_REFRESH, REFRESH_TOKEN_MAX_AGE } from '@/lib/auth-constants'

const PUBLIC_PATHS = ['/login', '/callback', '/logout']

function isSafeRedirect(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//')
}

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  const accessToken = req.cookies.get(COOKIE_ACCESS)?.value
  const refreshToken = req.cookies.get(COOKIE_REFRESH)?.value

  if (accessToken) {
    return NextResponse.next()
  }

  if (refreshToken) {
    try {
      const { token_endpoint } = await getOidcConfig()
      const body = new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: appConfig.oidcClientId,
        client_secret: appConfig.oidcClientSecret,
        refresh_token: refreshToken,
      })

      const res = await fetch(token_endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })

      if (res.ok) {
        const data = await res.json()
        const response = NextResponse.next()
        const cookieOpts = {
          httpOnly: true,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'lax' as const,
          path: '/',
        }
        response.cookies.set(COOKIE_ACCESS, data.access_token, {
          ...cookieOpts,
          maxAge: data.expires_in,
        })
        if (!data.refresh_token) {
          console.warn('OIDC refresh: response missing refresh_token, reusing existing token')
        }
        response.cookies.set(COOKIE_REFRESH, data.refresh_token ?? refreshToken, {
          ...cookieOpts,
          maxAge: REFRESH_TOKEN_MAX_AGE,
        })
        if (data.id_token) {
          response.cookies.set(COOKIE_ID, data.id_token, { ...cookieOpts, maxAge: REFRESH_TOKEN_MAX_AGE })
        }
        return response
      }
    } catch {
      // fall through to redirect
    }
  }

  const loginUrl = new URL('/login', new URL(appConfig.redirectUri).origin)
  if (isSafeRedirect(pathname)) {
    loginUrl.searchParams.set('next', pathname)
  }
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
