# Third-Party Notices

This document lists the open-source libraries used by Synteles, together with
their licenses and copyright holders. It is provided for informational purposes.
Apache 2.0 packages that carry a NOTICE file are additionally listed in the
repository-root `NOTICE` file, as required by Section 4(d) of that license.

---

## Python dependencies

### core-service · durable-worker · scheduler-service · synte-service · platform-db

| Package | License | Copyright |
|---|---|---|
| FastAPI | MIT | Sebastián Ramírez |
| Uvicorn | BSD-3-Clause | Encode OSS Ltd. |
| PyJWT | MIT | José Padilla |
| boto3 | Apache-2.0 | Amazon.com, Inc. or its affiliates |
| botocore | Apache-2.0 | Amazon.com, Inc. or its affiliates |
| httpx | BSD-3-Clause | Encode OSS Ltd. |
| PyYAML | MIT | Kirill Simonov |
| docker (docker-py) | Apache-2.0 | Docker, Inc. |
| SQLAlchemy | MIT | Michael Bayer |
| asyncpg | Apache-2.0 | MagicStack Inc. and asyncpg authors |
| psycopg2-binary | LGPL-3.0 | Federico Di Gregorio, Daniele Varrazzo |
| Alembic | MIT | Michael Bayer |
| cryptography | Apache-2.0 / BSD | Individual contributors (PyCA) |
| strands-agents | Apache-2.0 | Amazon.com, Inc. or its affiliates |
| strands-agents-tools | Apache-2.0 | Amazon.com, Inc. or its affiliates |
| LiteLLM | MIT | BerriAI |
| jsonschema | MIT | Julian Berman |
| requests | Apache-2.0 | Kenneth Reitz |
| temporalio | MIT | Temporal Technologies Inc. |
| mcp (Model Context Protocol Python SDK) | MIT | Anthropic, PBC |

### Development / tooling (not distributed)

| Package | License | Copyright |
|---|---|---|
| Ruff | MIT | Astral Software Inc. |
| Mypy | MIT | Jukka Lehtosalo |
| Bandit | Apache-2.0 | PyCQA |
| pytest | MIT | Holger Krekel |
| pytest-asyncio | Apache-2.0 | Tin Tvrtković |
| pytest-cov | MIT | Marc Schlaich |
| pytest-mock | MIT | Bruno Oliveira |
| respx | BSD-3-Clause | Jonas Lundberg |

---

## JavaScript / TypeScript dependencies (ux-console)

| Package | License | Copyright |
|---|---|---|
| Next.js | MIT | Vercel, Inc. |
| React | MIT | Meta Platforms, Inc. |
| react-dom | MIT | Meta Platforms, Inc. |
| TypeScript | Apache-2.0 | Microsoft Corporation |
| Tailwind CSS | MIT | Tailwind Labs, Inc. |
| @tanstack/react-query | MIT | Tanner Linsley |
| @codemirror/view | MIT | Marijn Haverbeke |
| @codemirror/lang-json | MIT | Marijn Haverbeke |
| @codemirror/lang-yaml | MIT | Marijn Haverbeke |
| @uiw/react-codemirror | MIT | UIW |
| class-variance-authority | Apache-2.0 | Joe Bell |
| clsx | MIT | Luke Edwards |
| tailwind-merge | MIT | Dany Castillo |
| lucide-react | ISC | Lucide Contributors |
| next-themes | MIT | Pacocoursey |
| react-markdown | MIT | Titus Wormer |
| remark-gfm | MIT | Titus Wormer |
| js-yaml | MIT | Vitaly Puzrin |
| sonner | MIT | Emil Kowalski |
| @base-ui/react | MIT | MUI SAS |
| shadcn/ui | MIT | shadcn |
| tw-animate-css | MIT | Wombosvideo |
| @radix-ui/react-toggle | MIT | WorkOS, Inc. |
| @radix-ui/react-toggle-group | MIT | WorkOS, Inc. |

### Development / tooling (not distributed)

| Package | License | Copyright |
|---|---|---|
| Vitest | MIT | Vitest contributors |
| @vitest/coverage-v8 | MIT | Vitest contributors |
| @testing-library/react | MIT | Kent C. Dodds |
| @testing-library/jest-dom | MIT | Testing Library contributors |
| @testing-library/user-event | MIT | Testing Library contributors |
| msw | MIT | Artem Zakharchenko |
| @playwright/test | Apache-2.0 | Microsoft Corporation |
| jsdom | MIT | jsdom contributors |
| PostCSS | MIT | Andrey Sitnik |
| @tailwindcss/postcss | MIT | Tailwind Labs, Inc. |
| @vitejs/plugin-react | MIT | Vite contributors |

---

## License texts

Full license texts are available at the URLs listed in each package's
repository, or via the package manager metadata (`pip show <pkg>`,
`npm info <pkg>`). The complete text of the Apache License, Version 2.0,
is reproduced in the `LICENSE` file at the root of this repository.
