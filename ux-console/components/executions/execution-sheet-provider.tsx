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

import { createContext, useContext, useState } from 'react'
import { ExecutionDetailSheet } from './execution-detail-sheet'

interface ExecutionSheetContextValue {
  openExecution: (id: string) => void
}

const ExecutionSheetContext = createContext<ExecutionSheetContextValue | null>(null)

export function useExecutionSheet() {
  const ctx = useContext(ExecutionSheetContext)
  if (!ctx) throw new Error('useExecutionSheet must be used inside ExecutionSheetProvider')
  return ctx
}

export function ExecutionSheetProvider({ children }: { children: React.ReactNode }) {
  const [execId, setExecId] = useState<string | null>(null)

  return (
    <ExecutionSheetContext.Provider value={{ openExecution: setExecId }}>
      {children}
      <ExecutionDetailSheet executionId={execId} onClose={() => setExecId(null)} />
    </ExecutionSheetContext.Provider>
  )
}
