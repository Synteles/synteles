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

import { redirect } from 'next/navigation'
import { getServerToken, getUser } from '@/lib/auth'
import { AppSidebar } from '@/components/sidebar/sidebar'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { WatchdogProvider } from '@/components/executions/watchdog-provider'
import { ExecutionSheetProvider } from '@/components/executions/execution-sheet-provider'
import { SessionRefresher } from '@/components/auth/session-refresher'

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const token = await getServerToken()
  if (!token) redirect('/login')

  const user = await getUser()

  return (
    <SidebarProvider className="h-screen overflow-hidden">
      <SessionRefresher />
      <WatchdogProvider>
        <ExecutionSheetProvider>
          <AppSidebar user={user} />
          <SidebarInset className="overflow-hidden">
            {children}
          </SidebarInset>
        </ExecutionSheetProvider>
      </WatchdogProvider>
    </SidebarProvider>
  )
}
