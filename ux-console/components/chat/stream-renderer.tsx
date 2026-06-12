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

import { Wrench, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { MarkdownContent } from './markdown-content'

export interface StreamTool {
  id: string
  name: string
  done: boolean
}

interface ToolGroup { name: string; count: number; done: boolean }

function groupTools(tools: StreamTool[]): ToolGroup[] {
  const map = new Map<string, ToolGroup>()
  for (const t of tools) {
    const g = map.get(t.name)
    if (g) { g.count++; g.done = g.done && t.done }
    else map.set(t.name, { name: t.name, count: 1, done: t.done })
  }
  return Array.from(map.values())
}

interface StreamRendererProps {
  text: string
  tools: StreamTool[]
}

export function StreamRenderer({ text, tools }: StreamRendererProps) {
  const showTools = tools.length > 0
  const showText = !!text
  const showDots = !showText && !showTools

  return (
    <div className="flex">
      <div className="w-full space-y-1">
        {showTools && (
          <div className="rounded-xl bg-card border border-border px-3 py-2 space-y-0.5 w-full">
            {groupTools(tools).map(g => (
              <div
                key={g.name}
                className={cn(
                  'flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px]',
                  g.done ? 'text-muted' : 'text-accent',
                )}
              >
                {g.done
                  ? <Wrench size={10} className="flex-none" />
                  : <Loader2 size={10} className="flex-none animate-spin" />
                }
                <span className="flex-1">{g.name.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())}</span>
                {g.count > 1 && (
                  <span className="rounded-full bg-surface px-1.5 py-0.5 text-[10px] tabular-nums text-muted">
                    ×{g.count}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {showText && (
          <div className="text-sm leading-relaxed text-foreground">
            <MarkdownContent content={text} />
            <span className="inline-block w-0.5 h-[1em] bg-current align-middle animate-pulse ml-0.5" />
          </div>
        )}

        {showDots && (
          <div className="py-1">
            <div className="flex gap-1 items-center">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 rounded-full bg-muted animate-bounce"
                  style={{ animationDelay: `${i * 150}ms` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
