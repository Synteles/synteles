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

import { useState, useTransition, useEffect, type ReactNode } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import {
  Plus, Search, Zap, Play, Pencil, X, ChevronRight, ChevronDown,
  Clock, CheckCircle2, XCircle, Loader2, Check, Copy,
  ListFilter, ArrowUpDown, Cpu, Workflow,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { AgentletApi, ExecutionApi } from '@/app/(dashboard)/dashboard/agentlets/actions'
import { createAgentlet, updateAgentlet, deleteAgentlet } from '@/app/(dashboard)/dashboard/agentlets/actions'
import { fetchRecentExecutions, type Execution } from '@/lib/executions'
import { useWatchdog } from '@/components/executions/watchdog-provider'
import { YamlEditor } from './yaml-editor'
import { AgentSchemaView } from './agent-schema'
import { ResizablePanel } from '@/components/ui/resizable-panel'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'
import { RunExecutionDialog } from '@/components/executions/run-execution-dialog'
import { useExecutionSheet } from '@/components/executions/execution-sheet-provider'

// ── Types ──────────────────────────────────────────────────────────────────
interface Agentlet {
  id: string
  name: string
  description: string
  createdAt: Date
}

function fromApi(k: AgentletApi): Agentlet {
  return {
    id: k.id,
    name: k.id,
    description: k.description ?? '',
    createdAt: k.created_at ? new Date(k.created_at) : new Date(0),
  }
}

function fmtElapsed(seconds: number | null | undefined): string | null {
  if (seconds == null) return null
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${s}s`
  return `${s}s`
}

// ── Sub-components ─────────────────────────────────────────────────────────
function BackendBadge({ type }: { type?: 'standard' | 'durable' }) {
  if (type === 'durable') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-accent-border bg-accent-light px-2 py-0.5 text-xs font-medium text-accent">
        <Workflow size={10} /> Durable
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-xs font-medium text-muted">
      <Cpu size={10} /> Standard
    </span>
  )
}

function StatusBadge({ status }: { status: ExecutionApi['status'] }) {
  const map: Record<ExecutionApi['status'], { icon: typeof Loader2; label: string; cls: string; spin: boolean }> = {
    running:    { icon: Loader2,      label: 'Running',    cls: 'text-running bg-running-bg border-running-border', spin: true  },
    deploying:  { icon: Loader2,      label: 'Deploying',  cls: 'text-running bg-running-bg border-running-border', spin: true  },
    completed:  { icon: CheckCircle2, label: 'Completed',  cls: 'text-success bg-success-bg border-success-border', spin: false },
    failed:     { icon: XCircle,      label: 'Failed',     cls: 'text-error   bg-error-bg   border-error-border',   spin: false },
    terminated: { icon: XCircle,      label: 'Terminated', cls: 'text-error   bg-error-bg   border-error-border',   spin: false },
  }
  const { icon: Icon, label, cls, spin } = map[status] ?? map.failed
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium', cls)}>
      <Icon size={11} className={spin ? 'animate-spin' : ''} />
      {label}
    </span>
  )
}

function AgentletCard({
  agentlet,
  onEdit,
  onRun,
}: {
  agentlet: Agentlet
  onEdit: () => void
  onRun: () => void
}) {
  return (
    <div className="group relative flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-accent-border hover:shadow-md">
      {/* Header */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex size-8 flex-none items-center justify-center rounded-lg bg-accent-light">
          <Zap size={15} className="text-accent" />
        </div>
        <p className="truncate font-mono text-sm font-semibold text-foreground">{agentlet.name}</p>
      </div>

      {/* Description */}
      <p className="flex-1 text-xs leading-relaxed text-muted line-clamp-2">
        {agentlet.description || <span className="text-faint italic">No description</span>}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          className="flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-border-2 hover:text-foreground"
        >
          <Pencil size={11} /> Edit
        </button>
        <button
          onClick={onRun}
          className="flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-xs text-white transition-colors hover:bg-accent-hover"
        >
          <Play size={11} /> Run
        </button>
      </div>
    </div>
  )
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

type SortField = 'created_at' | 'completed_at' | 'elapsed_seconds'

const SORT_LABELS: Record<SortField, string> = {
  created_at:      'Created',
  completed_at:    'Completed',
  elapsed_seconds: 'Elapsed',
}

const STATUS_OPTIONS = ['all', 'running', 'deploying', 'completed', 'failed', 'terminated'] as const
const STATUS_LABELS: Record<string, string> = {
  all: 'All statuses', running: 'Running', deploying: 'Deploying',
  completed: 'Completed', failed: 'Failed', terminated: 'Terminated',
}

function RunsTable({ runs, onSelect }: {
  runs: Execution[]
  onSelect: (id: string) => void
}) {
  const [agentletFilter, setAgentletFilter] = useState('all')
  const [statusFilter,   setStatusFilter]   = useState('all')
  const [sortBy,  setSortBy]  = useState<SortField>('created_at')
  const [sortAsc, setSortAsc] = useState(false)

  const agentletIds = Array.from(new Set(runs.map(r => r.agentlet_id))).sort()

  const displayed = [...runs]
    .filter(r => agentletFilter === 'all' || r.agentlet_id === agentletFilter)
    .filter(r => statusFilter   === 'all' || r.status       === statusFilter)
    .sort((a, b) => {
      const val = (r: Execution) =>
        sortBy === 'created_at'      ? new Date(r.created_at).getTime() :
        sortBy === 'completed_at'    ? (r.completed_at ? new Date(r.completed_at).getTime() : 0) :
        (r.elapsed_seconds ?? 0)
      return sortAsc ? val(a) - val(b) : val(b) - val(a)
    })

  return (
    <div className="flex flex-col gap-3">
      {/* ── Controls ───────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="flex items-center gap-1 text-xs text-muted select-none mr-1">
          <ListFilter size={13} /> Filter
        </span>

        <Select value={agentletFilter} onValueChange={(v) => setAgentletFilter(v ?? 'all')}>
          <SelectTrigger className="w-44">
            <SelectValue>{agentletFilter === 'all' ? 'All agentlets' : agentletFilter}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All agentlets</SelectItem>
            {agentletIds.map(id => <SelectItem key={id} value={id}>{id}</SelectItem>)}
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? 'all')}>
          <SelectTrigger className="w-36">
            <SelectValue>{STATUS_LABELS[statusFilter]}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map(s => (
              <SelectItem key={s} value={s}>{STATUS_LABELS[s]}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex-1" />

        <span className="flex items-center gap-1 text-xs text-muted select-none mr-1">
          <ArrowUpDown size={13} /> Sort
        </span>

        <Select value={sortBy} onValueChange={v => setSortBy(v as SortField)}>
          <SelectTrigger className="w-32">
            <SelectValue>{SORT_LABELS[sortBy]}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(SORT_LABELS) as SortField[]).map(f => (
              <SelectItem key={f} value={f}>{SORT_LABELS[f]}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button variant="outline" size="sm" onClick={() => setSortAsc(v => !v)}>
          {sortAsc ? 'Asc' : 'Desc'}
        </Button>
      </div>

      {/* ── Table ──────────────────────────────────────────────────────────── */}
      {displayed.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia><Clock size={28} className="text-faint" /></EmptyMedia>
            <EmptyTitle>
              {runs.length === 0 ? 'No runs in the last 30 days' : 'No runs match the current filters'}
            </EmptyTitle>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Agentlet</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Backend</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Created</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Completed</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted">Elapsed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {displayed.map(run => {
                const elapsed = fmtElapsed(run.elapsed_seconds)
                const active  = run.status === 'running' || run.status === 'deploying'
                return (
                  <tr
                    key={run.execution_id}
                    onClick={() => onSelect(run.execution_id)}
                    className="hover:bg-card-hover transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs font-medium text-foreground">{run.agentlet_id}</span>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
                    <td className="px-4 py-3"><BackendBadge type={run.execution_type} /></td>
                    <td className="px-4 py-3 text-xs text-muted">{fmtDate(run.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-muted">{fmtDate(run.completed_at)}</td>
                    <td className="px-4 py-3 text-xs text-muted font-mono">
                      {active ? (
                        <span className="text-running flex items-center gap-1">
                          <Loader2 size={10} className="animate-spin" /> live
                        </span>
                      ) : (elapsed ?? '—')}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── API Integration tab ────────────────────────────────────────────────────
const DEFAULT_API_BASE = 'https://api.synteles.dev'

type DrawerTab = 'properties' | 'api' | 'danger'

function CurlLine({ line }: { line: string }) {
  const parts = line.split(/("https?:\/\/[^"]*"|\$\{[^}]*\})/g)
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith('"http')) return <span key={i} className="text-success">{p}</span>
        if (p.startsWith('${')) return <span key={i} className="text-accent">{p}</span>
        return <span key={i} className="text-foreground-2">{p}</span>
      })}
    </>
  )
}

function CurlBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="group/curl relative rounded-lg border border-border bg-surface overflow-hidden">
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 z-10 flex items-center gap-1 rounded border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted opacity-0 group-hover/curl:opacity-100 transition-opacity hover:text-foreground shadow-sm"
      >
        {copied ? <Check size={10} /> : <Copy size={10} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="overflow-x-auto p-4 text-xs font-mono leading-relaxed">
        {code.split('\n').map((line, i) => (
          <div key={i}><CurlLine line={line} /></div>
        ))}
      </pre>
    </div>
  )
}

function ApiSection({ title, description, children }: {
  title: string
  description: ReactNode
  children: ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-surface transition-colors"
      >
        <ChevronDown size={14} className={cn('text-muted flex-none transition-transform', !open && '-rotate-90')} />
        <span className="text-sm font-medium text-foreground">{title}</span>
      </button>
      {open && (
        <div className="flex flex-col px-4 pb-4 gap-3 border-t border-border">
          <p className="pt-3 text-xs text-muted leading-relaxed">{description}</p>
          {children}
        </div>
      )}
    </div>
  )
}

function IC({ children }: { children: ReactNode }) {
  return (
    <code className="rounded border border-border bg-card px-1 py-0.5 text-[11px] font-mono text-foreground">{children}</code>
  )
}

function ApiIntegrationTab({ agentletName, apiBaseUrl }: { agentletName: string; apiBaseUrl: string }) {
  const getCurl =
    `curl -X GET \\\n  "${apiBaseUrl}/api/public/agentlets/${agentletName}" \\\n  -H "X-API-Key: \${SYNTELES_API_KEY}"`
  const runCurl =
    `curl -X POST \\\n  "${apiBaseUrl}/api/public/agentlets/${agentletName}/executions" \\\n  -H "X-API-Key: \${SYNTELES_API_KEY}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"prompt": "Your task description here", "timeout": 900}'`
  const statusCurl =
    `curl -X GET \\\n  "${apiBaseUrl}/api/public/executions/\${EXECUTION_ID}" \\\n  -H "X-API-Key: \${SYNTELES_API_KEY}"`

  return (
    <div className="flex flex-col gap-4 px-6 py-5">
      <p className="text-sm text-muted leading-relaxed">
        Use the <strong className="text-foreground">Synteles Public API</strong> to interact with this agentlet
        programmatically. Authenticate with your API key in the <IC>X-API-Key</IC> header.
      </p>
      <ApiSection title="Get agentlet definition" description="Retrieve the full YAML configuration of this agentlet.">
        <CurlBlock code={getCurl} />
      </ApiSection>
      <ApiSection
        title="Run agentlet"
        description={<>Start an execution and receive an <IC>execution_id</IC> immediately (async).</>}
      >
        <CurlBlock code={runCurl} />
      </ApiSection>
      <ApiSection
        title="Retrieve execution status"
        description={<>
          Poll the status of an execution using the <IC>execution_id</IC> returned above. Status lifecycle:{' '}
          <IC>deploying</IC> → <IC>running</IC> → <IC>completed</IC> | <IC>failed</IC> | <IC>terminated</IC>.
        </>}
      >
        <CurlBlock code={statusCurl} />
      </ApiSection>
    </div>
  )
}

function DangerZoneTab({ agentletName, onDeleteRequest }: { agentletName: string; onDeleteRequest: () => void }) {
  return (
    <div className="px-6 py-5">
      <div className="flex flex-col rounded-xl border border-error-border p-4 gap-3">
        <p className="text-sm font-medium text-foreground">Delete agentlet</p>
        <p className="text-xs text-muted leading-relaxed">
          Permanently delete <span className="font-mono text-foreground">{agentletName}</span> and all its
          configuration. This action cannot be undone.
        </p>
        <button
          onClick={onDeleteRequest}
          className="rounded-lg border border-error-border px-3 py-1.5 text-sm text-error hover:bg-error-bg transition-colors"
        >
          Delete agentlet…
        </button>
      </div>
    </div>
  )
}

// ── Create / Edit Drawer ───────────────────────────────────────────────────
function AgentletDrawer({
  open,
  initial,
  pending,
  error,
  onClose,
  onSave,
  onDeleteRequest,
  apiBaseUrl,
}: {
  open: boolean
  initial: Agentlet | null
  pending: boolean
  error: string | null
  onClose: () => void
  onSave: (name: string, description: string, executionBackend: 'standard' | 'durable') => void
  onDeleteRequest: () => void
  apiBaseUrl: string
}) {
  const isEdit = !!initial?.id
  const [name, setName]        = useState(initial?.name ?? '')
  const [description, setDesc] = useState(initial?.description ?? '')
  const [executionBackend, setExecutionBackend] = useState<'standard' | 'durable'>('standard')
  const [yamlMode, setYamlMode] = useState(false)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('properties')

  useEffect(() => {
    setName(initial?.name ?? '')
    setDesc(initial?.description ?? '')
    setExecutionBackend('standard')
    setYamlMode(false)
    setDrawerTab('properties')
  }, [initial, open])

  function handleSave() {
    if (!name.trim()) return
    onSave(name.trim(), description.trim(), executionBackend)
  }

  function switchTab(t: DrawerTab) {
    setDrawerTab(t)
    setYamlMode(false)
  }

  const tabs: { id: DrawerTab; label: string }[] = [
    { id: 'properties', label: 'Properties' },
    { id: 'api', label: 'API Integration' },
    { id: 'danger', label: 'Danger zone' },
  ]

  return (
    <ResizablePanel open={open} onBackdropClick={onClose}>
      {yamlMode && initial?.id ? (
        <YamlEditor
          agentletId={initial.id}
          onBack={() => setYamlMode(false)}
          onSaved={() => setYamlMode(false)}
        />
      ) : (
        <>
          {/* Header */}
          <div className="flex-none border-b border-border">
            <div className="flex items-center justify-between px-6 py-4">
              <h2 className="font-semibold text-foreground">{isEdit ? 'Edit agentlet' : 'New agentlet'}</h2>
              <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors">
                <X size={16} />
              </button>
            </div>
            {isEdit && (
              <div className="flex px-3">
                {tabs.map(t => (
                  <button
                    key={t.id}
                    onClick={() => switchTab(t.id)}
                    className={cn(
                      'px-3 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                      drawerTab === t.id
                        ? 'border-accent text-accent'
                        : 'border-transparent text-muted hover:text-foreground-2'
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Body */}
          {isEdit && drawerTab === 'api' ? (
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <ApiIntegrationTab agentletName={initial!.name} apiBaseUrl={apiBaseUrl} />
            </div>
          ) : isEdit && drawerTab === 'danger' ? (
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <DangerZoneTab
                agentletName={initial!.name}
                onDeleteRequest={() => { onClose(); onDeleteRequest() }}
              />
            </div>
          ) : (
            <>
              <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin px-6 py-5 gap-5">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-foreground-2">Name</label>
                  <input
                    value={name}
                    onChange={e => setName(e.target.value)}
                    disabled={isEdit}
                    placeholder="e.g. market-research"
                    className={cn(
                      'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors',
                      isEdit && 'opacity-60 cursor-not-allowed'
                    )}
                  />
                  {!isEdit && (
                    <p className="text-[11px] text-faint">Lowercase letters, numbers, and hyphens only. Cannot be changed after creation.</p>
                  )}
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-foreground-2">Description</label>
                  <textarea
                    rows={2}
                    value={description}
                    onChange={e => setDesc(e.target.value)}
                    placeholder="What does this agentlet do?"
                    className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
                  />
                </div>

                {!isEdit && (
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-medium text-foreground-2">Execution backend</label>
                    <ToggleGroup
                      type="single"
                      value={executionBackend}
                      onValueChange={v => { if (v) setExecutionBackend(v as 'standard' | 'durable') }}
                      className="w-full"
                    >
                      <ToggleGroupItem value="standard" className="flex-1">
                        <Cpu size={13} /> Standard
                      </ToggleGroupItem>
                      <ToggleGroupItem value="durable" className="flex-1">
                        <Workflow size={13} /> Durable
                      </ToggleGroupItem>
                    </ToggleGroup>
                    <div className="rounded-lg border border-border bg-surface px-3 py-2.5 text-[11px] text-muted leading-relaxed">
                      {executionBackend === 'standard' ? (
                        <>
                          <span className="font-medium text-foreground-2">Standard</span> runs your agentlet in a container for the duration of the task.
                          Best for short jobs (seconds to a few minutes) that run without interruption.
                        </>
                      ) : (
                        <>
                          <span className="font-medium text-foreground-2">Durable</span> runs your agentlet as a Temporal workflow — every step is checkpointed,
                          so the run can pause for human input, survive restarts, and safely handle long-running tasks (hours or days).
                        </>
                      )}
                    </div>
                  </div>
                )}

                {isEdit && initial?.id && (
                  <AgentSchemaView agentletId={initial.id} />
                )}

                <div className="flex flex-col rounded-lg border border-border bg-surface p-4 gap-3">
                  <p className="text-xs font-medium text-foreground-2">Configuration</p>
                  <p className="text-xs text-muted">Model, system prompt, and tool configuration are managed in the YAML editor.</p>
                  {isEdit ? (
                    <button
                      onClick={() => setYamlMode(true)}
                      className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
                    >
                      Open YAML editor <ChevronRight size={12} />
                    </button>
                  ) : (
                    <p className="text-[11px] text-faint">Save the agentlet first to edit its YAML configuration.</p>
                  )}
                </div>

                {error && <p className="text-xs text-error">{error}</p>}
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
                <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors">
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!name.trim() || pending}
                  className={cn(
                    'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                    name.trim() && !pending
                      ? 'bg-accent text-white hover:bg-accent-hover'
                      : 'bg-accent-muted text-white/60 cursor-not-allowed'
                  )}
                >
                  {pending ? 'Saving…' : isEdit ? 'Save changes' : 'Create agentlet'}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </ResizablePanel>
  )
}

// ── Delete Confirmation Modal ──────────────────────────────────────────────
function DeleteAgentletModal({
  agentlet,
  open,
  onClose,
  onConfirm,
}: {
  agentlet: Agentlet | null
  open: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const [input, setInput] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const matches = input === (agentlet?.name ?? '')

  useEffect(() => {
    if (open) { setInput(''); setError(null) }
  }, [open])

  function handleConfirm() {
    if (!matches || !agentlet) return
    setError(null)
    startTransition(async () => {
      const result = await deleteAgentlet(agentlet.id)
      if (result.error) { setError(result.error); return }
      onConfirm()
      onClose()
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete agentlet</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete{' '}
            <span className="font-mono bg-accent-light text-accent border border-accent-border px-1.5 py-0.5 rounded">
              {agentlet?.name}
            </span>
            . Type the name to confirm:
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-3">
          <input
            autoFocus={open}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleConfirm() }}
            placeholder={agentlet?.name ?? ''}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-error-focus transition-colors"
          />
          {error && <p className="text-xs text-error">{error}</p>}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!matches || pending}
            variant="destructive"
          >
            {pending ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export function AgentletsPage({ initialData, initialRuns, apiBaseUrl = DEFAULT_API_BASE }: { initialData: AgentletApi[]; initialRuns: ExecutionApi[]; apiBaseUrl?: string }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { activeRuns: liveActiveRuns } = useWatchdog()
  const [tab, setTab]           = useState<'agentlets' | 'runs'>('agentlets')
  const [search, setSearch]     = useState('')
  const [drawerOpen, setDrawer] = useState(false)
  const [editTarget, setEdit]   = useState<Agentlet | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Agentlet | null>(null)
  const [agentlets, setAgentlets] = useState<Agentlet[]>(() => initialData.map(fromApi))
  const [agentletSortField, setAgentletSortField] = useState<'created' | 'name'>('created')
  const [agentletSortAsc,   setAgentletSortAsc]   = useState(false)
  const [runTarget, setRunTarget]   = useState<string | null>(null)
  const [savePending, startSave] = useTransition()
  const { openExecution } = useExecutionSheet()

  useEffect(() => {
    const id = searchParams.get('exec')
    if (id) openExecution(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [saveError, setSaveError] = useState<string | null>(null)

  const { data: runs = initialRuns as unknown as Execution[] } = useQuery({
    queryKey: ['executions', 'recent'],
    queryFn: fetchRecentExecutions,
    refetchInterval: 60_000,
    initialData: initialRuns as unknown as Execution[],
  })

  useEffect(() => {
    setAgentlets(initialData.map(fromApi))
  }, [initialData])

  const filtered = agentlets
    .filter(a =>
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.description.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const cmp = agentletSortField === 'name'
        ? a.name.localeCompare(b.name)
        : a.createdAt.getTime() - b.createdAt.getTime()
      return agentletSortAsc ? cmp : -cmp
    })

  function openCreate() { setEdit(null); setSaveError(null); setDrawer(true) }
  function openEdit(a: Agentlet) { setEdit(a); setSaveError(null); setDrawer(true) }

  function handleSave(name: string, description: string, executionBackend: 'standard' | 'durable' = 'standard') {
    setSaveError(null)
    if (editTarget) {
      setAgentlets(prev => prev.map(a => a.id === editTarget.id ? { ...a, description } : a))
      startSave(async () => {
        const result = await updateAgentlet(editTarget.id, description)
        if (result.error) {
          setSaveError(result.error)
          setAgentlets(prev => prev.map(a => a.id === editTarget.id ? editTarget : a))
          return
        }
        setDrawer(false)
        router.refresh()
      })
    } else {
      const optimistic: Agentlet = { id: name, name, description, createdAt: new Date() }
      setAgentlets(prev => [optimistic, ...prev])
      startSave(async () => {
        const result = await createAgentlet(name, description, executionBackend)
        if (result.error) {
          setSaveError(result.error)
          setAgentlets(prev => prev.filter(a => a.id !== name))
          return
        }
        setDrawer(false)
        router.refresh()
      })
    }
  }

  function handleDeleted(id: string) {
    setAgentlets(prev => prev.filter(a => a.id !== id))
    router.refresh()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <div className="flex items-center gap-1">
            {(['agentlets', 'runs'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors',
                tab === t
                  ? 'bg-surface text-foreground border border-border'
                  : 'text-muted hover:text-foreground-2'
              )}
            >
              {t}
              {t === 'agentlets' && (
                <span className="ml-1.5 rounded-full border border-border bg-surface px-1.5 py-0.5 text-[10px] font-medium text-muted">
                  {agentlets.length}
                </span>
              )}
              {t === 'runs' && (
                <span className={cn(
                  'ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                  liveActiveRuns.length > 0
                    ? 'bg-running-bg text-running'
                    : 'bg-surface text-muted border border-border'
                )}>
                  {liveActiveRuns.length > 0 ? `${liveActiveRuns.length} live` : runs.length}
                </span>
              )}
            </button>
          ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="rounded-lg border border-border bg-card pl-8 pr-3 py-1.5 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus w-44 transition-colors"
            />
          </div>
          <ThemeToggle />
          <button
            onClick={openCreate}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
          >
            <Plus size={14} /> New
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {tab === 'agentlets' && (
          <>
            {/* Sort control */}
            <div className="flex items-center justify-end gap-2 mb-4">
              <span className="flex items-center gap-1 text-xs text-muted select-none">
                <ArrowUpDown size={13} /> Sort
              </span>
              <Select value={agentletSortField} onValueChange={v => setAgentletSortField(v as 'created' | 'name')}>
                <SelectTrigger className="w-32">
                  <SelectValue>{agentletSortField === 'created' ? 'Created' : 'Name'}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="created">Created</SelectItem>
                  <SelectItem value="name">Name</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={() => setAgentletSortAsc(v => !v)}>
                {agentletSortAsc ? 'Asc' : 'Desc'}
              </Button>
            </div>

            {filtered.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyMedia><Zap size={32} className="text-faint" /></EmptyMedia>
                  <EmptyTitle>{search ? `No agentlets matching "${search}"` : 'No agentlets yet'}</EmptyTitle>
                </EmptyHeader>
                {!search && (
                  <EmptyContent>
                    <button onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover transition-colors">
                      Create your first agentlet
                    </button>
                  </EmptyContent>
                )}
              </Empty>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filtered.map(a => (
                  <AgentletCard
                    key={a.id}
                    agentlet={a}
                    onEdit={() => openEdit(a)}
                    onRun={() => setRunTarget(a.id)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {tab === 'runs' && (() => {
          const liveMap = new Map(liveActiveRuns.map(e => [e.execution_id, e]))
          const recentRuns = runs as Execution[]
          const mergedRuns = [
            ...liveActiveRuns.filter(e => !recentRuns.some(r => r.execution_id === e.execution_id)),
            ...recentRuns.map(r => liveMap.get(r.execution_id) ?? r),
          ]
          return <RunsTable runs={mergedRuns} onSelect={openExecution} />
        })()}
      </div>

      {/* Drawer */}
      <AgentletDrawer
        open={drawerOpen}
        initial={editTarget}
        pending={savePending}
        error={saveError}
        onClose={() => setDrawer(false)}
        onSave={handleSave}
        onDeleteRequest={() => { if (editTarget) setDeleteTarget(editTarget) }}
        apiBaseUrl={apiBaseUrl}
      />

      {/* Delete modal */}
      <DeleteAgentletModal
        agentlet={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDeleted(deleteTarget.id)}
      />

      {/* Run dialog */}
      <RunExecutionDialog
        agentletId={runTarget}
        onClose={() => setRunTarget(null)}
      />

    </div>
  )
}
