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

type Params = { params: Promise<{ id: string }> }

export async function GET(_req: NextRequest, { params }: Params) {
  const { id } = await params
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const res = await fetch(
    `${config.apiBaseUrl}/api/conversations/${encodeURIComponent(id)}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
  ).catch(() => null)

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  if (!res.ok) return NextResponse.json({ error: `Backend error ${res.status}` }, { status: res.status })

  const meta = await res.json() as {
    conversation_id: string
    title: string
    created_at: string
    updated_at?: string
    // Backend returns either presigned URLs or inline data
    display_url?: string
    agent_state_url?: string
    display_messages?: unknown[]
    agent_state?: unknown
  }

  if (meta.display_url || meta.agent_state_url) {
    const [displayRes, stateRes] = await Promise.all([
      meta.display_url ? fetch(meta.display_url).catch(() => null) : null,
      meta.agent_state_url ? fetch(meta.agent_state_url).catch(() => null) : null,
    ])
    return NextResponse.json({
      conversation_id: meta.conversation_id,
      title: meta.title,
      created_at: meta.created_at,
      updated_at: meta.updated_at,
      display_messages: displayRes?.ok ? await displayRes.json() : [],
      agent_state: stateRes?.ok ? await stateRes.json() : { messages: [], manager_state: {} },
    })
  }

  return NextResponse.json(meta)
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const { id } = await params
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const res = await fetch(
    `${config.apiBaseUrl}/api/conversations/${encodeURIComponent(id)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(await req.json()),
      cache: 'no-store',
    },
  ).catch(() => null)

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  if (!res.ok) return NextResponse.json({ error: `Backend error ${res.status}` }, { status: res.status })

  return new NextResponse(null, { status: 204 })
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { id } = await params
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const res = await fetch(
    `${config.apiBaseUrl}/api/conversations/${encodeURIComponent(id)}`,
    { method: 'DELETE', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
  ).catch(() => null)

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  if (!res.ok) return NextResponse.json({ error: `Backend error ${res.status}` }, { status: res.status })

  return new NextResponse(null, { status: 204 })
}
