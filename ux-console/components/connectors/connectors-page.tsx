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

import { useState, useEffect, useCallback, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search, Plug, Pencil, X, Terminal, AlertCircle, CheckCircle2, Copy, Check, WandSparkles, WrapText } from 'lucide-react'
import CodeMirror from '@uiw/react-codemirror'
import { json } from '@codemirror/lang-json'
import { EditorView } from '@codemirror/view'
import { cn } from '@/lib/utils'
import type { ConnectorApi } from '@/app/(dashboard)/dashboard/connectors/actions'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { createConnector, updateConnector, deleteConnector } from '@/app/(dashboard)/dashboard/connectors/actions'
import { ResizablePanel } from '@/components/ui/resizable-panel'
import { useColorScheme } from '@/lib/use-color-scheme'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'

const jsonEditorTheme = EditorView.theme({
  '&': { fontSize: '12px', borderRadius: '0.5rem' },
  '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflow: 'auto', borderRadius: '0.5rem' },
  '.cm-content': { padding: '8px 0', minHeight: '220px' },
  '.cm-line': { padding: '0 12px' },
  '&.cm-focused': { outline: 'none' },
})

// ── Types ──────────────────────────────────────────────────────────────────
interface McpServer {
  command: string
  args: string[]
  env?: Record<string, string>
  autoApprove?: string[]
}

interface McpConfig {
  mcpServers: Record<string, McpServer>
}

interface Connector {
  name: string
  description: string
  mcpConfig: McpConfig
  createdAt: Date | null
}

function fromApi(c: ConnectorApi): Connector {
  let mcpConfig: McpConfig = { mcpServers: {} }
  try {
    mcpConfig = JSON.parse(c.mcp_config) as McpConfig
  } catch {
    // mcp_config may be invalid JSON — keep empty default
  }
  return {
    name: c.name,
    description: c.description ?? '',
    mcpConfig,
    createdAt: null,
  }
}

// ── Placeholder JSON template ─────────────────────────────────────────────
const JSON_PLACEHOLDER = `{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "my-mcp-package"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}`

// ── JSON validation ───────────────────────────────────────────────────────
type JsonValidation =
  | { state: 'idle' }
  | { state: 'invalid'; message: string }
  | { state: 'valid'; serverCount: number; servers: Record<string, McpServer> }

function validateMcpJson(raw: string): JsonValidation {
  if (!raw.trim()) return { state: 'idle' }
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch (e) {
    const msg = e instanceof SyntaxError ? e.message : 'Invalid JSON'
    return { state: 'invalid', message: msg }
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return { state: 'invalid', message: 'Root must be a JSON object' }
  }
  const root = parsed as Record<string, unknown>
  if (!('mcpServers' in root)) {
    return { state: 'invalid', message: 'Missing required top-level key "mcpServers"' }
  }
  const servers = root.mcpServers
  if (typeof servers !== 'object' || servers === null || Array.isArray(servers)) {
    return { state: 'invalid', message: '"mcpServers" must be an object' }
  }
  const serverMap = servers as Record<string, McpServer>
  return { state: 'valid', serverCount: Object.keys(serverMap).length, servers: serverMap }
}

// ── Server count pill ────────────────────────────────────────────────────────
function ServersPill({ config }: { config: McpConfig }) {
  const names = Object.keys(config.mcpServers)
  const count = names.length
  return (
    <p className="text-xs text-muted">
      <span className="font-medium text-foreground-2">{count} server{count !== 1 ? 's' : ''}:</span>{' '}
      {names.join(', ')}
    </p>
  )
}

// ── Connector card ────────────────────────────────────────────────────────────
function ConnectorCard({
  connector,
  onEdit,
}: {
  connector: Connector
  onEdit: () => void
}) {
  return (
    <div className="group relative flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-accent-border hover:shadow-md">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex size-8 flex-none items-center justify-center rounded-lg bg-accent-light">
          <Plug size={15} className="text-accent" />
        </div>
        <p className="truncate font-mono text-sm font-semibold text-foreground">{connector.name}</p>
      </div>

      <p className="flex-1 text-xs leading-relaxed text-muted line-clamp-2">
        {connector.description || <span className="text-faint italic">No description</span>}
      </p>

      <ServersPill config={connector.mcpConfig} />

      <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={onEdit}
          className="flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-border-2 hover:text-foreground"
        >
          <Pencil size={11} /> Edit
        </button>
      </div>
    </div>
  )
}

