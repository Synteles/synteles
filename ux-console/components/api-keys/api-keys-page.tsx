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

import { useState, useTransition, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search, Key, Trash2, X, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ApiKeyApi } from '@/app/(dashboard)/dashboard/api-keys/actions'
import { createApiKey, deleteApiKey } from '@/app/(dashboard)/dashboard/api-keys/actions'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'

// ── Types ──────────────────────────────────────────────────────────────────
interface ApiKey {
  id: string
  name: string
  createdAt: Date | null
  lastUsedAt: Date | null
}

function fromApi(k: ApiKeyApi): ApiKey {
  return {
    id: k.key_id,
    name: k.key_name,
    createdAt: k.created_at ? new Date(k.created_at) : null,
    lastUsedAt: k.last_used ? new Date(k.last_used) : null,
  }
}

function formatDate(d: Date | null) {
  if (!d) return '—'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Name badge ─────────────────────────────────────────────────────────────
function NameBadge({ name }: { name: string }) {
  return (
    <Badge className="font-mono border-accent-border bg-accent-light text-accent">{name}</Badge>
  )
}

// ── Copy button ────────────────────────────────────────────────────────────
function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className={cn(
        'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
        copied
          ? 'border-success-border bg-success-bg text-success'
          : 'border-border bg-surface text-muted hover:border-border-2 hover:text-foreground'
      )}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

// ── Create key panel ───────────────────────────────────────────────────────
function CreateKeyPanel({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (key: ApiKey) => void
}) {
  const [name, setName] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [generatedKey, setGeneratedKey] = useState<{ key: ApiKey; raw: string } | null>(null)

  useEffect(() => {
    if (open) {
      setName('')
      setError(null)
      setGeneratedKey(null)
    }
  }, [open])

  function handleCreate() {
    if (!name.trim()) return
    setError(null)
    startTransition(async () => {
      const result = await createApiKey(name.trim())
      if (result.error) { setError(result.error); return }
      const newKey: ApiKey = { id: crypto.randomUUID(), name: name.trim(), createdAt: new Date(), lastUsedAt: null }
      setGeneratedKey({ key: newKey, raw: result.key ?? '' })
      onCreated(newKey)
    })
  }

  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-30 bg-black/30 backdrop-blur-sm transition-opacity duration-300',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />
      <div
        className={cn(
          'fixed right-0 top-0 z-40 flex h-full w-full max-w-md flex-col bg-card border-l border-border shadow-xl transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="font-semibold text-foreground">{generatedKey ? 'API key created' : 'New API key'}</h2>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin px-6 py-5 gap-5">
          {generatedKey ? (
            <>
              <p className="text-sm text-muted leading-relaxed">
                Copy your key now — you will not be able to see it again.
              </p>
              <div className="rounded-lg border border-border bg-surface p-3 flex items-center gap-3">
                <code className="flex-1 min-w-0 truncate font-mono text-xs text-foreground">
                  {generatedKey.raw}
                </code>
                <CopyButton value={generatedKey.raw} />
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-foreground-2">Key name</label>
                <input
                  autoFocus={open}
                  value={name}
                  onChange={e => setName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
                  placeholder="e.g. production-integration"
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
                />
                <p className="text-[11px] text-faint">Letters, digits, underscores, and hyphens only.</p>
              </div>
              {error && <p className="text-xs text-error">{error}</p>}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
          {generatedKey ? (
            <button onClick={onClose} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover transition-colors">
              Done
            </button>
          ) : (
            <>
              <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!name.trim() || pending}
                className={cn(
                  'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
                  name.trim() && !pending
                    ? 'bg-accent text-white hover:bg-accent-hover'
                    : 'bg-accent-muted text-white/60 cursor-not-allowed'
                )}
              >
                {pending ? 'Creating…' : 'Create'}
              </button>
            </>
          )}
        </div>
      </div>
    </>
  )
}

// ── Delete Confirmation Modal ──────────────────────────────────────────────
function DeleteKeyModal({
  apiKey,
  open,
  onClose,
  onConfirm,
}: {
  apiKey: ApiKey | null
  open: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const [input, setInput] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const matches = input === (apiKey?.name ?? '')

  useEffect(() => {
    if (open) { setInput(''); setError(null) }
  }, [open])

  function handleConfirm() {
    if (!matches || !apiKey) return
    setError(null)
    startTransition(async () => {
      const result = await deleteApiKey(apiKey.id)
      if (result.error) { setError(result.error); return }
      onConfirm()
      onClose()
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete API key</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently revoke{' '}
            <span className="font-mono bg-accent-light text-accent border border-accent-border px-1.5 py-0.5 rounded">
              {apiKey?.name}
            </span>
            . Any integrations using this key will stop working. Type the name to confirm:
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-3">
          <input
            autoFocus={open}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={apiKey?.name ?? ''}
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
export function ApiKeysPage({ initialData }: { initialData: ApiKeyApi[] }) {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(() => initialData.map(fromApi))
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ApiKey | null>(null)

  useEffect(() => {
    setApiKeys(initialData.map(fromApi))
  }, [initialData])

  const filtered = apiKeys.filter(k =>
    k.name.toLowerCase().includes(search.toLowerCase())
  )

  function handleCreated(key: ApiKey) {
    setApiKeys(prev => [key, ...prev])
    router.refresh()
  }

  function handleDeleted(id: string) {
    setApiKeys(prev => prev.filter(k => k.id !== id))
    router.refresh()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <h1 className="text-sm font-semibold text-foreground">API Keys</h1>
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
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
          >
            <Plus size={14} /> New key
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {filtered.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia><Key size={32} className="text-faint" /></EmptyMedia>
              <EmptyTitle>{search ? `No API keys matching "${search}"` : 'No API keys yet'}</EmptyTitle>
            </EmptyHeader>
            {!search && (
              <EmptyContent>
                <button
                  onClick={() => setCreateOpen(true)}
                  className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover transition-colors"
                >
                  Create your first key
                </button>
              </EmptyContent>
            )}
          </Empty>
        ) : (
          <div className="rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-surface">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Last used</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {filtered.map(apiKey => (
                  <tr key={apiKey.id} className="hover:bg-card-hover transition-colors group">
                    <td className="px-4 py-3">
                      <NameBadge name={apiKey.name} />
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">{formatDate(apiKey.createdAt)}</td>
                    <td className="px-4 py-3 text-xs text-muted">
                      {apiKey.lastUsedAt ? formatDate(apiKey.lastUsedAt) : (
                        <span className="text-faint">Never</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => setDeleteTarget(apiKey)}
                          className="flex items-center gap-1 rounded-md border border-error-border bg-error-bg px-2.5 py-1 text-xs text-error transition-colors hover:bg-error-bg"
                        >
                          <Trash2 size={11} /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateKeyPanel
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />

      {/* Delete modal */}
      <DeleteKeyModal
        apiKey={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDeleted(deleteTarget.id)}
      />
    </div>
  )
}
