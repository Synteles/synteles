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

// Next.js 16+ replaces middleware.ts with proxy.ts (middleware.ts is deprecated).
// The exported function must be named `proxy` instead of `middleware`.
// The config.matcher, NextRequest, and NextResponse APIs are unchanged.
import { NextRequest, NextResponse } from 'next/server'
import { COOKIE_ACCESS, COOKIE_REFRESH, isSafeRedirect } from '@/lib/auth-constants'

const UNPROTECTED = ['/api/auth/refresh', '/api/health']

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (UNPROTECTED.some(p => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  const hasAccess = !!req.cookies.get(COOKIE_ACCESS)?.value
  if (hasAccess) return NextResponse.next()

  // API calls must always get 401, never a redirect. fetch() follows redirects
  // silently — if the refresh chain fails it ends up at the login page (200 HTML)
  // which the client can't parse as JSON, producing a generic error toast.
  // The client-side 401 handler does window.location.href to /api/auth/refresh
  // which is a full page navigation and handles both success and failure correctly.
  if (pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const hasRefresh = !!req.cookies.get(COOKIE_REFRESH)?.value
  const dest = pathname + req.nextUrl.search

  if (hasRefresh) {
    // For page navigations: redirect through the refresh route. It will set new
    // cookies and send the user to their original destination on success, or to
    // /login?error=session_expired on failure.
    const refreshUrl = new URL('/api/auth/refresh', req.url)
    if (isSafeRedirect(dest) && dest !== '/') refreshUrl.searchParams.set('next', dest)
    return NextResponse.redirect(refreshUrl)
  }

  const loginUrl = new URL('/login', req.url)
  if (isSafeRedirect(dest) && dest !== '/login') loginUrl.searchParams.set('next', dest)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: ['/dashboard/:path*', '/api/:path*'],
}
