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
import { getServerToken, getOrgId } from '@/lib/auth'
import { config } from '@/lib/config'

export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  const [token, orgId] = await Promise.all([getServerToken(), getOrgId()])
  if (!token || !orgId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json() as {
    message: string
    messages?: unknown[]
    manager_state?: Record<string, unknown>
    pending_input_objects?: string[]
  }

  const ac = new AbortController()
  req.signal.addEventListener('abort', () => ac.abort())

  const upstream = await fetch(config.chatStreamUrl, {
    method: 'POST',
    cache: 'no-store',
    signal: ac.signal,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      message: body.message,
      messages: body.messages,
      manager_state: body.manager_state,
      pending_input_objects: body.pending_input_objects,
      org_id: orgId,
    }),
  }).catch((err: unknown) => {
    console.error('[POST /api/chat/stream] fetch error:', err)
    return null
  })

  if (!upstream) {
    return NextResponse.json({ error: 'Chat service unreachable' }, { status: 502 })
  }

  if (!upstream.ok || !upstream.body) {
    console.error(`[POST /api/chat/stream] upstream ${upstream.status}`)
    return NextResponse.json({ error: `Upstream error ${upstream.status}` }, { status: upstream.status })
  }

  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
      Connection: 'keep-alive',
    },
  })
}
