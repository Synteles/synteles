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

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { EditorView } from '@codemirror/view'
import { json as jsonLang } from '@codemirror/lang-json'
import { toast } from 'sonner'
import {
  X, Download, WrapText, Square, CheckCircle2, XCircle, Loader2, FileText, Package, Bell, Copy, Check,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useColorScheme } from '@/lib/use-color-scheme'
import {
  getExecution,
  getExecutionLogs,
  getExecutionFiles,
  cancelExecution,
  sendSignal,
  isActive,
  type Execution,
  type ExecutionStatus,
} from '@/lib/executions'
import { ResizablePanel } from '@/components/ui/resizable-panel'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

// ── Status badge ──────────────────────────────────────────────────────────────
const STATUS_MAP: Record<ExecutionStatus, { label: string; cls: string; spin: boolean; icon: typeof Loader2 }> = {
  deploying:          { label: 'Deploying',  cls: 'text-running bg-running-bg border-running-border',   spin: true,  icon: Loader2      },
  running:            { label: 'Running',    cls: 'text-running bg-running-bg border-running-border',   spin: true,  icon: Loader2      },
  waiting_for_signal: { label: 'Waiting', cls: 'text-warning bg-warning-bg border-warning-border', spin: false, icon: Bell },
  completed:          { label: 'Completed',  cls: 'text-success bg-success-bg border-success-border',   spin: false, icon: CheckCircle2 },
  failed:             { label: 'Failed',     cls: 'text-error   bg-error-bg   border-error-border',     spin: false, icon: XCircle      },
  terminated:         { label: 'Terminated', cls: 'text-error   bg-error-bg   border-error-border',     spin: false, icon: XCircle      },
}

