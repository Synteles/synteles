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

import { useState } from 'react'
import { Wrench, Loader2, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { DisplayMessage, ToolCall } from '@/lib/conversations'
import { MarkdownContent } from './markdown-content'

interface ToolGroup {
  name: string
  count: number
  done: boolean
}

function groupTools(tools: ToolCall[]): ToolGroup[] {
  const map = new Map<string, ToolGroup>()
  for (const t of tools) {
    const g = map.get(t.name)
    if (g) {
      g.count++
      g.done = g.done && t.done
    } else {
      map.set(t.name, { name: t.name, count: 1, done: t.done })
    }
  }
  return Array.from(map.values())
}

function ToolCallRow({ group }: { group: ToolGroup }) {
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px]',
        group.done ? 'text-muted' : 'text-accent',
      )}
    >
      {group.done
        ? <Wrench size={10} className="flex-none" />
        : <Loader2 size={10} className="flex-none animate-spin" />
      }
      <span className="flex-1">{group.name.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())}</span>
      {group.count > 1 && (
        <span className="rounded-full bg-surface px-1.5 py-0.5 text-[10px] tabular-nums text-muted">
          ×{group.count}
        </span>
      )}
    </div>
  )
}

function MessageBubble({ msg }: { msg: DisplayMessage }) {
  const isUser = msg.role === 'user'
  const hasTools = (msg.tools?.length ?? 0) > 0
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(msg.content ?? '').then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className={cn('flex', isUser && 'justify-end')}>
      <div className={cn('space-y-1', isUser ? 'flex flex-col items-end' : 'w-full')}>
        {hasTools && (
          <div className="rounded-xl bg-card border border-border px-3 py-2 space-y-0.5 w-full">
            {groupTools(msg.tools).map(g => <ToolCallRow key={g.name} group={g} />)}
          </div>
        )}

        {msg.content && (
          <div className={cn(
            'text-sm leading-relaxed',
            isUser
              ? 'rounded-2xl bg-accent text-white px-4 py-2.5'
              : 'text-foreground',
          )}>
            {isUser
              ? <p className="whitespace-pre-wrap">{msg.content}</p>
              : <MarkdownContent content={msg.content} />
            }
            <div className={cn('mt-1 flex items-center gap-1.5', isUser ? 'justify-end' : '')}>
              <span className={cn('text-[10px]', isUser ? 'text-white/60' : 'text-faint')}>
                {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              {!isUser && (
                <button
                  onClick={handleCopy}
                  className="text-faint hover:text-muted transition-colors"
                  aria-label="Copy message"
                >
                  {copied
                    ? <Check size={11} />
                    : <Copy size={11} />
                  }
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface MessageListProps {
  messages: DisplayMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-5">
      {messages.map((msg, i) => (
        <MessageBubble key={msg.id ?? i} msg={msg} />
      ))}
    </div>
  )
}
