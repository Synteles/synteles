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

import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  fetchActiveExecutions,
  getExecution,
  agentletInitials,
  type Execution,
  type ExecutionStatus,
} from '@/lib/executions'

const POLL_MS = 30_000
const MAX_RECENT = 10

interface WatchdogCtx {
  activeRuns: Execution[]
  recentCompleted: Execution[]
}

const Ctx = createContext<WatchdogCtx>({ activeRuns: [], recentCompleted: [] })

export function useWatchdog() {
  return useContext(Ctx)
}

function fireToast(ex: Execution, finalStatus: ExecutionStatus) {
  const label = `${agentletInitials(ex.agentlet_id)}-${ex.execution_id.slice(-6)}`
  if (finalStatus === 'completed') {
    toast.success(`${ex.agentlet_id} completed`, { description: label, id: ex.execution_id })
  } else if (finalStatus === 'failed') {
    toast.error(`${ex.agentlet_id} failed`, { description: label, id: ex.execution_id })
  } else {
    toast.warning(`${ex.agentlet_id} terminated`, { description: label, id: ex.execution_id })
  }
}

export function WatchdogProvider({ children }: { children: React.ReactNode }) {
  const [recentCompleted, setRecentCompleted] = useState<Execution[]>([])
  const prevMap = useRef<Map<string, Execution>>(new Map())
  const queryClient = useQueryClient()

  const { data: activeRuns = [] } = useQuery({
    queryKey: ['executions', 'active'],
    queryFn: fetchActiveExecutions,
    refetchInterval: POLL_MS,
    staleTime: POLL_MS / 2,
  })

  useEffect(() => {
    const current = new Map(activeRuns.map(e => [e.execution_id, e]))
    const prev = prevMap.current

    if (prev.size > 0) {
      for (const [id, ex] of prev) {
        if (!current.has(id)) {
          // Fetch real terminal status before toasting
          getExecution(id).then(final => {
            fireToast(ex, final.status)
            setRecentCompleted(r => [final, ...r].slice(0, MAX_RECENT))
            queryClient.invalidateQueries({ queryKey: ['executions', 'recent'] })
          }).catch(() => {
            // Fallback if the fetch fails
            fireToast(ex, 'completed')
            setRecentCompleted(r =>
              [{ ...ex, status: 'completed' as const }, ...r].slice(0, MAX_RECENT),
            )
            queryClient.invalidateQueries({ queryKey: ['executions', 'recent'] })
          })
        }
      }
    }

    prevMap.current = current
  }, [activeRuns, queryClient])

  return <Ctx value={{ activeRuns, recentCompleted }}>{children}</Ctx>
}
