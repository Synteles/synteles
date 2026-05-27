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

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ToolCall {
  id: string
  name: string
  done: boolean
}

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools: ToolCall[]
  ts: string // ISO string
}

export interface AgentState {
  messages: unknown[]
  manager_state: Record<string, unknown>
}

export interface ConversationMeta {
  conversation_id: string
  title: string
  created_at: string
  updated_at?: string
}

export interface ConversationFull extends ConversationMeta {
  display_messages: DisplayMessage[]
  agent_state: AgentState
}

// ── Client-side API (calls Next.js proxy routes) ──────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'include', ...init })
  if (!res.ok) {
    const body = await res.json().catch(() => null) as { error?: string } | null
    throw new Error(body?.error ?? `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

export async function listConversations(): Promise<ConversationMeta[]> {
  const data = await apiFetch<{ conversations?: ConversationMeta[] }>('/api/conversations')
  return (data.conversations ?? []).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )
}

export async function getConversation(id: string): Promise<ConversationFull> {
  return apiFetch<ConversationFull>(`/api/conversations/${encodeURIComponent(id)}`)
}

export async function createConversation(
  title: string,
  displayMessages: DisplayMessage[],
  agentState: AgentState,
): Promise<ConversationMeta> {
  return apiFetch<ConversationMeta>('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, display_messages: displayMessages, agent_state: agentState }),
  })
}

export async function updateConversation(
  id: string,
  patch: { title?: string; display_messages?: DisplayMessage[]; agent_state?: AgentState },
): Promise<void> {
  await apiFetch<void>(`/api/conversations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
}

export async function deleteConversation(id: string): Promise<void> {
  await apiFetch<void>(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