// ── Server preview (inside drawer) ────────────────────────────────────────────
function ServerPreview({ servers }: { servers: Record<string, McpServer> }) {
  const entries = Object.entries(servers)
  if (entries.length === 0) return null

  return (
    <div className="flex flex-col rounded-lg border border-border bg-surface p-4 gap-3">
      <p className="text-xs font-medium text-foreground-2">Preview</p>
      <div className="flex flex-col gap-2.5">
        {entries.map(([sname, srv]) => {
          const envKeys = Object.keys(srv.env ?? {})
          return (
            <div key={sname} className="flex flex-col rounded-md border border-border bg-card px-3 py-2.5 gap-1">
              <div className="flex items-center gap-1.5">
                <Terminal size={11} className="text-faint flex-none" />
                <span className="font-mono text-xs font-semibold text-foreground">{sname}</span>
              </div>
              <p className="font-mono text-[11px] text-muted">
                {srv.command}{srv.args?.length ? ' ' + srv.args.join(' ') : ''}
              </p>
              {envKeys.length > 0 && (
                <p className="text-[11px] text-faint">env: {envKeys.join(', ')}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Delete confirmation modal ─────────────────────────────────────────────────
function DeleteModal({
  connector,
  open,
  onCancel,
  onConfirm,
}: {
  connector: Connector | null
  open: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const [typed, setTyped] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) { setTyped(''); setError(null) }
  }, [open])

  function handleConfirm() {
    if (!connector || typed !== connector.name) return
    setError(null)
    startTransition(async () => {
      const result = await deleteConnector(connector.name)
      if (result.error) { setError(result.error); return }
      onConfirm()
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete connector</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. Type{' '}
            <span className="font-mono font-semibold text-foreground">{connector?.name}</span>{' '}
            to confirm.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-3">
          <input
            autoFocus={open}
            value={typed}
            onChange={e => setTyped(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleConfirm() }}
            placeholder={connector?.name ?? ''}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-error-focus transition-colors"
          />
          {error && <p className="text-xs text-error">{error}</p>}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!connector || typed !== connector.name || pending}
            variant="destructive"
          >
            {pending ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ── Create / Edit Drawer ──────────────────────────────────────────────────────
type ConnectorDrawerTab = 'properties' | 'danger'

function ConnectorDrawer({
  open,
  initial,
  pending,
  error,
  onClose,
  onSave,
  onDeleteRequest,
}: {
  open: boolean
  initial: Connector | null
  pending: boolean
  error: string | null
  onClose: () => void
  onSave: (data: { name: string; description: string; mcpConfig: McpConfig }) => void
  onDeleteRequest: () => void
}) {
  const isEdit = !!initial?.name

  const [name, setName]         = useState(initial?.name ?? '')
  const [description, setDesc]  = useState(initial?.description ?? '')
  const [jsonText, setJsonText] = useState('')
  const [validation, setValidation] = useState<JsonValidation>({ state: 'idle' })
  const [copied, setCopied] = useState(false)
  const [wordWrap, setWordWrap] = useState(false)
  const [drawerTab, setDrawerTab] = useState<ConnectorDrawerTab>('properties')
  const scheme = useColorScheme()

  function handleFormat() {
    try {
      const parsed = JSON.parse(jsonText)
      const formatted = JSON.stringify(parsed, null, 2)
      setJsonText(formatted)
      setValidation(validateMcpJson(formatted))
    } catch { /* leave as-is if invalid */ }
  }

  function handleCopy() {
    navigator.clipboard.writeText(jsonText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  useEffect(() => {
    setName(initial?.name ?? '')
    setDesc(initial?.description ?? '')
    const raw = initial ? JSON.stringify(initial.mcpConfig, null, 2) : ''
    setJsonText(raw)
    setValidation(raw ? validateMcpJson(raw) : { state: 'idle' })
    setDrawerTab('properties')
  }, [initial, open])

  const handleJsonChange = useCallback((val: string) => {
    setJsonText(val)
    setValidation(validateMcpJson(val))
  }, [])

  const isValid = name.trim() !== '' && validation.state === 'valid' && !pending

  function handleSave() {
    if (!isValid || validation.state !== 'valid') return
    onSave({
      name: name.trim(),
      description: description.trim(),
      mcpConfig: { mcpServers: validation.servers },
    })
  }

  const tabs: { id: ConnectorDrawerTab; label: string }[] = [
    { id: 'properties', label: 'Properties' },
    { id: 'danger', label: 'Danger zone' },
  ]

  return (
    <ResizablePanel open={open} onBackdropClick={onClose}>
      {/* Header */}
      <div className="flex-none border-b border-border">
        <div className="flex items-center justify-between px-6 py-4">
          <h2 className="font-semibold text-foreground">{isEdit ? 'Edit connector' : 'New connector'}</h2>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors">
            <X size={16} />
          </button>
        </div>
        {isEdit && (
          <div className="flex px-3">
            {tabs.map(t => (
              <button
                key={t.id}
                onClick={() => setDrawerTab(t.id)}
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

      {/* Danger zone tab */}
      {isEdit && drawerTab === 'danger' ? (
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="flex flex-col rounded-xl border border-error-border p-4 gap-3">
            <p className="text-sm font-medium text-foreground">Delete connector</p>
            <p className="text-xs text-muted leading-relaxed">
              Permanently delete <span className="font-mono text-foreground">{initial!.name}</span> and all its
              configuration. This action cannot be undone.
            </p>
            <button
              onClick={() => { onClose(); onDeleteRequest() }}
              className="rounded-lg border border-error-border px-3 py-1.5 text-sm text-error hover:bg-error-bg transition-colors"
            >
              Delete connector…
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex flex-col flex-1 overflow-y-auto px-6 py-5 gap-5">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-foreground-2">Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                disabled={isEdit}
                placeholder="e.g. web-search"
                className={cn(
                  'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none transition-colors',
                  isEdit ? 'cursor-not-allowed opacity-60' : 'focus:border-accent-focus'
                )}
              />
              {!isEdit && (
                <p className="text-[11px] text-faint">Lowercase letters, numbers, and hyphens only.</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-foreground-2">Description</label>
              <input
                value={description}
                onChange={e => setDesc(e.target.value)}
                placeholder="What does this connector provide?"
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-foreground-2">JSON Config</label>
              <div className="group/json relative rounded-lg border border-border bg-surface overflow-hidden focus-within:border-accent-focus transition-colors">
                <div className="absolute right-2 top-2 z-10 flex items-center gap-1 opacity-0 group-hover/json:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={handleFormat}
                    title="Format JSON"
                    className="flex items-center gap-1 rounded border border-border bg-card px-1.5 py-0.5 text-[10px] text-muted hover:text-foreground hover:border-border-2 transition-colors shadow-sm"
                  >
                    <WandSparkles size={10} /> Format
                  </button>
                  <button
                    type="button"
                    onClick={() => setWordWrap(v => !v)}
                    title={wordWrap ? 'Disable word wrap' : 'Enable word wrap'}
                    className={cn(
                      'flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] transition-colors shadow-sm',
                      wordWrap
                        ? 'border-accent-border bg-accent-light text-accent'
                        : 'border-border bg-card text-muted hover:text-foreground hover:border-border-2'
                    )}
                  >
                    <WrapText size={10} /> Wrap
                  </button>
                  <button
                    type="button"
                    onClick={handleCopy}
                    title="Copy to clipboard"
                    className={cn(
                      'flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] transition-colors shadow-sm',
                      copied
                        ? 'border-success-border bg-success-bg text-success'
                        : 'border-border bg-card text-muted hover:text-foreground hover:border-border-2'
                    )}
                  >
                    {copied ? <Check size={10} /> : <Copy size={10} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <CodeMirror
                  value={jsonText}
                  onChange={handleJsonChange}
                  theme={scheme}
                  extensions={[json(), jsonEditorTheme, ...(wordWrap ? [EditorView.lineWrapping] : [])]}
                  basicSetup={{
                    lineNumbers: false,
                    foldGutter: false,
                    highlightActiveLine: false,
                    indentOnInput: true,
                    tabSize: 2,
                  }}
                />
              </div>
              {validation.state === 'valid' && (
                <p className="flex items-center gap-1.5 text-[11px] text-success">
                  <CheckCircle2 size={11} />
                  Valid — {validation.serverCount} server{validation.serverCount !== 1 ? 's' : ''} found
                </p>
              )}
              {validation.state === 'invalid' && (
                <p className="flex items-center gap-1.5 text-[11px] text-error">
                  <AlertCircle size={11} />
                  {validation.message}
                </p>
              )}
              {validation.state === 'idle' && (
                <p className="text-[11px] text-faint">Paste an MCP server configuration object.</p>
              )}
            </div>

            {validation.state === 'valid' && validation.serverCount > 0 && (
              <ServerPreview servers={validation.servers} />
            )}

            {error && <p className="text-xs text-error">{error}</p>}
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
            <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!isValid}
              className={cn(
                'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                isValid
                  ? 'bg-accent text-white hover:bg-accent-hover'
                  : 'bg-accent-muted text-white/60 cursor-not-allowed'
              )}
            >
              {pending ? 'Saving…' : isEdit ? 'Save changes' : 'Create connector'}
            </button>
          </div>
        </>
      )}
    </ResizablePanel>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export function ConnectorsPage({ initialData }: { initialData: ConnectorApi[] }) {
  const router = useRouter()
  const [search, setSearch]             = useState('')
  const [drawerOpen, setDrawer]         = useState(false)
  const [editTarget, setEdit]           = useState<Connector | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Connector | null>(null)
  const [connectors, setConnectors]     = useState<Connector[]>(() => initialData.map(fromApi))
  const [savePending, startSave]        = useTransition()
  const [saveError, setSaveError]       = useState<string | null>(null)

  useEffect(() => {
    setConnectors(initialData.map(fromApi))
  }, [initialData])

  const filtered = connectors.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.description.toLowerCase().includes(search.toLowerCase())
  )

  function openCreate() { setEdit(null); setSaveError(null); setDrawer(true) }
  function openEdit(c: Connector) { setEdit(c); setSaveError(null); setDrawer(true) }

  function handleSave(data: { name: string; description: string; mcpConfig: McpConfig }) {
    const mcpConfigStr = JSON.stringify(data.mcpConfig)
    setSaveError(null)

    if (editTarget) {
      startSave(async () => {
        const result = await updateConnector(editTarget.name, data.description, mcpConfigStr)
        if (result.error) { setSaveError(result.error); return }
        setConnectors(prev => prev.map(c =>
          c.name === editTarget.name ? { ...c, description: data.description, mcpConfig: data.mcpConfig } : c
        ))
        setDrawer(false)
        router.refresh()
      })
    } else {
      startSave(async () => {
        const result = await createConnector(data.name, data.description, mcpConfigStr)
        if (result.error) { setSaveError(result.error); return }
        setConnectors(prev => [{ ...data, createdAt: new Date() }, ...prev])
        setDrawer(false)
        router.refresh()
      })
    }
  }

  function handleDeleted(name: string) {
    setConnectors(prev => prev.filter(c => c.name !== name))
    setDeleteTarget(null)
    router.refresh()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <Plug size={16} className="text-muted" />
          <span className="text-sm font-semibold text-foreground">Connectors</span>
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] text-muted">
            {connectors.length}
          </span>
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
      <div className="flex-1 overflow-y-auto p-6">
        {filtered.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia><Plug size={32} className="text-faint" /></EmptyMedia>
              <EmptyTitle>{search ? `No connectors matching "${search}"` : 'No connectors yet'}</EmptyTitle>
            </EmptyHeader>
            {!search && (
              <EmptyContent>
                <button onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover transition-colors">
                  Create your first connector
                </button>
              </EmptyContent>
            )}
          </Empty>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map(c => (
              <ConnectorCard
                key={c.name}
                connector={c}
                onEdit={() => openEdit(c)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Drawer */}
      <ConnectorDrawer
        open={drawerOpen}
        initial={editTarget}
        pending={savePending}
        error={saveError}
        onClose={() => setDrawer(false)}
        onSave={handleSave}
        onDeleteRequest={() => { if (editTarget) setDeleteTarget(editTarget) }}
      />

      {/* Delete modal */}
      <DeleteModal
        connector={deleteTarget}
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDeleted(deleteTarget.name)}
      />
    </div>
  )
}
