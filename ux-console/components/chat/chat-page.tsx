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

import { useReducer, useRef, useEffect, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import Image from 'next/image'
import { List, PlusCircle, Network, Rocket, History } from 'lucide-react'
import { toast } from 'sonner'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { MessageList } from './message-list'
import { MessageInput, type StagedFile } from './message-input'
import { StreamRenderer, type StreamTool } from './stream-renderer'
import { ConversationSidebar } from './conversation-sidebar'
import {
  createConversation,
  updateConversation,
  deleteConversation,
  getConversation,
  type DisplayMessage,
  type AgentState,
  type ConversationMeta,
} from '@/lib/conversations'
import { createFileUploadSession } from '@/lib/executions'
import type { UserInfo } from '@/lib/auth'

// ── State ─────────────────────────────────────────────────────────────────────

interface ChatState {
  conversations: ConversationMeta[]
  activeConvId: string | null
  messages: DisplayMessage[]
  agentState: AgentState
  streaming: boolean
  streamText: string
  streamTools: StreamTool[]
  inputText: string
  stagedFiles: StagedFile[]
}

type ChatAction =
  | { type: 'INIT_CONVS'; conversations: ConversationMeta[] }
  | { type: 'SELECT_CONV'; id: string; messages: DisplayMessage[]; agentState: AgentState }
  | { type: 'NEW_CONV' }
  | { type: 'RENAME_CONV'; id: string; title: string }
  | { type: 'DELETE_CONV'; id: string }
  | { type: 'SET_INPUT'; text: string }
  | { type: 'ADD_FILES'; files: StagedFile[] }
  | { type: 'REMOVE_FILE'; id: string }
  | { type: 'STREAM_START'; userMsg: DisplayMessage }
  | { type: 'STREAM_TEXT'; delta: string }
  | { type: 'STREAM_TOOL_START'; id: string; name: string }
  | { type: 'STREAM_TOOL_END'; id: string }
  | { type: 'STREAM_DONE'; assistantMsg: DisplayMessage; agentState: AgentState; convMeta: ConversationMeta }
  | { type: 'STREAM_ERROR' }

const EMPTY_AGENT_STATE: AgentState = { messages: [], manager_state: {} }

function reducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'INIT_CONVS':
      return { ...state, conversations: action.conversations }

    case 'SELECT_CONV':
      return {
        ...state,
        activeConvId: action.id,
        messages: action.messages,
        agentState: action.agentState,
        streaming: false,
        streamText: '',
        streamTools: [],
      }

    case 'NEW_CONV':
      return {
        ...state,
        activeConvId: null,
        messages: [],
        agentState: EMPTY_AGENT_STATE,
        streaming: false,
        streamText: '',
        streamTools: [],
        inputText: '',
        stagedFiles: [],
      }

    case 'RENAME_CONV':
      return {
        ...state,
        conversations: state.conversations.map(c =>
          c.conversation_id === action.id ? { ...c, title: action.title } : c,
        ),
      }

    case 'DELETE_CONV': {
      const convs = state.conversations.filter(c => c.conversation_id !== action.id)
      if (state.activeConvId !== action.id) {
        return { ...state, conversations: convs }
      }
      return {
        ...state,
        conversations: convs,
        activeConvId: null,
        messages: [],
        agentState: EMPTY_AGENT_STATE,
        streaming: false,
        streamText: '',
        streamTools: [],
      }
    }

    case 'SET_INPUT':
      return { ...state, inputText: action.text }

    case 'ADD_FILES':
      return { ...state, stagedFiles: [...state.stagedFiles, ...action.files] }

    case 'REMOVE_FILE':
      return { ...state, stagedFiles: state.stagedFiles.filter(f => f.id !== action.id) }

    case 'STREAM_START':
      return {
        ...state,
        messages: [...state.messages, action.userMsg],
        inputText: '',
        stagedFiles: [],
        streaming: true,
        streamText: '',
        streamTools: [],
      }

    case 'STREAM_TEXT':
      return { ...state, streamText: state.streamText + action.delta }

    case 'STREAM_TOOL_START':
      return {
        ...state,
        streamTools: [...state.streamTools, { id: action.id, name: action.name, done: false }],
      }

    case 'STREAM_TOOL_END':
      return {
        ...state,
        streamTools: state.streamTools.map(t => t.id === action.id ? { ...t, done: true } : t),
      }

    case 'STREAM_DONE': {
      const exists = state.conversations.some(c => c.conversation_id === action.convMeta.conversation_id)
      const conversations = exists
        ? state.conversations.map(c =>
            c.conversation_id === action.convMeta.conversation_id ? action.convMeta : c,
          )
        : [action.convMeta, ...state.conversations]
      return {
        ...state,
        streaming: false,
        streamText: '',
        streamTools: [],
        messages: [...state.messages, action.assistantMsg],
        agentState: action.agentState,
        activeConvId: action.convMeta.conversation_id,
        conversations,
      }
    }

    case 'STREAM_ERROR':
      return { ...state, streaming: false, streamText: '', streamTools: [] }

    default:
      return state
  }
}

