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

export async function POST(req: NextRequest) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json() as {
    agentlet_id: string
    prompt?: string
    timeout?: number
    input_objects?: string[]
  }

  // POST /api/executions — agentlet_id + params in body; org_id resolved from OIDC token server-side
  const res = await fetch(`${config.apiBaseUrl}/api/executions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  }).catch((err: unknown) => {
    console.error('[POST /api/executions] fetch error:', err)
    return null
  })

  if (!res) {
    return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })
  }

  const text = await res.text()

  if (!res.ok) {
    console.error(`[POST /api/executions] backend ${res.status}:`, text)
    let detail: string
    try {
      detail = (JSON.parse(text) as { message?: string; error?: string }).message
        ?? (JSON.parse(text) as { message?: string; error?: string }).error
        ?? text
    } catch {
      detail = text || `Backend error ${res.status}`
    }
    return NextResponse.json({ error: detail }, { status: res.status })
  }

  // 202 Accepted — parse the body if present, otherwise return an empty object
  let result: Record<string, unknown> = {}
  if (text) {
    try {
      result = JSON.parse(text) as Record<string, unknown>
    } catch {
      // body was not JSON — still a success, just no execution_id in response
    }
  }

  return NextResponse.json(result, { status: 202 })
}
