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

export interface ModelPresetApi {
  name: string
  description?: string
  provider: string
  model_id: string
  secret_name?: string
  created_at?: string
}

const REVALIDATE = '/dashboard/models'

export async function listModelPresets(): Promise<ModelPresetApi[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<ModelPresetApi[] | { presets: ModelPresetApi[] } | null>('/api/models', {}, token)
    if (!data) return []
    if (Array.isArray(data)) return data
    return (data as { presets: ModelPresetApi[] }).presets ?? []
  } catch {
    return []
  }
}

export async function listSecretNames(): Promise<string[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<{ name: string }[] | null>('/api/secrets', {}, token)
    return (data ?? []).map(s => s.name).filter(Boolean)
  } catch {
    return []
  }
}

export async function createModelPreset(
  name: string,
  provider: string,
  modelId: string,
  description?: string,
  secretName?: string,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch('/api/models', {
      method: 'POST',
      body: JSON.stringify({
        name,
        provider,
        model_id: modelId,
        description: description || undefined,
        secret_name: secretName || undefined,
      }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function updateModelPreset(
  name: string,
  provider: string,
  modelId: string,
  description: string,
  secretName?: string,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/models/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        provider,
        model_id: modelId,
        description,
        secret_name: secretName || undefined,
      }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function deleteModelPreset(name: string): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/models/${encodeURIComponent(name)}`, { method: 'DELETE' }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}
