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

import { useSidebar } from '@/components/ui/sidebar'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { agentletInitials, type Execution } from '@/lib/executions'
import { useWatchdog } from './watchdog-provider'
import { useExecutionSheet } from './execution-sheet-provider'

// ── Gradient ring around an avatar ───────────────────────────────────────────
function GradientRing({ execution }: { execution: Execution }) {
  const { openExecution } = useExecutionSheet()
  const initials = agentletInitials(execution.agentlet_id)

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            onClick={() => openExecution(execution.execution_id)}
            className="relative size-8 rounded-full flex-shrink-0 cursor-pointer"
          />
        }
      >
        {/* Spinning gradient layer — rotates freely, never contains text */}
        <div
          className="absolute inset-0 rounded-full animate-gradient-ring-spin"
          style={{
            background:
              'conic-gradient(from 0deg, var(--running) 0%, var(--accent) 45%, transparent 65%, transparent 100%)',
          }}
        />
        {/* Inner fill — sibling to the spinner, stays upright */}
        <div className="absolute inset-[2px] rounded-full bg-[var(--sidebar-bg)] flex items-center justify-center text-[10px] font-bold text-[var(--text)] z-10">
          {initials}
        </div>
      </TooltipTrigger>
      <TooltipContent side="right" className="text-xs">
        {execution.agentlet_id}
      </TooltipContent>
    </Tooltip>
  )
}

// ── Completed dot ─────────────────────────────────────────────────────────────
function CompletedDot({ execution }: { execution: Execution }) {
  const { openExecution } = useExecutionSheet()
  const color =
    execution.status === 'completed'
      ? 'var(--success)'
      : 'var(--error)'

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div
            onClick={() => openExecution(execution.execution_id)}
            className="size-2.5 rounded-full flex-shrink-0 cursor-pointer hover:scale-125 transition-transform"
            style={{ background: color }}
          />
        }
      />
      <TooltipContent side="right" className="text-xs">
        {execution.agentlet_id} · {execution.status}
      </TooltipContent>
    </Tooltip>
  )
}

// ── Widget ────────────────────────────────────────────────────────────────────
export function ActiveRunsWidget() {
  const { activeRuns, recentCompleted } = useWatchdog()
  const { state } = useSidebar()
  const collapsed = state === 'collapsed'

  const total = activeRuns.length + recentCompleted.length
  if (total === 0) return null

  // Collapsed: single pulsing dot indicator
  if (collapsed) {
    return (
      <div className="flex justify-center py-2">
        <Tooltip>
          <TooltipTrigger
            render={
              <div className="relative size-2 rounded-full bg-[var(--running)]">
                <div className="absolute inset-0 rounded-full bg-[var(--running)] animate-ping opacity-75" />
              </div>
            }
          />
          <TooltipContent side="right" className="text-xs">
            {activeRuns.length} run{activeRuns.length !== 1 ? 's' : ''} active
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }

  return (
    <div className="border-t border-[var(--sidebar-border)]">
      {/* Active runs section */}
      {activeRuns.length > 0 && (
        <div className="px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
            {activeRuns.length} run{activeRuns.length !== 1 ? 's' : ''} active
          </p>
          <div className="flex flex-wrap gap-2">
            {activeRuns.map(ex => (
              <GradientRing key={ex.execution_id} execution={ex} />
            ))}
          </div>
        </div>
      )}

      {/* Divider between sections when both are visible */}
      {activeRuns.length > 0 && recentCompleted.length > 0 && (
        <div className="mx-3 border-t border-[var(--sidebar-border)]" />
      )}

      {/* Completed runs section */}
      {recentCompleted.length > 0 && (
        <div className="px-3 py-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
            Recent runs
          </p>
          <div className="flex flex-wrap gap-1.5">
            {recentCompleted.map(ex => (
              <CompletedDot key={ex.execution_id} execution={ex} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
