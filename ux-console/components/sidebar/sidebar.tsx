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

import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import {
  MessageSquare, Zap, Settings, LogOut,
  Key, ChevronUp, Plug, KeyRound, Cpu,
  ChevronsUpDown, Check, Building2, User, Copy,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { UserInfo } from '@/lib/auth'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { FieldGroup, Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from '@/components/ui/sidebar'
import { ActiveRunsWidget } from '@/components/executions/active-runs-widget'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const NAV_ITEMS = [
  { href: '/dashboard/chat',       label: 'Chat',       icon: MessageSquare },
  { href: '/dashboard/agentlets',  label: 'Agentlets',  icon: Zap },
  { href: '/dashboard/connectors', label: 'Connectors', icon: Plug },
]

// ── Org Switcher ─────────────────────────────────────────────────────────────
function OrgSwitcher({ user }: { user: UserInfo | null }) {
  const { state } = useSidebar()
  const orgName = user?.orgName ?? 'Organization'

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<SidebarMenuButton size="lg" tooltip={orgName} />}
          >
            <div className="flex size-8 flex-none items-center justify-center rounded-md bg-accent text-white">
              <Building2 className="size-4" />
            </div>
            <div className="grid flex-1 min-w-0 text-left leading-tight">
              <span className="truncate text-sm font-semibold">{orgName}</span>
              <span className="truncate text-xs opacity-60">Organization</span>
            </div>
            <ChevronsUpDown className="ml-auto" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={state === 'collapsed' ? 'right' : 'bottom'}
            align="start"
            className="w-56"
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel>Organization</DropdownMenuLabel>
              <DropdownMenuItem>
                <div className="flex size-6 flex-none items-center justify-center rounded bg-accent text-white">
                  <Building2 className="size-3.5" />
                </div>
                <span className="flex-1 truncate">{orgName}</span>
                <Check className="ml-auto opacity-60" />
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

// ── Profile Dialog ────────────────────────────────────────────────────────────
function ProfileDialog({ user, open, onOpenChange }: {
  user: UserInfo | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [copied, setCopied] = useState(false)
  const orgId = user?.orgId ?? ''

  function handleCopy() {
    navigator.clipboard.writeText(orgId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const infoFields = [
    { label: 'Full name',    value: user?.name ?? '',    mono: false },
    { label: 'Email',        value: user?.email ?? '',   mono: false },
    { label: 'User ID',      value: user?.userId ?? '',  mono: true  },
    { label: 'Organisation', value: user?.orgName ?? '', mono: false },
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md gap-5">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold">Profile</DialogTitle>
        </DialogHeader>
        <FieldGroup className="gap-4">
          {infoFields.map(({ label, value, mono }) => (
            <Field key={label}>
              <FieldLabel className="text-muted-foreground">{label}</FieldLabel>
              <Input
                readOnly
                tabIndex={-1}
                value={value}
                className={cn(
                  'bg-surface border-border cursor-default text-muted-foreground focus:border-border focus:ring-0 focus:shadow-none',
                  mono && 'font-mono text-xs'
                )}
              />
            </Field>
          ))}
          <Field>
            <FieldLabel className="text-muted-foreground">Organisation ID</FieldLabel>
            <div className="group relative">
              <Input
                readOnly
                tabIndex={-1}
                value={orgId}
                className="bg-surface border-border cursor-default text-muted-foreground font-mono text-xs focus:border-border focus:ring-0 focus:shadow-none pr-9"
              />
              <button
                onClick={handleCopy}
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex size-5 items-center justify-center rounded text-muted-foreground hover:text-foreground"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
              </button>
            </div>
          </Field>
        </FieldGroup>
        <div className="flex justify-end">
          <DialogClose render={<Button />}>Close</DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── User Widget ───────────────────────────────────────────────────────────────
function UserWidget({ user }: { user: UserInfo | null }) {
  const [open, setOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const { state } = useSidebar()
  const collapsed = state === 'collapsed'
  const displayName = user?.name ?? 'Account'
  const initials    = user?.initials ?? '?'
  const orgName     = user?.orgName ?? null
  const email       = user?.email ?? ''

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <div className="relative">
          {open && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
              <div className={cn(
                'absolute z-20 mb-1 rounded-xl border border-sidebar-border bg-sidebar shadow-xl overflow-hidden w-56',
                collapsed
                  ? 'bottom-0 left-full ml-2'
                  : 'bottom-full left-0 right-0'
              )}>
                <div className="flex items-center gap-3 px-3 py-3 border-b border-sidebar-border">
                  <div className="flex size-9 flex-none items-center justify-center rounded-full bg-accent text-white text-sm font-semibold">
                    {initials}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-sidebar-foreground">{displayName}</p>
                    {orgName && <p className="truncate text-xs text-sidebar-foreground/60">{orgName}</p>}
                    {email && !orgName && <p className="truncate text-xs text-sidebar-foreground/60">{email}</p>}
                  </div>
                </div>
                <div className="py-1">
                  <button onClick={() => { setOpen(false); setProfileOpen(true) }} className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <User className="size-3.5 flex-none opacity-60" />
                    Profile
                  </button>
                  <div className="my-1 mx-2 border-t border-sidebar-border" />
                  <Link href="/dashboard/secrets" onClick={() => setOpen(false)} className="flex items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <KeyRound className="size-3.5 flex-none opacity-60" />
                    Secrets
                  </Link>
                  <Link href="/dashboard/models" onClick={() => setOpen(false)} className="flex items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <Cpu className="size-3.5 flex-none opacity-60" />
                    Models
                  </Link>
                  <Link href="/dashboard/api-keys" onClick={() => setOpen(false)} className="flex items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <Key className="size-3.5 flex-none opacity-60" />
                    API keys
                  </Link>
                  <div className="my-1 mx-2 border-t border-sidebar-border" />
                  <Link href="/dashboard/settings" onClick={() => setOpen(false)} className="flex items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <Settings className="size-3.5 flex-none opacity-60" />
                    Settings
                  </Link>
                  <div className="my-1 mx-2 border-t border-sidebar-border" />
                  <a href="/logout" className="flex items-center gap-2.5 px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                    <LogOut className="size-3.5 flex-none opacity-60" />
                    Sign out
                  </a>
                </div>
              </div>
            </>
          )}
          <ProfileDialog user={user} open={profileOpen} onOpenChange={setProfileOpen} />
          <SidebarMenuButton
            size="lg"
            onClick={() => setOpen(v => !v)}
            tooltip={displayName}
            data-open={open || undefined}
          >
            <div className="flex size-8 flex-none items-center justify-center rounded-full bg-accent text-white text-xs font-semibold">
              {initials}
            </div>
            <div className="grid flex-1 min-w-0 text-left text-sm leading-tight">
              <span className="truncate font-semibold">{displayName}</span>
              {email && <span className="truncate text-xs opacity-60">{email}</span>}
            </div>
            <ChevronUp className={cn('ml-auto transition-transform', open && 'rotate-180')} />
          </SidebarMenuButton>
        </div>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

// ── App Sidebar ───────────────────────────────────────────────────────────────
export function AppSidebar({ user }: { user: UserInfo | null }) {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-0 p-0">
        {/* Logo */}
        <div className="flex h-14 items-center px-4">
          <div className="group-data-[collapsible=icon]:hidden overflow-hidden">
            <Image
              src="/synteles_logo.svg"
              alt="Synteles"
              width={130}
              height={29}
              className="h-auto object-contain dark:invert"
              priority
            />
          </div>
          <div className="hidden group-data-[collapsible=icon]:flex items-center justify-center w-full">
            <Image
              src="/synteles_favicon.png"
              alt="Synteles"
              width={24}
              height={24}
              className="object-contain dark:invert"
              priority
            />
          </div>
        </div>
        {/* Org Switcher */}
        <div className="px-2 pb-2">
          <OrgSwitcher user={user} />
        </div>
        <SidebarSeparator />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton
                    render={<Link href={href} />}
                    isActive={pathname.startsWith(href)}
                    tooltip={label}
                  >
                    <Icon />
                    <span>{label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <ActiveRunsWidget />

      <SidebarFooter>
        <UserWidget user={user} />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
