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

import { useRef, useState, useEffect } from 'react'
import { Send, Paperclip, X, Loader2, FileText, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { listAgentlets, type AgentletApi } from '@/app/(dashboard)/dashboard/agentlets/actions'

export interface StagedFile {
  file: File
  id: string
}

interface MessageInputProps {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onAddFiles: (files: File[]) => void
  onRemoveFile: (id: string) => void
  stagedFiles: StagedFile[]
  disabled: boolean
}

// ── @mention helpers ──────────────────────────────────────────────────────────

interface MentionState {
  query: string
  start: number  // index of the @ character in the full text
}

function detectMention(text: string, cursorPos: number): MentionState | null {
  const before = text.slice(0, cursorPos)
  const atIdx = before.lastIndexOf('@')
  if (atIdx === -1) return null
  const afterAt = before.slice(atIdx + 1)
  // Close if there's whitespace between @ and cursor (mention ended)
  if (/\s/.test(afterAt)) return null
  return { query: afterAt.toLowerCase(), start: atIdx }
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MessageInput({
  value,
  onChange,
  onSend,
  onAddFiles,
  onRemoveFile,
  stagedFiles,
  disabled,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const [agentlets, setAgentlets] = useState<AgentletApi[]>([])
  const [mention, setMention] = useState<MentionState | null>(null)
  const [activeIdx, setActiveIdx] = useState(0)
  const fetchedRef = useRef(false)

  const filtered = mention
    ? agentlets.filter(a => a.id.toLowerCase().includes(mention.query)).slice(0, 6)
    : []

  // Browsers don't restore focus after re-enabling a disabled element
  useEffect(() => {
    if (!disabled && document.activeElement !== textareaRef.current) {
      textareaRef.current?.focus()
    }
  }, [disabled])

  // Close dropdown on outside click
  useEffect(() => {
    if (!mention) return
    function handler(e: MouseEvent) {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        textareaRef.current && !textareaRef.current.contains(e.target as Node)
      ) {
        setMention(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [mention])

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const text = e.target.value
    onChange(text)
    autoResize()

    const cursor = e.target.selectionStart ?? text.length
    const m = detectMention(text, cursor)
    setMention(m)
    setActiveIdx(0)

    if (m && !fetchedRef.current) {
      fetchedRef.current = true
      listAgentlets().then(setAgentlets)
    }
  }

  function selectMention(agentlet: AgentletApi) {
    if (!mention) return
    const before = value.slice(0, mention.start)
    const after = value.slice(mention.start + 1 + mention.query.length)
    onChange(before + '@' + agentlet.id + after)
    setMention(null)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  function handleKey(e: React.KeyboardEvent) {
    if (mention && filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIdx(i => Math.min(i + 1, filtered.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIdx(i => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        selectMention(filtered[activeIdx])
        return
      }
      if (e.key === 'Escape') {
        setMention(null)
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) {
      onAddFiles(Array.from(e.target.files))
      e.target.value = ''
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    if (e.dataTransfer.files.length) onAddFiles(Array.from(e.dataTransfer.files))
  }

  const canSend = (value.trim() || stagedFiles.length > 0) && !disabled

  return (
    <div className="space-y-2">
      {/* Staged files strip */}
      {stagedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-1">
          {stagedFiles.map(sf => (
            <div
              key={sf.id}
              className="flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-xs text-foreground-2"
            >
              <FileText size={11} className="text-muted flex-none" />
              <span className="max-w-[120px] truncate">{sf.file.name}</span>
              <button
                onClick={() => onRemoveFile(sf.id)}
                className="ml-0.5 text-muted hover:text-foreground transition-colors"
                aria-label={`Remove ${sf.file.name}`}
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input wrapper — relative so dropdown can anchor to it */}
      <div className="relative">
        {/* @mention dropdown */}
        {mention && filtered.length > 0 && (
          <div
            ref={dropdownRef}
            className="absolute bottom-full mb-2 left-0 right-0 z-50 rounded-xl border border-border bg-card shadow-md overflow-hidden"
          >
            {filtered.map((a, i) => (
              <button
                key={a.id}
                onMouseDown={e => { e.preventDefault(); selectMention(a) }}
                className={cn(
                  'flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm transition-colors',
                  i === activeIdx
                    ? 'bg-accent-light text-foreground'
                    : 'text-foreground-2 hover:bg-card-hover hover:text-foreground',
                )}
              >
                <Zap size={13} className="flex-none text-muted" />
                <span className="font-medium">{a.id}</span>
                {a.description && (
                  <span className="ml-1 truncate text-xs text-muted">{a.description}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Input box */}
        <div
          className="flex flex-col rounded-2xl border border-border bg-card px-4 pt-3 pb-2 shadow-sm focus-within:border-accent-focus transition-colors"
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKey}
            placeholder="Ask Synte…"
            disabled={disabled}
            className="w-full resize-none bg-transparent text-sm text-foreground placeholder:text-faint outline-none leading-relaxed disabled:opacity-60"
            style={{ minHeight: '24px' }}
          />

          {/* Toolbar */}
          <div className="flex items-center justify-between mt-2">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              className="text-muted hover:text-foreground"
              aria-label="Attach files"
            >
              <Paperclip size={15} />
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileChange}
            />

            <button
              onClick={onSend}
              disabled={!canSend}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-lg transition-colors',
                canSend
                  ? 'bg-accent text-white hover:bg-accent-hover'
                  : 'text-faint cursor-not-allowed',
              )}
              aria-label="Send"
            >
              {disabled
                ? <Loader2 size={15} className="animate-spin" />
                : <Send size={15} />
              }
            </button>
          </div>
        </div>
      </div>

      <p className="text-center text-[11px] text-faint">
        Synte is AI and can make mistakes. Please double-check responses.
      </p>
    </div>
  )
}
