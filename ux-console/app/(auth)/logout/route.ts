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
import { config } from '@/lib/config'
import { getOidcConfig } from '@/lib/oidc-discovery'
import { COOKIE_ACCESS, COOKIE_ID, COOKIE_REFRESH } from '@/lib/auth-constants'

export async function GET(req: NextRequest) {
  const oidc = await getOidcConfig()
  const base = new URL(config.redirectUri).origin

  let response: NextResponse
  if (oidc.end_session_endpoint) {
    const logoutUrl = new URL(oidc.end_session_endpoint)
    logoutUrl.searchParams.set('client_id', config.oidcClientId)
    logoutUrl.searchParams.set('post_logout_redirect_uri', `${base}/login`)
    response = NextResponse.redirect(logoutUrl)
  } else {
    response = NextResponse.redirect(new URL('/login', base))
  }

  response.cookies.delete(COOKIE_ACCESS)
  response.cookies.delete(COOKIE_REFRESH)
  response.cookies.delete(COOKIE_ID)

  return response
}