function StatusBadge({ status }: { status: ExecutionStatus }) {
  const { label, cls, spin, icon: Icon } = STATUS_MAP[status] ?? STATUS_MAP.failed
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium', cls)}>
      <Icon size={11} className={spin ? 'animate-spin' : ''} />
      {label}
    </span>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${s}s`
  return `${s}s`
}

const editorTheme = EditorView.theme({
  '&': { fontSize: '12px', height: '100%' },
  '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflow: 'auto' },
  '.cm-content': { padding: '8px 0' },
  '.cm-line': { padding: '0 12px' },
  '&.cm-focused': { outline: 'none' },
  '.cm-gutters': { display: 'none' },
})

// ── Signal panel ─────────────────────────────────────────────────────────────
function SignalPanel({
  execution,
  onSignalSent,
}: {
  execution: Execution
  onSignalSent: () => void
}) {
  const [value, setValue] = useState('')
  const qc = useQueryClient()

  const { mutate: submit, isPending } = useMutation({
    mutationFn: () => sendSignal(execution.execution_id, value.trim()),
    onSuccess: () => {
      setValue('')
      qc.invalidateQueries({ queryKey: ['execution', execution.execution_id] })
      qc.invalidateQueries({ queryKey: ['executions', 'active'] })
      onSignalSent()
    },
    onError: () => toast.error('Failed to send response'),
  })

  const canSubmit = value.trim().length > 0 && !isPending

  return (
    <div className="flex-none border-b border-warning-border bg-warning-bg px-6 py-4 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <Bell size={13} className="flex-none text-warning mt-0.5" />
        <p className="text-xs text-warning font-medium leading-relaxed">
          {execution.pending_question ?? 'The agent is waiting for your input.'}
        </p>
      </div>
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && canSubmit) submit()
          }}
          placeholder="Type your response…"
          rows={2}
          className="flex-1 resize-none rounded-lg border border-warning-border bg-card px-3 py-2 text-xs text-foreground placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-warning"
        />
        <button
          onClick={() => submit()}
          disabled={!canSubmit}
          className="flex-none self-end flex items-center gap-1.5 rounded-lg bg-warning px-3 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isPending ? <Loader2 size={11} className="animate-spin" /> : null}
          Send
        </button>
      </div>
      <p className="text-[10px] text-faint">⌘ Enter to send</p>
    </div>
  )
}

const outputEditorTheme = EditorView.theme({
  '&': { fontSize: '12px' },
  '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflow: 'auto' },
  '.cm-content': { padding: '8px 0' },
  '.cm-line': { padding: '0 12px' },
  '&.cm-focused': { outline: 'none' },
  '.cm-gutters': { display: 'none' },
})

function OutputBlock({ text }: { text: string }) {
  const scheme = useColorScheme()
  const [copied, setCopied] = useState(false)

  let pretty: string | null = null
  try { pretty = JSON.stringify(JSON.parse(text), null, 2) } catch { /* not json */ }

  const displayText = pretty ?? text

  function handleCopy() {
    navigator.clipboard.writeText(displayText)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="group relative rounded-xl border border-border overflow-hidden">
      <button
        onClick={handleCopy}
        title="Copy"
        className="absolute top-2 right-2 z-10 flex items-center justify-center rounded-md p-1.5 text-muted bg-surface border border-border opacity-0 group-hover:opacity-100 transition-opacity hover:text-foreground"
      >
        {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
      </button>

      {pretty ? (
        <CodeMirror
          value={pretty}
          theme={scheme === 'dark' ? 'dark' : 'light'}
          extensions={[outputEditorTheme, jsonLang(), EditorView.lineWrapping]}
          editable={false}
          readOnly
          basicSetup={{ lineNumbers: false, foldGutter: false, highlightActiveLine: false }}
        />
      ) : (
        <pre className="bg-surface px-4 py-3 text-xs text-foreground leading-relaxed whitespace-pre-wrap">
          {text}
        </pre>
      )}
    </div>
  )
}

// ── Details tab ───────────────────────────────────────────────────────────────
function DetailsTab({ execution }: { execution: Execution }) {
  const rows = [
    { label: 'Execution ID', value: execution.execution_id, mono: true  },
    { label: 'Status',       value: <StatusBadge status={execution.status} /> },
    { label: 'Started',      value: fmtDate(execution.created_at) },
    { label: 'Completed',    value: fmtDate(execution.completed_at) },
    { label: 'Duration',     value: fmtDuration(execution.elapsed_seconds) },
    ...(execution.workflow_id ? [{ label: 'Workflow ID', value: execution.workflow_id, mono: true }] : []),
  ]

  return (
    <div className="flex flex-col gap-5 px-6 py-5">
      <dl className="flex flex-col divide-y divide-border rounded-xl border border-border overflow-hidden">
        {rows.map(({ label, value, mono }) => (
          <div key={label} className="flex items-start gap-4 px-4 py-3">
            <dt className="w-28 flex-none text-xs text-muted pt-0.5">{label}</dt>
            <dd className={cn('flex-1 text-xs text-foreground break-all', mono && 'font-mono')}>
              {value}
            </dd>
          </div>
        ))}
      </dl>

      {execution.prompt && (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium text-foreground-2">Prompt</p>
          <p className="rounded-xl border border-border bg-surface px-4 py-3 text-xs text-foreground leading-relaxed whitespace-pre-wrap">
            {execution.prompt}
          </p>
        </div>
      )}

      {execution.last_message && (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium text-foreground-2">Output</p>
          <OutputBlock text={execution.last_message} />
        </div>
      )}
    </div>
  )
}

// ── Logs tab ──────────────────────────────────────────────────────────────────
function LogsTab({ executionId, status }: { executionId: string; status: ExecutionStatus }) {
  const [wordWrap, setWordWrap] = useState(false)
  const scheme = useColorScheme()
  const active = isActive(status)

  const { data } = useQuery({
    queryKey: ['execution', executionId, 'logs'],
    queryFn: () => getExecutionLogs(executionId),
    refetchInterval: (q) => {
      if (active) return 5_000
      const d = q.state.data
      // Keep polling until logs land in S3 even after execution terminates
      if (!d || d.pending || d.logs == null) return 5_000
      return false
    },
    staleTime: active ? 4_000 : 60_000,
  })

  const logs = data?.logs
  const pending = data?.pending

  function handleDownload() {
    if (!logs) return
    const blob = new Blob([logs], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${executionId}-logs.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const extensions = [
    editorTheme,
    ...(wordWrap ? [EditorView.lineWrapping] : []),
  ]

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border flex-none">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setWordWrap(v => !v)}
            title="Toggle word wrap"
            className={cn(
              'flex items-center gap-1 rounded px-2 py-1 text-xs transition-colors',
              wordWrap
                ? 'bg-accent-light text-accent border border-accent-border'
                : 'text-muted hover:text-foreground hover:bg-surface border border-transparent',
            )}
          >
            <WrapText size={11} /> Wrap
          </button>
        </div>
        <button
          onClick={handleDownload}
          disabled={!logs}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted hover:text-foreground hover:bg-surface border border-transparent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Download size={11} /> Download
        </button>
      </div>

      {/* Log content */}
      <div className="flex-1 overflow-hidden">
        {pending ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-2 text-muted">
              <Loader2 size={20} className="animate-spin text-running" />
              <p className="text-xs">Logs not yet available…</p>
            </div>
          </div>
        ) : logs == null ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-xs text-faint">No logs</p>
          </div>
        ) : (
          <CodeMirror
            value={logs}
            theme={scheme === 'dark' ? 'dark' : 'light'}
            extensions={extensions}
            editable={false}
            readOnly
            height="100%"
            style={{ height: '100%', fontSize: 12 }}
          />
        )}
      </div>
    </div>
  )
}

// ── Files tab ─────────────────────────────────────────────────────────────────
function FilesTab({ executionId }: { executionId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['execution', executionId, 'files'],
    queryFn: () => getExecutionFiles(executionId),
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 size={20} className="animate-spin text-muted" />
      </div>
    )
  }

  const inputFiles = data?.input_files ?? []
  const outputZip  = data?.output_zip ?? null

  return (
    <div className="flex flex-col gap-5 px-6 py-5">
      {/* Input files */}
      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium text-foreground-2">Input files</p>
        {inputFiles.length === 0 ? (
          <p className="text-xs text-faint">No input files</p>
        ) : (
          <div className="flex flex-col gap-1">
            {inputFiles.map(f => (
              <a
                key={f.name}
                href={f.download_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 hover:border-border-2 transition-colors group"
              >
                <FileText size={13} className="flex-none text-muted" />
                <span className="flex-1 truncate text-xs text-foreground group-hover:text-accent transition-colors">
                  {f.name}
                </span>
                <Download size={12} className="flex-none text-faint" />
              </a>
            ))}
          </div>
        )}
      </div>

      {/* Output zip */}
      {outputZip?.exists && outputZip.download_url && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-foreground-2">Output</p>
          <a
            href={outputZip.download_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg border border-success-border bg-success-bg px-3 py-2 hover:border-success transition-colors group"
          >
            <Package size={13} className="flex-none text-success" />
            <span className="flex-1 text-xs text-success font-medium">output_zip.zip</span>
            <Download size={12} className="flex-none text-success" />
          </a>
        </div>
      )}
    </div>
  )
}

// ── Main sheet ────────────────────────────────────────────────────────────────
type Tab = 'details' | 'logs' | 'files'

interface Props {
  executionId: string | null
  onClose: () => void
}

export function ExecutionDetailSheet({ executionId, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('details')
  const qc = useQueryClient()

  const { data: execution } = useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => getExecution(executionId!),
    enabled: !!executionId,
    refetchInterval: (q) => isActive(q.state.data?.status ?? 'completed') ? 10_000 : false,
  })

  // When the sheet detects a terminal status (active → done), kick the watchdog
  // immediately so it detects the transition and fires the completion toast within
  // its next effect run rather than waiting up to 30s for its own poll cycle.
  const prevActiveRef = useRef<boolean | undefined>(undefined)
  useEffect(() => {
    if (!execution) return
    const nowActive = isActive(execution.status)
    if (prevActiveRef.current === true && !nowActive) {
      qc.invalidateQueries({ queryKey: ['executions', 'active'] })
      qc.invalidateQueries({ queryKey: ['execution', executionId, 'logs'] })
      qc.invalidateQueries({ queryKey: ['execution', executionId, 'files'] })
    }
    prevActiveRef.current = nowActive
  }, [execution?.status, executionId, qc])

  const { mutate: cancel, isPending: cancelling } = useMutation({
    mutationFn: () => cancelExecution(executionId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['execution', executionId] })
      qc.invalidateQueries({ queryKey: ['executions', 'active'] })
      toast.success('Execution cancelled')
    },
    onError: () => toast.error('Could not cancel execution'),
  })

  const tabs: { id: Tab; label: string }[] = [
    { id: 'details', label: 'Details' },
    { id: 'logs',    label: 'Logs'    },
    { id: 'files',   label: 'Files'   },
  ]

  const active = execution ? isActive(execution.status) : false

  return (
    <ResizablePanel open={!!executionId} onBackdropClick={onClose}>
      {/* Header */}
      <div className="flex-none border-b border-border">
        <div className="flex items-center justify-between gap-3 px-6 py-4">
          <div className="flex items-center gap-2.5 min-w-0">
            {execution && <StatusBadge status={execution.status} />}
            <span className="truncate font-mono text-sm font-semibold text-foreground">
              {execution?.agentlet_id ?? '…'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 flex-none">
            {active && execution && (
              <AlertDialog>
                <AlertDialogTrigger
                  disabled={cancelling}
                  className="flex items-center gap-1 rounded-md border border-error-border px-2.5 py-1 text-xs text-error hover:bg-error-bg transition-colors disabled:opacity-50"
                >
                  <Square size={10} fill="currentColor" />
                  {cancelling ? 'Terminating…' : 'Terminate'}
                </AlertDialogTrigger>
                <AlertDialogContent size="sm">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Terminate execution?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will immediately terminate the running agentlet. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction variant="destructive" onClick={() => cancel()}>
                      Terminate
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex px-3">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'px-3 py-2 text-sm font-medium border-b-2 transition-colors',
                tab === t.id
                  ? 'border-accent text-accent'
                  : 'border-transparent text-muted hover:text-foreground-2',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Signal panel — shown when workflow is waiting for user input */}
      {execution?.status === 'waiting_for_signal' && (
        <SignalPanel
          execution={execution}
          onSignalSent={() => setTab('details')}
        />
      )}

      {/* Body */}
      {!execution ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 size={20} className="animate-spin text-muted" />
        </div>
      ) : tab === 'details' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <DetailsTab execution={execution} />
        </div>
      ) : tab === 'logs' ? (
        <div className="flex-1 overflow-hidden">
          <LogsTab executionId={execution.execution_id} status={execution.status} />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          <FilesTab executionId={execution.execution_id} />
        </div>
      )}
    </ResizablePanel>
  )
}
