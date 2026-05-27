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

export interface SecretApi {
  name: string
  description?: string
  key_count?: number
  created_at?: string
  updated_at?: string
}

export interface SecretDetailApi {
  name: string
  description?: string
  key_names?: string[]
  value?: Record<string, string>
}

const REVALIDATE = '/dashboard/secrets'

export async function listSecrets(): Promise<SecretApi[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<SecretApi[] | null>('/api/secrets', {}, token)
    return data ?? []
  } catch {
    return []
  }
}

export async function getSecretDetail(
  name: string,
): Promise<SecretDetailApi | { error: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    const data = await apiFetch<SecretDetailApi>(
      `/api/secrets/${encodeURIComponent(name)}?reveal_value=true`,
      {},
      token,
    )
    return data
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function createSecret(
  name: string,
  description: string,
  value: Record<string, string>,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch('/api/secrets', {
      method: 'POST',
      body: JSON.stringify({ name, value, description: description || undefined }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function updateSecret(
  name: string,
  description: string,
  value: Record<string, string>,
): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/secrets/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify({ value, description }),
    }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function deleteSecret(name: string): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/secrets/${encodeURIComponent(name)}`, { method: 'DELETE' }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}