// ── SSE reader ────────────────────────────────────────────────────────────────

async function* readSSE(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''
  let eventData = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const raw of lines) {
        const line = raw.trimEnd()
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          eventData = line.slice(5).trim()
        } else if (line === '') {
          if (eventType || eventData) {
            yield { event: eventType, data: eventData }
            eventType = ''
            eventData = ''
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// ── Greeting ─────────────────────────────────────────────────────────────────

const GREETINGS_ANY = [
  'Hello, {name}!', 'Good to see you, {name}!', 'Hey {name}!',
  'Welcome back, {name}.', 'Greetings, {name}!', 'Hey there, {name}!',
  'Back again, {name}?', 'Welcome, {name}.', 'Ah, {name}!',
  'Hello again, {name}!', 'Great to have you back, {name}.',
  '{name} has entered the building.', 'Look who\'s back, {name}!',
  'Welcome in, {name}.', '{name}, you\'re live.', 'Hey {name}, long time no see!',
]
const GREETINGS_MORNING = ['Good morning, {name}!', 'Rise and shine, {name}!']
const GREETINGS_AFTERNOON = ['Good afternoon, {name}!']
const GREETINGS_EVENING = ['Good evening, {name}!']

function pickGreeting(name: string): string {
  const hour = new Date().getHours()
  let pool = [...GREETINGS_ANY]
  if (hour >= 5 && hour < 12) pool = pool.concat(GREETINGS_MORNING)
  else if (hour >= 12 && hour < 18) pool = pool.concat(GREETINGS_AFTERNOON)
  else pool = pool.concat(GREETINGS_EVENING)
  return pool[Math.floor(Math.random() * pool.length)].replace('{name}', name)
}

// ── Suggestions ───────────────────────────────────────────────────────────────

const SUGGESTIONS: { label: string; prompt: string; icon: React.ElementType }[] = [
  { label: 'Show my agentlets',           prompt: 'List all my agentlets',                                               icon: List       },
  { label: 'Create a new agentlet',       prompt: 'Help me create a new agentlet from scratch',                          icon: PlusCircle },
  { label: 'Create a multi-agent system', prompt: 'I want to build a system with multiple AI agents working together',   icon: Network    },
  { label: 'Run an agentlet',             prompt: 'I want to execute one of my agentlets',                               icon: Rocket     },
  { label: 'Show my recent runs',         prompt: 'Show my most recent agentlet executions',                             icon: History    },
]

// ── Component ─────────────────────────────────────────────────────────────────

interface ChatPageProps {
  initialConversations: ConversationMeta[]
  user?: UserInfo | null
}

export function ChatPage({ initialConversations, user }: ChatPageProps) {
  const [state, dispatch] = useReducer(reducer, {
    conversations: initialConversations,
    activeConvId: null,
    messages: [],
    agentState: EMPTY_AGENT_STATE,
    streaming: false,
    streamText: '',
    streamTools: [],
    inputText: '',
    stagedFiles: [],
  })

  const stateRef = useRef(state)
  stateRef.current = state

  const firstName = user?.name?.split(' ')[0] || user?.email?.split('@')[0] || 'there'
  const greetingRef = useRef<string | null>(null)
  if (!greetingRef.current) greetingRef.current = pickGreeting(firstName)

  const streamAbortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.messages.length, state.streamText, state.streamTools.length])

  // ── Conversation handlers ─────────────────────────────────────────────────

  const handleSelectConv = useCallback(async (id: string) => {
    if (stateRef.current.activeConvId === id) return
    streamAbortRef.current?.abort()
    try {
      const full = await getConversation(id)
      dispatch({
        type: 'SELECT_CONV',
        id,
        messages: full.display_messages,
        agentState: full.agent_state,
      })
    } catch {
      toast.error('Failed to load conversation')
    }
  }, [])

  const handleNew = useCallback(() => {
    streamAbortRef.current?.abort()
    dispatch({ type: 'NEW_CONV' })
  }, [])

  const handleRename = useCallback(async (id: string, title: string) => {
    dispatch({ type: 'RENAME_CONV', id, title })
    try {
      await updateConversation(id, { title })
    } catch {
      toast.error('Failed to rename')
    }
  }, [])

  const handleDelete = useCallback(async (id: string) => {
    if (stateRef.current.activeConvId === id) {
      streamAbortRef.current?.abort()
    }
    dispatch({ type: 'DELETE_CONV', id })
    try {
      await deleteConversation(id)
    } catch {
      toast.error('Failed to delete conversation')
    }
  }, [])

  // ── Send ──────────────────────────────────────────────────────────────────

  const send = useCallback(async (textOverride?: string) => {
    const { stagedFiles, messages, agentState, activeConvId, streaming } = stateRef.current
    const trimmed = (textOverride ?? stateRef.current.inputText).trim()
    if ((!trimmed && stagedFiles.length === 0) || streaming) return

    // Upload staged files
    let pendingInputObjects: string[] | undefined
    if (stagedFiles.length > 0) {
      try {
        const session = await createFileUploadSession(stagedFiles.map(sf => sf.file.name))
        const byName = Object.fromEntries(stagedFiles.map(sf => [sf.file.name, sf.file]))
        await Promise.all(
          session.files.map(slot => {
            const file = byName[slot.name]
            if (!file) return Promise.resolve()
            const form = new FormData()
            for (const [k, v] of Object.entries(slot.upload_fields)) form.append(k, v)
            form.append('file', file)
            return fetch(slot.upload_url, { method: 'POST', body: form })
          }),
        )
        pendingInputObjects = session.files.map(s => s.s3_uri)
      } catch {
        toast.error('File upload failed')
        return
      }
    }

    const userMsg: DisplayMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      tools: [],
      ts: new Date().toISOString(),
    }

    dispatch({ type: 'STREAM_START', userMsg })

    // Capture conversation state for this turn before any dispatches
    const prevMessages = messages
    const prevAgentState = agentState
    const prevConvId = activeConvId

    let capturedAgentMessages: unknown[] = prevAgentState.messages
    let capturedManagerState: Record<string, unknown> = prevAgentState.manager_state
    let streamedText = ''
    const streamedTools: StreamTool[] = []

    const ac = new AbortController()
    streamAbortRef.current = ac

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: ac.signal,
        body: JSON.stringify({
          message: trimmed,
          messages: prevAgentState.messages,
          manager_state: prevAgentState.manager_state,
          pending_input_objects: pendingInputObjects,
        }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`Stream failed: ${res.status}`)
      }

      for await (const { event, data } of readSSE(res.body)) {
        if (event === 'text') {
          const p = JSON.parse(data) as { delta: string }
          streamedText += p.delta
          dispatch({ type: 'STREAM_TEXT', delta: p.delta })
        } else if (event === 'tool_start') {
          const p = JSON.parse(data) as { id: string; name: string }
          if (!streamedTools.some(t => t.id === p.id)) {
            streamedTools.push({ id: p.id, name: p.name, done: false })
            dispatch({ type: 'STREAM_TOOL_START', id: p.id, name: p.name })
          }
        } else if (event === 'tool_end') {
          const p = JSON.parse(data) as { id: string }
          const i = streamedTools.findIndex(t => t.id === p.id)
          if (i >= 0) streamedTools[i] = { ...streamedTools[i], done: true }
          dispatch({ type: 'STREAM_TOOL_END', id: p.id })
        } else if (event === 'state') {
          const p = JSON.parse(data) as { messages?: unknown[]; manager_state?: Record<string, unknown> }
          if (p.messages) capturedAgentMessages = p.messages
          if (p.manager_state) capturedManagerState = p.manager_state
        } else if (event === 'error') {
          const p = JSON.parse(data) as { message?: string }
          throw new Error(p.message ?? 'Stream error')
        } else if (event === 'done') {
          break
        }
      }

      if (ac.signal.aborted) {
        dispatch({ type: 'STREAM_ERROR' })
        return
      }

      const capturedAgentState: AgentState = {
        messages: capturedAgentMessages,
        manager_state: capturedManagerState,
      }

      const assistantMsg: DisplayMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: streamedText,
        tools: streamedTools.map(t => ({ id: t.id, name: t.name, done: t.done })),
        ts: new Date().toISOString(),
      }

      const allDisplayMessages: DisplayMessage[] = [...prevMessages, userMsg, assistantMsg]

      let convMeta: ConversationMeta
      if (prevConvId) {
        await updateConversation(prevConvId, {
          display_messages: allDisplayMessages,
          agent_state: capturedAgentState,
        })
        const existing = stateRef.current.conversations.find(c => c.conversation_id === prevConvId)
        convMeta = existing ?? {
          conversation_id: prevConvId,
          title: trimmed.slice(0, 60),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      } else {
        const title = trimmed.slice(0, 60) || 'New conversation'
        convMeta = await createConversation(title, allDisplayMessages, capturedAgentState)
      }

      dispatch({ type: 'STREAM_DONE', assistantMsg, agentState: capturedAgentState, convMeta })
      qc.invalidateQueries({ queryKey: ['executions', 'active'] })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        dispatch({ type: 'STREAM_ERROR' })
        return
      }
      dispatch({ type: 'STREAM_ERROR' })
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    }
  }, [qc])

  // ── Render ────────────────────────────────────────────────────────────────

  const isEmpty = state.messages.length === 0 && !state.streaming

  return (
    <div className="flex h-full">
      <ConversationSidebar
        conversations={state.conversations}
        activeId={state.activeConvId}
        onSelect={handleSelectConv}
        onNew={handleNew}
        onRename={handleRename}
        onDelete={handleDelete}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="flex h-14 flex-none items-center justify-between px-6 border-b border-border">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
            <h1 className="text-sm font-semibold text-foreground tracking-wide">Chat</h1>
          </div>
          <ThemeToggle />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {isEmpty ? (
            <div className="flex h-full flex-col justify-center px-8 py-12 max-w-2xl mx-auto w-full">
              {/* Greeting */}
              <h1 className="text-3xl font-bold text-foreground mb-6">
                {greetingRef.current}
              </h1>

              {/* Synte intro bubble */}
              <div className="flex items-start gap-3 mb-8">
                <div className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-[var(--accent)]">
                  <Image
                    src="/synteles_favicon.png"
                    alt="Synte"
                    width={18}
                    height={18}
                    className="object-contain brightness-0 invert"
                  />
                </div>
                <p className="text-sm text-foreground leading-relaxed pt-1">
                  Hi, I&apos;m <strong>SYNTE</strong>, I help you build and run AI agent workforces to automate your tasks. How can I assist?
                </p>
              </div>

              {/* Suggestion pills */}
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map(({ label, prompt, icon: Icon }) => (
                  <button
                    key={label}
                    onClick={() => send(prompt)}
                    className="flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-1.5 text-sm text-foreground-2 transition-colors hover:border-accent-border hover:bg-card-hover hover:text-foreground"
                  >
                    <Icon size={13} className="text-muted" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-3xl space-y-5 px-6 py-6">
              <MessageList messages={state.messages} />
              {state.streaming && (
                <StreamRenderer text={state.streamText} tools={state.streamTools} />
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="flex-none px-6 pb-4">
          <div className="mx-auto w-full max-w-3xl">
            <MessageInput
              value={state.inputText}
              onChange={(text) => dispatch({ type: 'SET_INPUT', text })}
              onSend={() => send()}
              onAddFiles={(files) =>
                dispatch({
                  type: 'ADD_FILES',
                  files: files.map(f => ({ file: f, id: crypto.randomUUID() })),
                })
              }
              onRemoveFile={(id) => dispatch({ type: 'REMOVE_FILE', id })}
              stagedFiles={state.stagedFiles}
              disabled={state.streaming}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
