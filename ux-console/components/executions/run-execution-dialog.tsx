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

import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Play, X, Upload, FileText, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { launchExecution, createFileUploadSession } from '@/lib/executions'
import { ResizablePanel } from '@/components/ui/resizable-panel'

const TIMEOUT_OPTIONS = [
  { label: '5 min',  value: 300  },
  { label: '15 min', value: 900  },
  { label: '30 min', value: 1800 },
  { label: '1 hr',   value: 3600 },
]

interface StagedFile {
  file: File
  id: string
}

interface Props {
  agentletId: string | null
  onClose: () => void
}

export function RunExecutionDialog({ agentletId, onClose }: Props) {
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [prompt, setPrompt]       = useState('')
  const [timeout, setTimeout]     = useState(900)
  const [staged, setStaged]       = useState<StagedFile[]>([])
  const [dragging, setDragging]   = useState(false)
  const [launching, setLaunching] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  // Reset form each time a new agentlet is targeted
  useEffect(() => {
    if (agentletId) {
      setPrompt('')
      setTimeout(900)
      setStaged([])
      setDragging(false)
      setError(null)
    }
  }, [agentletId])

  function addFiles(files: FileList | File[]) {
    const incoming = Array.from(files).map(f => ({ file: f, id: crypto.randomUUID() }))
    setStaged(prev => [...prev, ...incoming])
  }

  function removeFile(id: string) {
    setStaged(prev => prev.filter(f => f.id !== id))
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setDragging(true)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  async function handleLaunch() {
    if (!agentletId) return
    setError(null)
    setLaunching(true)

    try {
      let inputObjects: string[] | undefined
      if (staged.length > 0) {
        const session = await createFileUploadSession(staged.map(s => s.file.name))
        const stagedByName = Object.fromEntries(staged.map(s => [s.file.name, s.file]))
        await Promise.all(
          session.files.map(slot => {
            const file = stagedByName[slot.name]
            if (!file) return Promise.resolve()
            const form = new FormData()
            for (const [k, v] of Object.entries(slot.upload_fields)) form.append(k, v)
            form.append('file', file)
            return fetch(slot.upload_url, { method: 'POST', body: form })
          }),
        )
        inputObjects = session.files.map(s => s.s3_uri)
      }

      const result = await launchExecution({
        agentlet_id: agentletId,
        prompt: prompt.trim() || undefined,
        timeout,
        input_objects: inputObjects,
      })

      await qc.invalidateQueries({ queryKey: ['executions', 'active'] })
      await qc.invalidateQueries({ queryKey: ['executions', 'recent'] })

      toast.success(`${agentletId} started`, {
        description: `Execution ${result.execution_id.slice(-8)}`,
        id: result.execution_id,
        duration: 4000,
      })

      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Launch failed')
    } finally {
      setLaunching(false)
    }
  }

  return (
    <ResizablePanel open={!!agentletId} onBackdropClick={onClose}>
      {/* Header */}
      <div className="flex-none border-b border-border">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 min-w-0">
            <Play size={14} className="flex-none text-accent" />
            <h2 className="font-mono text-sm font-semibold text-foreground truncate">
              {agentletId}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-col flex-1 overflow-y-auto scrollbar-thin px-6 py-5 gap-5">
        {/* Prompt */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground-2">
            Prompt <span className="text-faint font-normal">optional</span>
          </label>
          <textarea
            rows={5}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="Describe the task for this agentlet…"
            className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint outline-none focus:border-accent-focus transition-colors"
          />
        </div>

        {/* Timeout */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-foreground-2">Timeout</label>
          <div className="flex gap-2">
            {TIMEOUT_OPTIONS.map(o => (
              <button
                key={o.value}
                onClick={() => setTimeout(o.value)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                  timeout === o.value
                    ? 'border-accent bg-accent-light text-accent'
                    : 'border-border bg-surface text-muted hover:text-foreground hover:border-border-2',
                )}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        {/* File upload */}
        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-foreground-2">
            Input files <span className="text-faint font-normal">optional</span>
          </label>
          <div
            onDragOver={handleDragOver}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed py-6 transition-colors',
              dragging
                ? 'border-accent bg-accent-light'
                : 'border-border bg-surface hover:border-border-2 hover:bg-card',
            )}
          >
            <Upload size={16} className="text-faint" />
            <p className="text-xs text-muted">
              Drop files here or <span className="text-accent">browse</span>
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={e => { if (e.target.files) addFiles(e.target.files) }}
            />
          </div>

          {staged.length > 0 && (
            <div className="flex flex-col gap-1">
              {staged.map(s => (
                <div key={s.id} className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5">
                  <FileText size={12} className="flex-none text-muted" />
                  <span className="flex-1 truncate text-xs text-foreground">{s.file.name}</span>
                  <span className="text-[10px] text-faint tabular-nums">
                    {(s.file.size / 1024).toFixed(0)} KB
                  </span>
                  <button
                    onClick={() => removeFile(s.id)}
                    className="flex-none text-faint hover:text-error transition-colors"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && <p className="text-xs text-error">{error}</p>}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
        <button
          onClick={onClose}
          className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleLaunch}
          disabled={launching}
          className={cn(
            'flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
            launching
              ? 'bg-accent-muted text-white/60 cursor-not-allowed'
              : 'bg-accent text-white hover:bg-accent-hover',
          )}
        >
          {launching
            ? <><Loader2 size={13} className="animate-spin" /> Launching…</>
            : <><Play size={13} /> Run agentlet</>
          }
        </button>
      </div>
    </ResizablePanel>
  )
}
