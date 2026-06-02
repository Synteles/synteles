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

import { useState, useEffect, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search, Cpu, Pencil, Trash2, X, KeyRound } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ModelPresetApi } from '@/app/(dashboard)/dashboard/models/actions'
import { createModelPreset, updateModelPreset, deleteModelPreset } from '@/app/(dashboard)/dashboard/models/actions'
import { ResizablePanel } from '@/components/ui/resizable-panel'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '@/components/ui/alert-dialog'
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'

// ── Types ──────────────────────────────────────────────────────────────────
interface ModelPreset {
  name: string
  description: string
  provider: string
  modelId: string
  secretName: string | null
  createdAt: Date | null
}

function fromApi(m: ModelPresetApi): ModelPreset {
  return {
    name: m.name,
    description: m.description ?? '',
    provider: m.provider,
    modelId: m.model_id,
    secretName: m.secret_name ?? null,
    createdAt: m.created_at ? new Date(m.created_at) : null,
  }
}

// ── Provider catalog ────────────────────────────────────────────────────────
const PROVIDERS = [
  { id: 'anthropic',   name: 'Anthropic' },
  { id: 'openai',      name: 'OpenAI' },
  { id: 'bedrock',     name: 'AWS Bedrock' },
  { id: 'vertex_ai',   name: 'Google Vertex AI' },
  { id: 'gemini',      name: 'Google AI Studio' },
  { id: 'azure',       name: 'Azure OpenAI' },
  { id: 'azure_ai',    name: 'Azure AI' },
  { id: 'mistral',     name: 'Mistral AI' },
  { id: 'groq',        name: 'Groq' },
  { id: 'cohere',      name: 'Cohere' },
  { id: 'together_ai', name: 'Together AI' },
  { id: 'ollama',      name: 'Ollama' },
] as const

const CUSTOM_PROVIDER = '-- custom --'

// ── Helpers ─────────────────────────────────────────────────────────────────
function providerById(id: string) {
  return PROVIDERS.find(p => p.id === id)
}

function truncate(str: string, max: number) {
  return str.length > max ? str.slice(0, max) + '…' : str
}

