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

export interface ApiKeyApi {
  key_id: string
  key_name: string
  created_at?: string
  last_used?: string
}

const REVALIDATE = '/dashboard/api-keys'

export async function listApiKeys(): Promise<ApiKeyApi[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<ApiKeyApi[] | null>('/api/users/apikeys', {}, token)
    return data ?? []
  } catch {
    return []
  }
}

export async function createApiKey(
  keyName: string,
): Promise<{ key?: string; error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    const data = await apiFetch<{ key_name: string; key: string }>(
      '/api/users/apikeys',
      { method: 'POST', body: JSON.stringify({ key_name: keyName }) },
      token,
    )
    revalidatePath(REVALIDATE)
    return { key: data.key }
  } catch (e) {
    return { error: errMsg(e) }
  }
}

export async function deleteApiKey(keyId: string): Promise<{ error?: string }> {
  const token = await getServerToken()
  if (!token) return { error: 'Not authenticated' }
  try {
    await apiFetch(`/api/users/apikeys/${encodeURIComponent(keyId)}`, { method: 'DELETE' }, token)
    revalidatePath(REVALIDATE)
    return {}
  } catch (e) {
    return { error: errMsg(e) }
  }
}
