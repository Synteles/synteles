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

import React, { useEffect, useState } from 'react'
import * as jsYaml from 'js-yaml'
import { Bot, ArrowDown, RefreshCw } from 'lucide-react'
import { getAgentletYaml } from '@/app/(dashboard)/dashboard/agentlets/actions'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

interface AgentletModel {
  provider?: string
  model_id?: string
}

interface SubAgentlet {
  name: string
  description?: string
  tools?: string[]
  model?: AgentletModel
}

interface SwarmParticipant {
  name: string
  count?: number
  description?: string
  tools?: string[]
  model?: AgentletModel
}

interface SwarmConfig {
  entry_point?: string
  participants?: SwarmParticipant[]
}

interface ParsedAgentlet {
  agentlet?: { name?: string }
  model?: AgentletModel
  tools?: string[]
  sub_agentlets?: SubAgentlet[]
  swarm?: SwarmConfig
}

type PatternType =
  | 'multi-agent'
  | 'combined-swarm'
  | 'swarm-panel'
  | 'dynamic-swarm'
  | 'single'

// ── Helpers ────────────────────────────────────────────────────────────────

function shortenModelId(modelId: string | undefined): string | null {
  if (!modelId) return null
  // Strip long ARN paths — show only last segment after the final "/"
  const parts = modelId.split('/')
  return parts[parts.length - 1] ?? modelId
}

const PATTERN_LABELS: Record<PatternType, string | null> = {
  'multi-agent':    'Orchestrator',
  'swarm-panel':    'Swarm',
  'combined-swarm': 'Swarm · Dynamic',
  'dynamic-swarm':  'Swarm · Dynamic',
  'single':         null,
}

function detectPattern(parsed: ParsedAgentlet): PatternType {
  const hasSubAgentlets = Array.isArray(parsed.sub_agentlets) && parsed.sub_agentlets.length > 0
  const hasParticipants = Array.isArray(parsed.swarm?.participants) && (parsed.swarm?.participants?.length ?? 0) > 0
  const hasSwarmTool = Array.isArray(parsed.tools) && parsed.tools.includes('swarm')

  if (hasSubAgentlets) return 'multi-agent'
  if (hasParticipants && hasSwarmTool) return 'combined-swarm'
  if (hasParticipants) return 'swarm-panel'
  if (hasSwarmTool) return 'dynamic-swarm'
  return 'single'
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ToolPill({ name }: { name: string }) {
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-mono bg-surface border border-border text-faint">
      {name}
    </span>
  )
}

function SkeletonPulse() {
  return (
    <div className="flex flex-col gap-2 animate-pulse">
      <div className="h-3 w-24 rounded bg-surface" />
      <div className="h-16 rounded-lg bg-surface" />
      <div className="h-4 w-32 rounded bg-surface" />
      <div className="grid grid-cols-2 gap-2">
        <div className="h-20 rounded-lg bg-surface" />
        <div className="h-20 rounded-lg bg-surface" />
      </div>
    </div>
  )
}

// ── Shared primitives ─────────────────────────────────────────────────────

function AgentCard({
  name,
  model,
  description,
  tools,
  count,
  role,
}: {
  name: string
  model?: string | null
  description?: string
  tools?: string[]
  count?: number
  role?: string
}) {
  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-border bg-surface p-3">
      <div className="flex items-center gap-1.5 min-w-0">
        <Bot size={12} className="text-muted flex-none" />
        <span className="text-[11px] font-semibold text-foreground truncate">{name}</span>
        {count && count > 1 && (
          <span className="text-[10px] text-faint flex-none font-mono">×{count}</span>
        )}
        {role && (
          <span className="ml-auto text-[10px] text-faint flex-none">{role}</span>
        )}
      </div>
      {model && (
        <p className="font-mono text-[10px] text-faint truncate pl-[21px]">{model}</p>
      )}
      {description && (
        <p className="text-[10px] text-muted leading-relaxed line-clamp-2 pl-[21px]">{description}</p>
      )}
      {tools && tools.length > 0 && (
        <div className="flex flex-wrap gap-1 pl-[21px]">
          {tools.map(t => <ToolPill key={t} name={t} />)}
        </div>
      )}
    </div>
  )
}

function Connector({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center gap-1.5 px-1">
      <Icon size={11} className="text-faint flex-none" />
      <span className="text-[10px] text-faint">{label}</span>
    </div>
  )
}

function AgentGrid({ children, count }: { children: React.ReactNode; count: number }) {
  return (
    <div className={cn('grid gap-2', count === 1 ? 'grid-cols-1' : 'grid-cols-2')}>
      {children}
    </div>
  )
}

