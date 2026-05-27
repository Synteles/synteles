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

export interface ConnectorApi {
  name: string
  description?: string
  mcp_config: string
}

const REVALIDATE = '/dashboard/connectors'

export async function listConnectors(): Promise<ConnectorApi[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<{ presets?: ConnectorApi[] } | null>('/api/connectors', {}, token)
    return data?.presets ?? []
  } catch {
    return []
  }
}

export async function createConnector(
  name: string,
  description: string,
  mcpConfig: string,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch('/api/connectors', {
      method: 'POST',
      body: JSON.stringify({ name, description: description || undefined, mcp_config: mcpConfig }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function updateConnector(
  name: string,
  description: string,
  mcpConfig: string,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/connectors/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({ description, mcp_config: mcpConfig }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function deleteConnector(name: string): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/connectors/${encodeURIComponent(name)}`, { method: 'DELETE' }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}
