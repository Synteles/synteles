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
import { getServerToken } from '@/lib/auth'
import { config } from '@/lib/config'

export const dynamic = 'force-dynamic'

export async function GET() {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const res = await fetch(`${config.apiBaseUrl}/api/conversations`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  }).catch((err: unknown) => {
    console.error('[GET /api/conversations] fetch error:', err)
    return null
  })

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  if (!res.ok) {
    console.error(`[GET /api/conversations] backend ${res.status}`)
    return NextResponse.json({ error: `Backend error ${res.status}` }, { status: res.status })
  }

  return NextResponse.json(await res.json())
}

export async function POST(req: NextRequest) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json() as {
    title: string
    display_messages: unknown[]
    agent_state: unknown
  }

  const res = await fetch(`${config.apiBaseUrl}/api/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    cache: 'no-store',
  }).catch((err: unknown) => {
    console.error('[POST /api/conversations] fetch error:', err)
    return null
  })

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  if (!res.ok) {
    console.error(`[POST /api/conversations] backend ${res.status}`)
    return NextResponse.json({ error: `Backend error ${res.status}` }, { status: res.status })
  }

  return NextResponse.json(await res.json(), { status: 201 })
}
