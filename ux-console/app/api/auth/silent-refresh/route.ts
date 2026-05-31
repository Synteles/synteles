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
import { COOKIE_REFRESH, setSessionCookies } from '@/lib/auth-constants'

// Called by SessionRefresher before the access token expires.
// Returns JSON (no redirect) so the client can stay on the current page.
export async function POST(req: NextRequest) {
  const refreshToken = req.cookies.get(COOKIE_REFRESH)?.value
  if (!refreshToken) {
    return NextResponse.json({ ok: false }, { status: 401 })
  }

  const tokens = await refreshAccessToken(refreshToken)
  if (!tokens) {
    return NextResponse.json({ ok: false }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  setSessionCookies(res, tokens)
  return res
}
