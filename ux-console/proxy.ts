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
import { COOKIE_ACCESS, COOKIE_REFRESH } from '@/lib/auth-constants'

const UNPROTECTED = ['/api/auth/refresh', '/api/health']

// Accepts only same-origin relative paths. Rejects protocol-relative URLs
// (//evil.com) and backslash variants (/\evil.com) that some browsers treat
// as absolute redirects.
function isSafeRedirect(p: string): boolean {
  return p.startsWith('/') && !p.startsWith('//') && !p.startsWith('/\\')
}

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (UNPROTECTED.some(p => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  const hasAccess = !!req.cookies.get(COOKIE_ACCESS)?.value
  if (hasAccess) return NextResponse.next()

  const hasRefresh = !!req.cookies.get(COOKIE_REFRESH)?.value
  const dest = pathname + req.nextUrl.search

  if (hasRefresh) {
    // Redirect through the refresh route; it will set new cookies then send the
    // user to their original destination (or /dashboard on success, /login on failure).
    const refreshUrl = new URL('/api/auth/refresh', req.url)
    if (isSafeRedirect(dest) && dest !== '/') refreshUrl.searchParams.set('next', dest)
    return NextResponse.redirect(refreshUrl)
  }

  // No tokens at all.
  if (pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const loginUrl = new URL('/login', req.url)
  if (isSafeRedirect(dest) && dest !== '/login') loginUrl.searchParams.set('next', dest)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: ['/dashboard/:path*', '/api/:path*'],
}
