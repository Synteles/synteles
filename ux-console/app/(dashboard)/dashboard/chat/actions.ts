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
import { getServerToken } from '@/lib/auth'
import { apiFetch } from '@/lib/api-client'
import type { ConversationMeta } from '@/lib/conversations'

export async function listConversations(): Promise<ConversationMeta[]> {
  const token = await getServerToken()
  if (!token) return []
  try {
    const data = await apiFetch<{ conversations?: ConversationMeta[] } | null>(
      '/api/conversations',
      {},
      token,
    )
    return (data?.conversations ?? []).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )
  } catch {
    return []
  }
}
