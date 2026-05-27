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

export type ExecutionStatus =
  | 'deploying'
  | 'running'
  | 'completed'
  | 'failed'
  | 'terminated'

export interface Execution {
  execution_id: string
  agentlet_id: string
  status: ExecutionStatus
  created_at: string
  completed_at?: string | null
  elapsed_seconds?: number | null
  prompt?: string | null
  logs_s3_uri?: string | null
}

export interface ExecutionFile {
  name: string
  size?: number
  download_url: string
}

export interface ExecutionFiles {
  input_files: ExecutionFile[]
  output_zip?: { exists: boolean; download_url: string | null } | null
}

export interface UploadSlot {
  name: string
  s3_uri: string
  upload_url: string
  upload_fields: Record<string, string>
}

export function agentletInitials(id: string): string {
  return id
    .split(/[_\-]/)
    .map(w => w[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, 2)
}

export function isActive(status: ExecutionStatus): boolean {
  return status === 'running' || status === 'deploying'
}

export function isTerminal(status: ExecutionStatus): boolean {
  return status === 'completed' || status === 'failed' || status === 'terminated'
}

// ── Client-side API (calls our Next.js proxy route handlers) ─────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'include', ...init })
  if (!res.ok) {
    const body = await res.json().catch(() => null) as { error?: string } | null
    throw new Error(body?.error ?? `Request failed: ${res.status}`)
  }
  if (res.status === 202) {
    return res.json() as Promise<T>
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

export async function fetchActiveExecutions(): Promise<Execution[]> {
  const data = await apiFetch<{ executions?: Execution[] }>('/api/executions/active')
  return data.executions ?? []
}

export async function fetchRecentExecutions(): Promise<Execution[]> {
  const data = await apiFetch<{ executions?: Execution[] }>('/api/executions/recent')
  return data.executions ?? []
}

export async function getExecution(id: string): Promise<Execution> {
  return apiFetch<Execution>(`/api/executions/${encodeURIComponent(id)}`)
}

export async function getExecutionLogs(id: string): Promise<{ logs: string | null; pending?: boolean }> {
  const res = await fetch(`/api/executions/${encodeURIComponent(id)}/logs`, { credentials: 'include' })
  if (res.status === 202) return { logs: null, pending: true }
  if (!res.ok) return { logs: '' }
  return res.json() as Promise<{ logs: string | null }>
}

export async function getExecutionFiles(id: string): Promise<ExecutionFiles> {
  return apiFetch<ExecutionFiles>(`/api/executions/${encodeURIComponent(id)}/files`)
}

export async function cancelExecution(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/api/executions/${encodeURIComponent(id)}`, { method: 'POST' })
}

export async function createFileUploadSession(
  fileNames: string[],
): Promise<{ upload_id: string; files: UploadSlot[] }> {
  return apiFetch<{ upload_id: string; files: UploadSlot[] }>('/api/files', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files: fileNames.map(name => ({ name })) }),
  })
}

export async function launchExecution(params: {
  agentlet_id: string
  prompt?: string
  timeout?: number
  input_objects?: string[]
}): Promise<{ execution_id: string }> {
  return apiFetch<{ execution_id: string }>('/api/executions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}
