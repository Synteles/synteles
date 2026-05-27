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

import { NextResponse } from 'next/server'
import { getServerToken } from '@/lib/auth'
import { apiFetch } from '@/lib/api-client'
import type { Execution } from '@/lib/executions'

interface ExecutionsResponse { executions?: Execution[] }

export async function GET() {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ executions: [] }, { status: 401 })

  const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    .toISOString().replace(/\.\d+Z$/, 'Z')

  try {
    const data = await apiFetch<ExecutionsResponse | null>(
      `/api/executions?limit=100&created_at_start=${encodeURIComponent(since)}`,
      {},
      token,
    )
    return NextResponse.json({ executions: data?.executions ?? [] })
  } catch {
    return NextResponse.json({ executions: [] })
  }
}
