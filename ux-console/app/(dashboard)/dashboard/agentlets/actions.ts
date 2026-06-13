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

'use server'
import { revalidatePath } from 'next/cache'
import { getServerToken } from '@/lib/auth'
import { apiFetch } from '@/lib/api-client'
import { errMsg } from '@/lib/action-utils'

export interface AgentletApi {
  id: string
  description?: string
  created_at?: string
  execution_backend?: 'standard' | 'durable'
}

export interface ExecutionApi {
  execution_id: string
  agentlet_id: string
  status: 'running' | 'deploying' | 'waiting_for_signal' | 'completed' | 'failed' | 'terminated'
  execution_type?: 'standard' | 'durable'
  created_at: string
  completed_at?: string | null
  elapsed_seconds?: number | null
  prompt?: string | null
  logs_s3_uri?: string | null
}

const REVALIDATE = '/dashboard/agentlets'

const DEFAULT_YAML = `model:
  provider: azure_ai
  model_id: gpt-5.3-chat
system_prompt: |
  You are a helpful assistant.
secrets:
  - default
`

export async function listExecutions(): Promise<ExecutionApi[]> {
  const token = await getServerToken()
  if (!token) return []
  const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().replace(/\.\d+Z$/, 'Z')
  try {
    const data = await apiFetch<{ executions?: ExecutionApi[] } | null>(
      `/api/executions?limit=100&created_at_start=${encodeURIComponent(since)}`,
      {},
      token,
    )
    return data?.executions ?? []
  } catch {
    return []
  }
}

export async function listAgentlets(): Promise<AgentletApi[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<AgentletApi[] | null>('/api/agentlets', {}, token)
    return data ?? []
  } catch (e) {
    console.error('[listAgentlets]', errMsg(e))
    return []
  }
}

export async function getAgentletYaml(
  id: string,
): Promise<{ yaml: string } | { error: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    const data = await apiFetch<{ YAML?: string; id?: string }>(`/api/agentlets/${encodeURIComponent(id)}`, {}, token)
    return { yaml: data?.YAML ?? '' }
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function createAgentlet(
  id: string,
  description: string,
  executionBackend: 'standard' | 'durable' = 'standard',
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch('/api/agentlets', {
      method: 'POST',
      body: JSON.stringify({
        id,
        description: description || undefined,
        YAML: DEFAULT_YAML,
        execution_backend: executionBackend,
      }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function saveAgentletYaml(
  id: string,
  yaml: string,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/agentlets/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ YAML: yaml }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function updateAgentlet(
  id: string,
  description: string,
  executionBackend?: 'standard' | 'durable',
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/agentlets/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        description,
        ...(executionBackend !== undefined && { execution_backend: executionBackend }),
      }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function deleteAgentlet(id: string): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/agentlets/${encodeURIComponent(id)}`, { method: 'DELETE' }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}
