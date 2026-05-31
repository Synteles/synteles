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

export const config = {
  apiBaseUrl: process.env.API_BASE_URL!,
  chatStreamUrl: process.env.CHAT_STREAM_URL!,
  oidcIssuerUrl: process.env.OIDC_ISSUER_URL!,
  oidcClientId: process.env.OIDC_CLIENT_ID!,
  oidcClientSecret: process.env.OIDC_CLIENT_SECRET!,
  redirectUri: process.env.REDIRECT_URI!,
} as const

export const appOrigin = new URL(config.redirectUri).origin
