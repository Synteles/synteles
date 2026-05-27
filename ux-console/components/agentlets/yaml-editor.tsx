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

import { useEffect, useState, useTransition } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { yaml } from '@codemirror/lang-yaml'
import { EditorView } from '@codemirror/view'
import { Copy, Check, WandSparkles, WrapText, Download } from 'lucide-react'
import * as jsYaml from 'js-yaml'
import { getAgentletYaml, saveAgentletYaml } from '@/app/(dashboard)/dashboard/agentlets/actions'
import { useColorScheme } from '@/lib/use-color-scheme'
import { cn } from '@/lib/utils'

interface Props {
  agentletId: string
  onBack: () => void
  onSaved: () => void
}

const editorTheme = EditorView.theme({
  '&': { fontSize: '12px', height: '100%' },
  '.cm-scroller': { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflow: 'auto' },
  '.cm-content': { padding: '8px 0' },
  '.cm-line': { padding: '0 12px' },
  '&.cm-focused': { outline: 'none' },
})

export function YamlEditor({ agentletId, onBack, onSaved }: Props) {
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [formatError, setFormatError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [pending, startTransition] = useTransition()
  const [wordWrap, setWordWrap] = useState(false)
  const scheme = useColorScheme()

  useEffect(() => {
    setLoading(true)
    setFetchError(null)
    getAgentletYaml(agentletId).then(res => {
      if ('error' in res) setFetchError(res.error)
      else setValue(res.yaml)
      setLoading(false)
    })
  }, [agentletId])

  function handleFormat() {
    setFormatError(null)
    try {
      const parsed = jsYaml.load(value)
      setValue(jsYaml.dump(parsed, { indent: 2, lineWidth: 120 }))
    } catch (e) {
      setFormatError(e instanceof Error ? e.message : 'Invalid YAML')
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleDownload() {
    let filename = agentletId
    try {
      const parsed = jsYaml.load(value) as Record<string, unknown>
      const name = (parsed?.agentlet as Record<string, unknown>)?.name ?? parsed?.name
      if (typeof name === 'string' && name) filename = name
    } catch {}
    const blob = new Blob([value], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename.endsWith('.yaml') ? filename : `${filename}.yaml`
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleSave() {
    setSaveError(null)
    startTransition(async () => {
      const res = await saveAgentletYaml(agentletId, value)
      if (res.error) { setSaveError(res.error); return }
      onSaved()
    })
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div className="flex items-center gap-2">
          <button
            onClick={onBack}
            className="rounded-md p-1.5 text-muted hover:bg-surface hover:text-foreground transition-colors"
            title="Back"
          >
            ←
          </button>
          <h2 className="font-semibold text-foreground">YAML editor</h2>
        </div>
      </div>

      {/* Editor body */}
      <div className="group/yaml relative flex-1 overflow-hidden bg-surface">
        {/* Hover buttons */}
        {!loading && !fetchError && (
          <div className="absolute right-2 top-2 z-10 flex items-center gap-1 opacity-0 group-hover/yaml:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={handleFormat}
              title="Format YAML"
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
        )}
        {loading ? (
          <div className="flex h-full items-center justify-center text-xs text-muted">Loading…</div>
        ) : fetchError ? (
          <div className="flex h-full items-center justify-center text-xs text-error px-6 text-center">{fetchError}</div>
        ) : (
          <CodeMirror
            value={value}
            onChange={setValue}
            theme={scheme}
            extensions={[yaml(), editorTheme, ...(wordWrap ? [EditorView.lineWrapping] : [])]}

            height="100%"
            style={{ height: '100%' }}
            basicSetup={{
              lineNumbers: true,
              foldGutter: true,
              highlightActiveLine: true,
              indentOnInput: true,
              tabSize: 2,
            }}
          />
        )}
      </div>

      {/* Footer */}
      <div className="flex flex-col gap-2 border-t border-border px-6 py-4">
        {(saveError || formatError) && (
          <p className="text-xs text-error">{saveError ?? formatError}</p>
        )}
        <div className="flex items-center justify-between">
          <button
            onClick={handleDownload}
            disabled={loading || !!fetchError}
            className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download size={14} /> Download
          </button>
          <div className="flex items-center gap-2">
          <button
            onClick={onBack}
            className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:bg-surface hover:text-foreground transition-colors"
          >
            Back
          </button>
          <button
            onClick={handleSave}
            disabled={loading || !!fetchError || pending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover transition-colors disabled:bg-accent-muted disabled:text-white/60 disabled:cursor-not-allowed"
          >
            {pending ? 'Saving…' : 'Save YAML'}
          </button>
          </div>
        </div>
      </div>
    </div>
  )
}