function fmtDate(d: Date | null) {
  if (!d) return '—'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Name badge ───────────────────────────────────────────────────────────────
function NameBadge({ name }: { name: string }) {
  return (
    <Badge className="font-mono border-accent-border bg-accent-light text-accent">{name}</Badge>
  )
}

// ── Provider label ────────────────────────────────────────────────────────────
function ProviderLabel({ providerId }: { providerId: string }) {
  const p = providerById(providerId)
  return <span className="text-xs text-muted">{p?.name ?? providerId}</span>
}

// ── Delete confirmation modal ─────────────────────────────────────────────────
function DeleteModal({
  preset,
  open,
  onCancel,
  onConfirm,
}: {
  preset: ModelPreset | null
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
    if (!preset || typed !== preset.name) return
    setError(null)
    startTransition(async () => {
      const result = await deleteModelPreset(preset.name)
      if (result.error) { setError(result.error); return }
      onConfirm()
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete model preset</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. Type{' '}
            <span className="font-mono font-semibold text-foreground">{preset?.name}</span>{' '}
            to confirm.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex flex-col gap-3">
          <input
            autoFocus={open}
            value={typed}
            onChange={e => setTyped(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleConfirm() }}
            placeholder={preset?.name ?? ''}
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-error-focus transition-colors"
          />
          {error && <p className="text-xs text-error">{error}</p>}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={!preset || typed !== preset.name || pending}
            variant="destructive"
          >
            {pending ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ── Create / Edit drawer ──────────────────────────────────────────────────────
function ModelDrawer({
  open,
  initial,
  secretNames,
  pending,
  error,
  onClose,
  onSave,
}: {
  open: boolean
  initial: ModelPreset | null
  secretNames: string[]
  pending: boolean
  error: string | null
  onClose: () => void
  onSave: (data: Omit<ModelPreset, 'createdAt'>) => void
}) {
  const isEdit = !!initial?.name

  const [name, setName]                   = useState(initial?.name ?? '')
  const [description, setDesc]            = useState(initial?.description ?? '')
  const [providerId, setProvider]         = useState(initial?.provider ?? 'anthropic')
  const [customProvider, setCustomProvider] = useState('')
  const [modelId, setModelId]             = useState(initial?.modelId ?? '')
  const [secretName, setSecret]           = useState<string | null>(initial?.secretName ?? null)

  useEffect(() => {
    setName(initial?.name ?? '')
    setDesc(initial?.description ?? '')
    const pid = initial?.provider ?? 'anthropic'
    if (PROVIDERS.some(p => p.id === pid)) {
      setProvider(pid)
      setCustomProvider('')
    } else {
      setProvider(CUSTOM_PROVIDER)
      setCustomProvider(pid)
    }
    setModelId(initial?.modelId ?? '')
    setSecret(initial?.secretName ?? null)
  }, [initial, open])

  function handleProviderChange(pid: string) {
    setProvider(pid)
    if (pid !== CUSTOM_PROVIDER) setCustomProvider('')
  }

  const effectiveProvider = providerId === CUSTOM_PROVIDER ? customProvider.trim() : providerId
  const isValid = name.trim() !== '' && effectiveProvider !== '' && modelId.trim() !== '' && !pending

  function handleSave() {
    if (!isValid) return
    onSave({
      name: name.trim(),
      description: description.trim(),
      provider: effectiveProvider,
      modelId: modelId.trim(),
      secretName: secretName || null,
    })
  }

  return (
    <ResizablePanel open={open} onBackdropClick={onClose}>
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="font-semibold text-foreground">{isEdit ? 'Edit model preset' : 'New model preset'}</h2>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex flex-col flex-1 overflow-y-auto px-6 py-5 gap-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2">Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isEdit}
              placeholder="e.g. claude-prod"
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
              placeholder="Brief description of this preset"
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2">Provider</label>
            <Select value={providerId} onValueChange={(v) => v && handleProviderChange(v)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {PROVIDERS.map(p => (
                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                  ))}
                  <SelectItem value={CUSTOM_PROVIDER}>{CUSTOM_PROVIDER}</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            {providerId === CUSTOM_PROVIDER && (
              <input
                value={customProvider}
                onChange={e => setCustomProvider(e.target.value)}
                placeholder="e.g. huggingface, alephalpha, deepinfra"
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
              />
            )}
            <p className="text-[11px] text-faint">
              Full list of supported providers on{' '}
              <a
                href="https://docs.litellm.ai/docs/providers"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent underline-offset-2 hover:underline"
              >
                LiteLLM docs
              </a>
              .
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2">Model ID</label>
            <input
              value={modelId}
              onChange={e => setModelId(e.target.value)}
              placeholder="e.g. claude-sonnet-4-6, gpt-4o, llama3:8b"
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground-2 flex items-center gap-1.5">
              <KeyRound size={12} className="text-faint" />
              Secret
            </label>
            <Select value={secretName ?? ''} onValueChange={(v) => setSecret(v || null)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="">— none —</SelectItem>
                  {secretNames.map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <p className="text-[11px] text-faint">The secret holding API credentials for this provider.</p>
          </div>

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
            {pending ? 'Saving…' : isEdit ? 'Save changes' : 'Create preset'}
          </button>
        </div>
    </ResizablePanel>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export function ModelsPage({
  initialData,
  secretNames,
}: {
  initialData: ModelPresetApi[]
  secretNames: string[]
}) {
  const router = useRouter()
  const [search, setSearch]         = useState('')
  const [drawerOpen, setDrawer]     = useState(false)
  const [editTarget, setEdit]       = useState<ModelPreset | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ModelPreset | null>(null)
  const [presets, setPresets]       = useState<ModelPreset[]>(() => initialData.map(fromApi))
  const [savePending, startSave]    = useTransition()
  const [saveError, setSaveError]   = useState<string | null>(null)

  useEffect(() => {
    setPresets(initialData.map(fromApi))
  }, [initialData])

  const filtered = presets.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.description.toLowerCase().includes(search.toLowerCase()) ||
    (providerById(p.provider)?.name ?? p.provider).toLowerCase().includes(search.toLowerCase())
  )

  function openCreate() { setEdit(null); setSaveError(null); setDrawer(true) }
  function openEdit(p: ModelPreset) { setEdit(p); setSaveError(null); setDrawer(true) }

  function handleSave(data: Omit<ModelPreset, 'createdAt'>) {
    setSaveError(null)
    if (editTarget) {
      startSave(async () => {
        const result = await updateModelPreset(
          editTarget.name,
          data.provider,
          data.modelId,
          data.description,
          data.secretName ?? undefined,
        )
        if (result.error) { setSaveError(result.error); return }
        setPresets(prev => prev.map(p => p.name === editTarget.name ? { ...p, ...data } : p))
        setDrawer(false)
        router.refresh()
      })
    } else {
      startSave(async () => {
        const result = await createModelPreset(
          data.name,
          data.provider,
          data.modelId,
          data.description,
          data.secretName ?? undefined,
        )
        if (result.error) { setSaveError(result.error); return }
        setPresets(prev => [{ ...data, createdAt: new Date() }, ...prev])
        setDrawer(false)
        router.refresh()
      })
    }
  }

  function handleDeleted(name: string) {
    setPresets(prev => prev.filter(p => p.name !== name))
    setDeleteTarget(null)
    router.refresh()
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <Cpu size={16} className="text-muted" />
          <span className="text-sm font-semibold text-foreground">Model Presets</span>
          <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] text-muted">
            {presets.length}
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
              <EmptyMedia><Cpu size={32} className="text-faint" /></EmptyMedia>
              <EmptyTitle>{search ? `No presets matching "${search}"` : 'No model presets yet'}</EmptyTitle>
            </EmptyHeader>
            {!search && (
              <EmptyContent>
                <button onClick={openCreate} className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover transition-colors">
                  Create your first preset
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Provider</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Model ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Secret</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted">Created</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {filtered.map(preset => (
                  <tr key={preset.name} className="hover:bg-card-hover transition-colors group">
                    <td className="px-4 py-3"><NameBadge name={preset.name} /></td>
                    <td className="px-4 py-3"><ProviderLabel providerId={preset.provider} /></td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-muted" title={preset.modelId}>
                        {truncate(preset.modelId, 36)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {preset.secretName ? (
                        <span className="inline-flex items-center gap-1 font-mono text-xs text-muted">
                          <KeyRound size={10} className="text-faint" />
                          {preset.secretName}
                        </span>
                      ) : (
                        <span className="text-faint text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted whitespace-nowrap">{fmtDate(preset.createdAt)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEdit(preset)}
                          className="flex items-center gap-1 rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-muted transition-colors hover:border-border-2 hover:text-foreground"
                        >
                          <Pencil size={11} /> Edit
                        </button>
                        <button
                          onClick={() => setDeleteTarget(preset)}
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
      <ModelDrawer
        open={drawerOpen}
        initial={editTarget}
        secretNames={secretNames}
        pending={savePending}
        error={saveError}
        onClose={() => setDrawer(false)}
        onSave={handleSave}
      />

      {/* Delete modal */}
      <DeleteModal
        preset={deleteTarget}
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && handleDeleted(deleteTarget.name)}
      />
    </div>
  )
}
