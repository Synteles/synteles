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
import { Plus, MessageSquare, Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog'
import type { ConversationMeta } from '@/lib/conversations'

interface ConversationSidebarProps {
  conversations: ConversationMeta[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: ConversationSidebarProps) {
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameTitle, setRenameTitle] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)

  function openRename(conv: ConversationMeta, e: React.MouseEvent) {
    e.stopPropagation()
    setRenameId(conv.conversation_id)
    setRenameTitle(conv.title)
  }

  function openDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    setDeleteId(id)
  }

  function submitRename() {
    if (renameId && renameTitle.trim()) {
      onRename(renameId, renameTitle.trim())
    }
    setRenameId(null)
  }

  return (
    <aside className="flex h-full w-60 flex-none flex-col border-r border-sidebar-border bg-sidebar overflow-hidden">
      <div className="flex-none p-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onNew}
          className="w-full justify-start gap-2 text-muted hover:text-foreground"
        >
          <Plus size={14} />
          New chat
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3 space-y-0.5">
        {conversations.length === 0 && (
          <p className="px-2 py-4 text-xs text-faint text-center">No conversations yet</p>
        )}
        {conversations.map(conv => (
          <button
            key={conv.conversation_id}
            onClick={() => onSelect(conv.conversation_id)}
            className={cn(
              'group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition-colors',
              activeId === conv.conversation_id
                ? 'bg-sidebar-active text-foreground'
                : 'text-muted hover:bg-sidebar-hover hover:text-foreground',
            )}
          >
            <MessageSquare size={12} className="flex-none opacity-60" />
            <span className="flex-1 truncate">{conv.title}</span>
            <span className="flex-none flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => openRename(conv, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') openRename(conv, e as unknown as React.MouseEvent) }}
                className="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-surface hover:text-foreground transition-colors"
                aria-label="Rename"
              >
                <Pencil size={10} />
              </span>
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => openDelete(conv.conversation_id, e)}
                onKeyDown={(e) => { if (e.key === 'Enter') openDelete(conv.conversation_id, e as unknown as React.MouseEvent) }}
                className="flex h-5 w-5 items-center justify-center rounded text-muted hover:bg-surface hover:text-destructive transition-colors"
                aria-label="Delete"
              >
                <Trash2 size={10} />
              </span>
            </span>
          </button>
        ))}
      </div>

      <Dialog open={renameId !== null} onOpenChange={(o) => { if (!o) setRenameId(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename conversation</DialogTitle>
          </DialogHeader>
          <Input
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submitRename() }}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameId(null)}>Cancel</Button>
            <Button onClick={submitRename} disabled={!renameTitle.trim()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteId !== null} onOpenChange={(o) => { if (!o) setDeleteId(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => { if (deleteId) { onDelete(deleteId); setDeleteId(null) } }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  )
}
