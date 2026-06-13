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

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  const body = await req.json() as { input: string }

  const res = await fetch(
    `${config.apiBaseUrl}/api/executions/${encodeURIComponent(id)}/signal`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    },
  ).catch(() => null)

  if (!res) return NextResponse.json({ error: 'Backend unreachable' }, { status: 502 })

  const text = await res.text()
  if (!res.ok) {
    let detail = text
    try { detail = (JSON.parse(text) as { detail?: string }).detail ?? text } catch { /* raw */ }
    return NextResponse.json({ error: detail }, { status: res.status })
  }

  return NextResponse.json(text ? JSON.parse(text) : { ok: true }, { status: 202 })
}
