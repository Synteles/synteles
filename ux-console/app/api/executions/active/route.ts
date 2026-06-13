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

interface ExecutionsResponse {
  executions?: Execution[]
}

export async function GET() {
  const token = await getServerToken()
  if (!token) return NextResponse.json({ executions: [] }, { status: 401 })

  try {
    const [running, deploying, waiting] = await Promise.all([
      apiFetch<ExecutionsResponse | null>('/api/executions?status=running&limit=50', {}, token),
      apiFetch<ExecutionsResponse | null>('/api/executions?status=deploying&limit=50', {}, token),
      apiFetch<ExecutionsResponse | null>('/api/executions?status=waiting_for_signal&limit=50', {}, token),
    ])
    const executions = [
      ...(running?.executions ?? []),
      ...(deploying?.executions ?? []),
      ...(waiting?.executions ?? []),
    ]
    return NextResponse.json({ executions })
  } catch {
    return NextResponse.json({ executions: [] })
  }
}
