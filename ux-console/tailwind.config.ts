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

import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:              'var(--bg)',
        surface:         'var(--surface)',
        card:            'var(--card)',
        'card-hover':    'var(--card-hover)',
        foreground:      'var(--text)',
        'foreground-2':  'var(--text-2)',
        muted:           'var(--text-muted)',
        faint:           'var(--text-faint)',
        inv:             'var(--text-inv)',
        'inv-2':         'var(--text-inv-2)',
        'inv-muted':     'var(--text-inv-muted)',
        accent:          'var(--accent)',
        'accent-hover':  'var(--accent-hover)',
        'accent-light':  'var(--accent-light)',
        'accent-border': 'var(--accent-border)',
        'accent-focus':  'var(--accent-focus)',
        'accent-muted':  'var(--accent-muted)',
        border:          'var(--border)',
        'border-2':      'var(--border-2)',
        sidebar:                      'var(--sidebar-bg)',
        'sidebar-foreground':         'var(--text)',
        'sidebar-hover':              'var(--sidebar-hover)',
        'sidebar-active':             'var(--sidebar-active)',
        'sidebar-border':             'var(--sidebar-border)',
        'sidebar-accent':             'var(--sidebar-hover)',
        'sidebar-accent-foreground':  'var(--text)',
        'sidebar-ring':               'var(--accent-focus)',
        running:         'var(--running)',
        'running-bg':    'var(--running-bg)',
        'running-border':'var(--running-border)',
        success:         'var(--success)',
        'success-bg':    'var(--success-bg)',
        'success-border':'var(--success-border)',
        error:           'var(--error)',
        'error-bg':      'var(--error-bg)',
        'error-border':  'var(--error-border)',
        'error-focus':   'var(--error-focus)',

        /* ── shadcn standard tokens ── */
        background:              'var(--bg)',
        primary:                 'var(--accent)',
        'primary-foreground':    '#ffffff',
        secondary:               'var(--surface)',
        'secondary-foreground':  'var(--text-2)',
        'muted-foreground':      'var(--text-muted)',
        popover:                 'var(--card)',
        'popover-foreground':    'var(--text)',
        destructive:             'var(--error)',
        'destructive-foreground':'#ffffff',
        input:                   'var(--border)',
        ring:                    'var(--accent-focus)',
        'accent-foreground':     '#ffffff',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
    },
  },
  plugins: [],
}

export default config
