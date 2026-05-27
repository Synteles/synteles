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
import { Plus, Search, KeyRound, Pencil, Trash2, X, Eye, EyeOff, Lock, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SecretApi } from '@/app/(dashboard)/dashboard/secrets/actions'
import { createSecret, updateSecret, deleteSecret, getSecretDetail } from '@/app/(dashboard)/dashboard/secrets/actions'
import { ResizablePanel } from '@/components/ui/resizable-panel'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'

// ── Types ──────────────────────────────────────────────────────────────────
interface Secret {
  name: string
  description: string
  keyCount: number
  createdAt: Date | null
  updatedAt: Date | null
}

interface SecretKV {
  key: string
  value: string
}

function fromApi(s: SecretApi): Secret {
  return {
    name: s.name,
    description: s.description ?? '',
    keyCount: s.key_count ?? 0,
    createdAt: s.created_at ? new Date(s.created_at) : null,
    updatedAt: s.updated_at ? new Date(s.updated_at) : null,
  }
}

function formatDate(d: Date | null) {
  if (!d) return '—'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

const NAME_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$/

// ── Name badge ─────────────────────────────────────────────────────────────
function NameBadge({ name }: { name: string }) {
  return (
    <Badge className="font-mono border-accent-border bg-accent-light text-accent">{name}</Badge>
  )
}

// ── KV Row ─────────────────────────────────────────────────────────────────
function KVRow({
  kv,
  onChange,
  onRemove,
  canRemove,
}: {
  kv: SecretKV
  onChange: (updated: SecretKV) => void
  onRemove: () => void
  canRemove: boolean
}) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div className="flex items-center gap-2">
      <input
        value={kv.key}
        onChange={e => onChange({ ...kv, key: e.target.value })}
        placeholder="KEY_NAME"
        className="w-36 flex-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
      />
      <div className="relative flex-1">
        <input
          type={revealed ? 'text' : 'password'}
          value={kv.value}
          onChange={e => onChange({ ...kv, value: e.target.value })}
          placeholder="value"
          className="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-9 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
        />
        <button
          type="button"
          onClick={() => setRevealed(v => !v)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-faint hover:text-muted transition-colors"
        >
          {revealed ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
      </div>
      <button
        type="button"
        onClick={onRemove}
        disabled={!canRemove}
        className={cn(
          'flex-none rounded-md p-1.5 transition-colors',
          canRemove
            ? 'text-faint hover:bg-error-bg hover:text-error'
            : 'text-faint/30 cursor-not-allowed'
        )}
      >
        <X size={13} />
      </button>
    </div>
  )
}

// ── Create / Edit Drawer ───────────────────────────────────────────────────
function SecretDrawer({
  open,
  initial,
  initialKvs,
  loadingKvs,
  pending,
  error,
  onClose,
  onSave,
}: {
  open: boolean
  initial: Secret | null
  initialKvs: SecretKV[]
  loadingKvs: boolean
  pending: boolean
  error: string | null
  onClose: () => void
  onSave: (data: { name: string; description: string; kvs: SecretKV[] }) => void
}) {
  const isEdit = !!initial?.name
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDesc] = useState(initial?.description ?? '')
  const [kvs, setKvs] = useState<SecretKV[]>(initialKvs)

  useEffect(() => {
    setName(initial?.name ?? '')
    setDesc(initial?.description ?? '')
  }, [initial, open])

  useEffect(() => {
    setKvs(initialKvs)
  }, [initialKvs])

  const nameValid = NAME_REGEX.test(name)
  const kvValid = kvs.length > 0 && kvs.every(kv => kv.key.trim() !== '')
  const canSave = nameValid && kvValid && !pending && !loadingKvs

  function addKv() { setKvs(prev => [...prev, { key: '', value: '' }]) }
  function updateKv(i: number, updated: SecretKV) { setKvs(prev => prev.map((kv, j) => j === i ? updated : kv)) }
  function removeKv(i: number) { setKvs(prev => prev.filter((_, j) => j !== i)) }

  function handleSave() {
    if (!canSave) return
    onSave({ name: name.trim(), description: description.trim(), kvs })
  }

  return (
    <ResizablePanel open={open} onBackdropClick={onClose}>
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="font-semibold text-foreground">{isEdit ? 'Edit secret' : 'New secret'}</h2>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin px-6 py-5 gap-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isEdit}
              placeholder="e.g. openai-prod"
              className={cn(
                'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors',
                isEdit && 'opacity-60 cursor-not-allowed'
              )}
            />
            {name && !nameValid && (
              <p className="text-[11px] text-error">
                Must start with a letter or digit, then letters, digits, underscores, or hyphens (max 128 chars).
              </p>
            )}
            {!name && (
              <p className="text-[11px] text-faint">Letters, digits, underscores, and hyphens only. Cannot be changed after creation.</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2">Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={e => setDesc(e.target.value)}
              placeholder="What credentials does this secret hold?"
              className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-foreground-2">Key-value pairs</label>
            {loadingKvs ? (
              <div className="flex items-center gap-2 text-xs text-muted py-2">
                <Loader2 size={13} className="animate-spin" /> Loading secret values…
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {kvs.map((kv, i) => (
                  <KVRow
                    key={i}
                    kv={kv}
                    onChange={updated => updateKv(i, updated)}
                    onRemove={() => removeKv(i)}
                    canRemove={kvs.length > 1}
                  />
                ))}
              </div>
            )}
            <button
              type="button"
              onClick={addKv}
              disabled={loadingKvs}
              className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors mt-1 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus size={13} /> Add key
            </button>
          </div>

          {error && <p className="text-xs text-error">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
          <button onClick={onClose} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className={cn(
              'rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              canSave
                ? 'bg-accent text-white hover:bg-accent-hover'
                : 'bg-accent-muted text-white/60 cursor-not-allowed'
            )}
          >
            {pending ? 'Saving…' : isEdit ? 'Save changes' : 'Create secret'}
          </button>
        </div>
    </ResizablePanel>
  )
}

// ── Delete Confirmation Modal ──────────────────────────────────────────────
function DeleteSecretModal({
  secret,
  open,
  onClose,
  onConfirm,
}: {
  secret: Secret | null
  open: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const [input, setInput] = useState('')
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const matches = input === (secret?.name ?? '')

  useEffect(() => {
    if (open) { setInput(''); setError(null) }
  }, [open])

  function handleConfirm() {
    if (!matches || !secret) return
    setError(null)
    startTransition(async () => {
      const result = await deleteSecret(secret.name)
      if (result.error) { setError(result.error); return }
      onConfirm()
      onClose()
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete secret</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete{' '}
            <span className="font-mono bg-accent-light text-accent border border-accent-border px-1.5 py-0.5 rounded">
              {secret?.name}
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
            placeholder={secret?.name ?? ''}
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
export function SecretsPage({ initialData }: { initialData: SecretApi[] }) {
  const router = useRouter()
  const [search, setSearch]     = useState('')
  const [secrets, setSecrets]   = useState<Secret[]>(() => initialData.map(fromApi))
  const [drawerOpen, setDrawer] = useState(false)
  const [editTarget, setEdit]   = useState<Secret | null>(null)
  const [editKvs, setEditKvs]   = useState<SecretKV[]>([{ key: '', value: '' }])
  const [deleteTarget, setDeleteTarget] = useState<Secret | null>(null)
  const [savePending, startSave] = useTransition()
  const [loadKvsPending, startLoadKvs] = useTransition()
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setSecrets(initialData.map(fromApi))
  }, [initialData])

  const filtered = secrets.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.description.toLowerCase().includes(search.toLowerCase())
  )

  function openCreate() {
    setEdit(null)
    setEditKvs([{ key: '', value: '' }])
    setSaveError(null)
    setDrawer(true)
  }

  function openEdit(s: Secret) {
    setEdit(s)
    setEditKvs([{ key: '', value: '' }])
    setSaveError(null)
    startLoadKvs(async () => {
      const detail = await getSecretDetail(s.name)
      if ('error' in detail) {
        setEditKvs([{ key: '', value: '' }])
      } else if (detail.value && Object.keys(detail.value).length > 0) {
        setEditKvs(Object.entries(detail.value).map(([k, v]) => ({ key: k, value: v })))
      } else {
        setEditKvs([{ key: '', value: '' }])
      }
      setDrawer(true)
    })
  }

  function handleSave(data: { name: string; description: string; kvs: SecretKV[] }) {
    const value = Object.fromEntries(data.kvs.map(kv => [kv.key, kv.value]))
    setSaveError(null)

    if (editTarget) {
      startSave(async () => {
        const result = await updateSecret(editTarget.name, data.description, value)
        if (result.error) { setSaveError(result.error); return }
        setSecrets(prev => prev.map(s =>
          s.name === editTarget.name
            ? { ...s, description: data.description, keyCount: data.kvs.length, updatedAt: new Date() }
            : s
        ))
        setDrawer(false)
        router.refresh()
      })
    } else {
      startSave(async () => {
        const result = await createSecret(data.name, data.description, value)
        if (result.error) { setSaveError(result.error); return }
        const next: Secret = {
          name: data.name,
          description: data.description,
          keyCount: data.kvs.length,
          createdAt: new Date(),
          updatedAt: new Date(),
        }
        setSecrets(prev => [next, ...prev])
        setDrawer(false)
        router.refresh()
      })
    }
  }

  function handleDeleted(name: string) {
    setSecrets(prev => prev.filter(s => s.name !== name))
    router.refresh()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <h1 className="text-sm font-semibold text-foreground">Secrets</h1>
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
            <Plus size={14} /> New secret
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {filtered.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia><Lock size={32} className="text-faint" /></EmptyMedia>
              <EmptyTitle>{search ? `No secrets matching "${search}"` : 'No secrets yet'}</EmptyTitle>
            </EmptyHeader>
            {!search && (
              <EmptyContent>
                <button onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover transition-colors">
                  Create your first secret
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Description</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Keys</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Updated</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {filtered.map(secret => (
                  <tr key={secret.name} className="hover:bg-card-hover transition-colors group">
                    <td className="px-4 py-3">
                      <NameBadge name={secret.name} />
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <span className="text-xs text-muted line-clamp-1">{secret.description}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-muted">
                        <KeyRound size={10} />
                        {secret.keyCount}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted">{formatDate(secret.createdAt)}</td>
                    <td className="px-4 py-3 text-xs text-muted">{formatDate(secret.updatedAt)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEdit(secret)}
                          className="flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-border-2 hover:text-foreground"
                        >
                          <Pencil size={11} /> Edit
                        </button>
                        <button
                          onClick={() => setDeleteTarget(secret)}
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

      {/* Drawer */}
      <SecretDrawer
        open={drawerOpen}
        initial={editTarget}
        initialKvs={editKvs}
        loadingKvs={loadKvsPending}
        pending={savePending}
        error={saveError}
        onClose={() => setDrawer(false)}
        onSave={handleSave}
      />

      {/* Delete modal */}
      <DeleteSecretModal
        secret={deleteTarget}
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDeleted(deleteTarget.name)}
      />
    </div>
  )
}
