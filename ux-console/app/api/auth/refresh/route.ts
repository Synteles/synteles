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
import { refreshAccessToken } from '@/lib/auth'
import { config } from '@/lib/config'
import {
  COOKIE_ACCESS,
  COOKIE_REFRESH,
  COOKIE_ID,
  REFRESH_TOKEN_MAX_AGE,
} from '@/lib/auth-constants'

export async function GET(req: NextRequest) {
  const appOrigin = new URL(config.redirectUri).origin
  const next = req.nextUrl.searchParams.get('next')
  const destination =
    next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\')
      ? next
      : '/dashboard'

  const refreshToken = req.cookies.get(COOKIE_REFRESH)?.value
  if (!refreshToken) {
    const url = new URL('/login', appOrigin)
    url.searchParams.set('error', 'session_expired')
    return NextResponse.redirect(url)
  }

  const tokens = await refreshAccessToken(refreshToken)
  if (!tokens) {
    const url = new URL('/login', appOrigin)
    url.searchParams.set('error', 'session_expired')
    const response = NextResponse.redirect(url)
    response.cookies.delete(COOKIE_ACCESS)
    response.cookies.delete(COOKIE_REFRESH)
    response.cookies.delete(COOKIE_ID)
    return response
  }

  const response = NextResponse.redirect(new URL(destination, appOrigin))
  const cookieOpts = {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    path: '/',
  }
  response.cookies.set(COOKIE_ACCESS, tokens.accessToken, { ...cookieOpts, maxAge: tokens.expiresIn })
  response.cookies.set(COOKIE_REFRESH, tokens.refreshToken, { ...cookieOpts, maxAge: REFRESH_TOKEN_MAX_AGE })
  response.cookies.set(COOKIE_ID, tokens.idToken, { ...cookieOpts, maxAge: REFRESH_TOKEN_MAX_AGE })

  return response
}
