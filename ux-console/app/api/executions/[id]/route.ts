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
import { apiFetch } from '@/lib/api-client'

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  try {
    const data = await apiFetch(`/api/executions/${encodeURIComponent(id)}`, {}, token)
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }
}

export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  try {
    await apiFetch(`/api/executions/${encodeURIComponent(id)}/cancel`, { method: 'POST' }, token)
    return NextResponse.json({ ok: true })
  } catch {
    return NextResponse.json({ error: 'Failed to cancel' }, { status: 500 })
  }
}
