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

import { Settings } from 'lucide-react'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyContent } from '@/components/ui/empty'

export function SettingsPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <h1 className="text-sm font-semibold text-foreground">Settings</h1>
        </div>
        <ThemeToggle />
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        <Empty>
          <EmptyHeader>
            <EmptyMedia><Settings size={32} className="text-faint" /></EmptyMedia>
            <EmptyTitle>Settings coming soon</EmptyTitle>
          </EmptyHeader>
          <EmptyContent>
            <p className="text-sm text-muted">Configuration options will appear here.</p>
          </EmptyContent>
        </Empty>
      </div>
    </div>
  )
}
