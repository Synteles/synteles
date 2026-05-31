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
import { appOrigin } from '@/lib/config'
import {
  COOKIE_ACCESS,
  COOKIE_REFRESH,
  COOKIE_ID,
  isSafeRedirect,
  setSessionCookies,
} from '@/lib/auth-constants'

function expiredResponse(): NextResponse {
  const url = new URL('/login', appOrigin)
  url.searchParams.set('error', 'session_expired')
  const res = NextResponse.redirect(url)
  res.cookies.delete(COOKIE_ACCESS)
  res.cookies.delete(COOKIE_REFRESH)
  res.cookies.delete(COOKIE_ID)
  return res
}

export async function GET(req: NextRequest) {
  const next = req.nextUrl.searchParams.get('next')
  const destination = next && isSafeRedirect(next) ? next : '/dashboard'

  const refreshToken = req.cookies.get(COOKIE_REFRESH)?.value
  if (!refreshToken) return expiredResponse()

  const tokens = await refreshAccessToken(refreshToken)
  if (!tokens) return expiredResponse()

  const response = NextResponse.redirect(new URL(destination, appOrigin))
  setSessionCookies(response, tokens)
  return response
}
