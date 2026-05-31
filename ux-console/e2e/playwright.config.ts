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

import { defineConfig, devices } from '@playwright/test'
import { MOCK_OIDC_ISSUER } from './oidc-mock'

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  globalSetup: './global-setup.ts',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // reuseExistingServer is intentionally false: the webServer.env below must
  // reach the Next.js process, which only happens when Playwright spawns it.
  // Stop any running `pnpm dev` on port 3000 before running `pnpm test:e2e`.
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:3000/api/health',
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      OIDC_ISSUER_URL: MOCK_OIDC_ISSUER,
      OIDC_CLIENT_ID: 'test-client',
      OIDC_CLIENT_SECRET: 'test-secret',
      REDIRECT_URI: 'http://localhost:3000/callback',
      // API_BASE_URL is not reachable in the e2e environment; auth.ts catches
      // the resulting errors and returns null for user info, which is fine for
      // auth flow tests that only assert on URL and cookie state.
      API_BASE_URL: `${MOCK_OIDC_ISSUER}`,
      CHAT_STREAM_URL: `${MOCK_OIDC_ISSUER}`,
    },
  },
})
