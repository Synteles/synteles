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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'include', ...init })
  if (!res.ok) {
    if (res.status === 401) {
      if (typeof window === 'undefined') throw new Error('Unauthorized')
      const next = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.href = `/api/auth/refresh?next=${next}`
      return new Promise<T>(() => {})
    }
    const body = await res.json().catch(() => null) as { error?: string } | null
    throw new Error(body?.error ?? `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}
