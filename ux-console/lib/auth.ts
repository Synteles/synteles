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

import { cookies } from 'next/headers'
import { config } from './config'
import { getOidcConfig } from './oidc-discovery'
import { apiFetch } from './api-client'
import { COOKIE_ACCESS } from './auth-constants'

export interface TokenSet {
  accessToken: string
  refreshToken: string
  idToken: string
  expiresIn: number
}

export interface UserInfo {
  name: string
  email: string
  initials: string
  orgName: string | null
  userId: string | null
  orgId: string | null
}

export interface MeProfile {
  sub: string
  email: string
  name?: string
  given_name?: string
  family_name?: string
  org_id?: string
  org_name?: string
}

export interface OidcTokenResponse {
  access_token: string
  refresh_token?: string
  id_token: string
  expires_in: number
  token_type: string
}

export async function exchangeCodeForTokens(code: string, codeVerifier: string): Promise<TokenSet> {
  const { token_endpoint } = await getOidcConfig()

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: config.oidcClientId,
    client_secret: config.oidcClientSecret,
    code,
    redirect_uri: config.redirectUri,
    code_verifier: codeVerifier,
  })

  const res = await fetch(token_endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Token exchange failed: ${err}`)
  }

  const data: OidcTokenResponse = await res.json()
  if (!data.refresh_token) throw new Error('Token exchange did not return a refresh token')
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    idToken: data.id_token,
    expiresIn: data.expires_in,
  }
}

export async function getServerToken(): Promise<string | null> {
  const cookieStore = await cookies()
  return cookieStore.get(COOKIE_ACCESS)?.value ?? null
}

export async function refreshAccessToken(refreshToken: string): Promise<TokenSet | null> {
  try {
    const { token_endpoint } = await getOidcConfig()
    const body = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: config.oidcClientId,
      client_secret: config.oidcClientSecret,
      refresh_token: refreshToken,
    })
    const res = await fetch(token_endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!res.ok) return null
    const data: OidcTokenResponse = await res.json()
    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token ?? refreshToken,
      idToken: data.id_token,
      expiresIn: data.expires_in,
    }
  } catch {
    return null
  }
}

export async function getMe(): Promise<MeProfile | null> {
  const token = await getServerToken()
  if (!token) return null
  try {
    return await apiFetch<MeProfile>('/api/users/me', {}, token)
  } catch {
    return null
  }
}

export async function getOrgId(): Promise<string | null> {
  const me = await getMe()
  return me?.org_id ?? null
}

export async function getUser(): Promise<UserInfo | null> {
  const me = await getMe()
  if (!me) return null
  const given = me.given_name ?? ''
  const family = me.family_name ?? ''
  const name = [given, family].filter(Boolean).join(' ') || me.name || me.email || 'User'
  const initials = [given[0], family[0]].filter(Boolean).join('').toUpperCase() || name[0]?.toUpperCase() || '?'
  return {
    name,
    email: me.email ?? '',
    initials,
    orgName: me.org_name ?? null,
    userId: me.sub ?? null,
    orgId: me.org_id ?? null,
  }
}