// ── Multi-agent diagram ────────────────────────────────────────────────────

function MultiAgentDiagram({ parsed }: { parsed: ParsedAgentlet }) {
  const subAgentlets = parsed.sub_agentlets ?? []
  const orchestratorModel = shortenModelId(parsed.model?.model_id)

  return (
    <div className="flex flex-col gap-2">
      <AgentCard
        name={parsed.agentlet?.name ?? 'orchestrator'}
        model={orchestratorModel}
        role="orchestrator"
      />
      <Connector icon={ArrowDown} label="calls as tools" />
      <AgentGrid count={subAgentlets.length}>
        {subAgentlets.map(agent => {
          const agentModel = shortenModelId(agent.model?.model_id)
          return (
            <AgentCard
              key={agent.name}
              name={agent.name}
              model={agentModel !== orchestratorModel ? agentModel : null}
              description={agent.description}
              tools={agent.tools}
            />
          )
        })}
      </AgentGrid>
    </div>
  )
}

// ── Swarm panel diagram ────────────────────────────────────────────────────

function SwarmPanelDiagram({ parsed, isDynamic }: { parsed: ParsedAgentlet; isDynamic: boolean }) {
  const participants = parsed.swarm?.participants ?? []
  const defaultModel = shortenModelId(parsed.model?.model_id)
  const entryParticipant = participants.find(p => p.name === parsed.swarm?.entry_point) ?? participants[0]
  const peers = participants.filter(p => p !== entryParticipant)
  const connectorLabel = isDynamic ? 'peer handoffs · swarm + dynamic' : 'peer handoffs · swarm'

  function resolveModel(p: SwarmParticipant) {
    return shortenModelId(p.model?.model_id) ?? defaultModel
  }

  return (
    <div className="flex flex-col gap-2">
      {entryParticipant && (
        <AgentCard
          name={entryParticipant.name}
          model={resolveModel(entryParticipant)}
          tools={entryParticipant.tools}
          count={entryParticipant.count}
          role="entry"
        />
      )}
      {peers.length > 0 && <Connector icon={RefreshCw} label={connectorLabel} />}
      {peers.length > 0 && (
        <AgentGrid count={peers.length}>
          {peers.map(p => (
            <AgentCard
              key={p.name}
              name={p.name}
              model={resolveModel(p)}
              description={p.description}
              tools={p.tools}
              count={p.count}
            />
          ))}
        </AgentGrid>
      )}
    </div>
  )
}

// ── Dynamic swarm diagram ──────────────────────────────────────────────────

function DynamicSwarmDiagram({ parsed }: { parsed: ParsedAgentlet }) {
  return (
    <div className="flex flex-col gap-2">
      <AgentCard
        name={parsed.agentlet?.name ?? 'orchestrator'}
        model={shortenModelId(parsed.model?.model_id)}
        role="dynamic swarm"
      />
      <div className="flex items-center gap-1.5 px-1">
        <RefreshCw size={11} className="text-faint flex-none" />
        <span className="text-[10px] text-faint">assembles agent team at runtime</span>
      </div>
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────

export function AgentSchemaView({ agentletId }: { agentletId: string }) {
  const [loading, setLoading] = useState(true)
  const [parsed, setParsed] = useState<ParsedAgentlet | null>(null)
  const [pattern, setPattern] = useState<PatternType>('single')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setParsed(null)

    getAgentletYaml(agentletId).then(result => {
      if (cancelled) return
      setLoading(false)
      if ('error' in result) return
      try {
        const doc = jsYaml.load(result.yaml) as ParsedAgentlet
        if (!doc || typeof doc !== 'object') return
        const p = detectPattern(doc)
        setParsed(doc)
        setPattern(p)
      } catch {
        // silently swallow parse errors — just don't render
      }
    })

    return () => { cancelled = true }
  }, [agentletId])

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium text-foreground-2">Structure</p>
        <SkeletonPulse />
      </div>
    )
  }

  if (!parsed || pattern === 'single') return null

  const typeLabel = PATTERN_LABELS[pattern]

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <p className="text-xs font-medium text-foreground-2">Structure</p>
        {typeLabel && (
          <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted">
            {typeLabel}
          </span>
        )}
      </div>

      {pattern === 'multi-agent' && (
        <MultiAgentDiagram parsed={parsed} />
      )}

      {(pattern === 'swarm-panel' || pattern === 'combined-swarm') && (
        <SwarmPanelDiagram parsed={parsed} isDynamic={pattern === 'combined-swarm'} />
      )}

      {pattern === 'dynamic-swarm' && (
        <DynamicSwarmDiagram parsed={parsed} />
      )}
    </div>
  )
}
