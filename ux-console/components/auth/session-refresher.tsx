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

'use client'

import { useEffect, useRef } from 'react'

// How many ms before expiry to proactively refresh
const EARLY_MS = 60_000

function readExpMs(): number {
  const match = document.cookie.match(/(?:^|;\s*)sid_exp=([^;]+)/)
  return match ? parseInt(match[1], 10) : 0
}

// Silently refreshes the access token before it expires so background
// API calls (e.g. watchdog polling) never hit a 401 that would force a
// full-page reload and reset in-memory UI state (e.g. the selected chat
// conversation).
export function SessionRefresher() {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    function schedule() {
      if (timerRef.current) clearTimeout(timerRef.current)
      const expMs = readExpMs()
      if (!expMs) return
      const delay = Math.max(expMs - Date.now() - EARLY_MS, 0)
      timerRef.current = setTimeout(() => { void refresh() }, delay)
    }

    async function refresh() {
      try {
        const res = await fetch('/api/auth/silent-refresh', {
          method: 'POST',
          credentials: 'include',
        })
        if (!res.ok) {
          window.location.href = '/login?error=session_expired'
          return
        }
        schedule()
      } catch {
        // Network hiccup — retry in 30 s
        timerRef.current = setTimeout(() => { void refresh() }, 30_000)
      }
    }

    function onVisibility() {
      if (document.visibilityState !== 'visible') return
      const exp = readExpMs()
      // Refresh immediately if already within the early window or expired
      if (!exp || Date.now() >= exp - EARLY_MS) {
        void refresh()
      } else {
        schedule()
      }
    }

    schedule()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return null
}
