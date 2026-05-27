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

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params

  // Use raw fetch — apiFetch always JSON.parses the body which breaks plain-text
  // log responses, and 202 is 2xx so apiFetch never throws for it.
  const res = await fetch(
    `${config.apiBaseUrl}/api/executions/${encodeURIComponent(id)}/logs`,
    { headers: { Authorization: `Bearer ${token}` } },
  ).catch(() => null)

  if (!res) return NextResponse.json({ logs: '' })

  if (res.status === 202) {
    return NextResponse.json({ logs: null, pending: true }, { status: 202 })
  }

  if (!res.ok) {
    return NextResponse.json({ logs: '' })
  }

  const text = await res.text()

  // Backend may return plain text or a JSON envelope — handle both.
  let logs = text
  try {
    const parsed = JSON.parse(text) as unknown
    if (typeof parsed === 'string') {
      logs = parsed
    } else if (parsed && typeof parsed === 'object' && 'logs' in parsed) {
      logs = (parsed as { logs: string }).logs ?? ''
    }
  } catch {
    // plain text — use as-is
  }

  return NextResponse.json({ logs })
}
