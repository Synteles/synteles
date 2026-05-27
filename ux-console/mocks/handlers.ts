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

import { http, HttpResponse } from 'msw'

const API_BASE = 'http://localhost:4000'

export const handlers = [
  http.get(`${API_BASE}/api/users/me`, () =>
    HttpResponse.json({
      sub: 'user-123',
      email: 'test@example.com',
      given_name: 'Test',
      family_name: 'User',
      org_id: 'org-456',
      org_name: 'Test Org',
    })
  ),

  http.get(`${API_BASE}/api/executions`, () =>
    HttpResponse.json({ items: [], total: 0 })
  ),

  http.get(`${API_BASE}/api/agentlets`, () =>
    HttpResponse.json({ items: [] })
  ),

  http.get(`${API_BASE}/api/conversations`, () =>
    HttpResponse.json({ items: [] })
  ),

  http.get(`${API_BASE}/api/connectors`, () =>
    HttpResponse.json({ items: [] })
  ),

  http.get(`${API_BASE}/api/model-presets`, () =>
    HttpResponse.json({ items: [] })
  ),
]
