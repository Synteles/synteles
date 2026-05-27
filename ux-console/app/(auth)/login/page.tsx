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

import Image from 'next/image'
import { LogIn } from 'lucide-react'
import { redirect } from 'next/navigation'
import { getServerToken } from '@/lib/auth'

interface Props {
  searchParams: Promise<{ error?: string; next?: string }>
}

const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: 'Login session expired. Please try again.',
  token_exchange_failed: 'Authentication failed. Please try again.',
  access_denied: 'Access was denied.',
}

export default async function LoginPage({ searchParams }: Props) {
  const token = await getServerToken()
  if (token) redirect('/dashboard')

  const { error, next } = await searchParams
  const errorMessage = error ? (ERROR_MESSAGES[error] ?? 'An error occurred. Please try again.') : null
  const startHref = next ? `/login/start?next=${encodeURIComponent(next)}` : '/login/start'

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 rounded-xl border bg-card p-8 shadow-sm">
        <div className="flex flex-col items-center gap-3">
          <Image
            src="/synteles_logo.svg"
            alt="Synteles"
            width={160}
            height={36}
            className="h-auto dark:invert"
            priority
          />
          <p className="text-sm text-muted-foreground">Sign in to your account</p>
        </div>

        {errorMessage && (
          <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {errorMessage}
          </div>
        )}

        <a
          href={startHref}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <LogIn className="size-4" />
          Sign in
        </a>
      </div>
    </div>
  )
}
