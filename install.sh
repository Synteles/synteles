#!/usr/bin/env bash

# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

# ─── Brand colours & formatting ───────────────────────────────────────────────
# Palette: #A47FA7 purple · #ABA6AB silver · #EBECDF cream · #393840 charcoal
if [ -t 1 ] && tput colors &>/dev/null 2>&1 && [ "$(tput colors)" -ge 8 ]; then
  BOLD=$(tput bold)
  RED=$(tput setaf 1); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
  RESET=$(tput sgr0)
  _DIM=$(tput dim 2>/dev/null || tput setaf 8 2>/dev/null || printf '')
  if [[ "${COLORTERM:-}" =~ ^(truecolor|24bit)$ ]]; then
    C_HEAD=$'\e[38;2;164;127;167m'   # #A47FA7 — brand purple
    C_MUTED=$'\e[38;2;171;166;171m'  # #ABA6AB — silver grey
    C_LIGHT=$'\e[38;2;235;236;223m'  # #EBECDF — warm cream
  else
    C_HEAD=$(tput setaf 5)            # magenta fallback
    C_MUTED="$_DIM"
    C_LIGHT=$(tput setaf 7)
  fi
  LOGO="$C_HEAD"
  DIM="$C_MUTED"
else
  BOLD=''; RED=''; GREEN=''; YELLOW=''; RESET=''
  C_HEAD=''; C_MUTED=''; C_LIGHT=''; DIM=''; LOGO=''
fi

# ─── Layout helpers ───────────────────────────────────────────────────────────

# Repeat character $1 exactly $2 times
_repeat() {
  local c="$1" n="$2" s="" i=0
  while [ "$i" -lt "$n" ]; do s="${s}${c}"; i=$(( i + 1 )); done
  printf '%s' "$s"
}

# Box row for print_done — inner content area = 62 chars
# Total line visual width: "  ║  "(5) + 62 + "  ║"(3) = 70
_box_row() {
  local text="${1:-}"
  local pad=$(( 62 - ${#text} ))
  [ "$pad" -lt 0 ] && pad=0
  printf "  ${BOLD}${GREEN}║${RESET}  %s%*s  ${BOLD}${GREEN}║${RESET}\n" "$text" "$pad" ""
}
_box_div() { printf "  ${BOLD}${GREEN}╠%s╣${RESET}\n" "$(_repeat ═ 66)"; }

# ─── Print helpers ────────────────────────────────────────────────────────────
ok()   { printf "  ${GREEN}✓${RESET}  %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${RESET}  %s\n" "$*"; }
err()  { printf "  ${RED}✗${RESET}  %s\n" "$*" >&2; }
info() { printf "  %s\n" "$*"; }
dim()  { printf "  ${C_MUTED}%s${RESET}\n" "$*"; }
note() { printf "  ${C_HEAD}→${RESET}  %s\n" "$*"; }
ask()  { printf "  ${BOLD}${C_HEAD}›${RESET}  %s " "$*"; }
die()  { err "$*"; exit 1; }

# Section header: "  ╭─ N. Title ─────╮"  total visual width = 70
# "  ╭─ "(5) + title + " "(1) + dashes + "╮"(1) = 70  →  dashes = 63 - len(title)
STEP_N=0
step() {
  STEP_N=$(( STEP_N + 1 ))
  local title="${STEP_N}. $1"
  local pad=$(( 63 - ${#title} ))
  [ "$pad" -lt 1 ] && pad=1
  printf "\n${BOLD}${C_HEAD}  ╭─ %s %s╮${RESET}\n\n" "$title" "$(_repeat ─ "$pad")"
}

# Braille spinner for long background tasks
_spinner() {
  [ -t 1 ] || return
  local pid="$1" msg="$2"
  local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r  ${C_HEAD}%s${RESET}  %s" "${frames:$(( i % ${#frames} )):1}" "$msg"
    i=$(( i + 1 ))
    sleep 0.1
  done
  printf "\r%*s\r" $(( ${#msg} + 8 )) ""
}

confirm_overwrite() {
  [ -f "$1" ] || return 0
  ask "$1 already exists. Overwrite? [Y/n]:"
  read -r _ow
  [[ "$_ow" =~ ^[Nn]$ ]] && { warn "Skipping $1 — using existing file"; return 1; }
  return 0
}

# ─── Banner ───────────────────────────────────────────────────────────────────
print_banner() {
  local rule; rule=$(_repeat ─ 70)
  printf "\n"
  printf "${BOLD}${LOGO}    ███████╗██╗   ██╗███╗   ██╗████████╗███████╗██╗     ███████╗███████╗${RESET}\n"
  printf "${BOLD}${LOGO}    ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝${RESET}\n"
  printf "${BOLD}${LOGO}    ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   █████╗  ██║     █████╗  ███████╗${RESET}\n"
  printf "${BOLD}${LOGO}    ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══╝  ██║     ██╔══╝  ╚════██║${RESET}\n"
  printf "${BOLD}${LOGO}    ███████║   ██║   ██║ ╚████║   ██║   ███████╗███████╗███████╗███████║${RESET}\n"
  printf "${BOLD}${LOGO}    ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚══════╝${RESET}\n"
  printf "\n"
  printf "  ${C_MUTED}%s${RESET}\n" "$rule"
  printf "\n"
  printf "  ${BOLD}${C_LIGHT}Welcome to Platform Setup${RESET}\n"
  printf "\n"
  printf "  ${C_MUTED}Guides you through choosing your AI providers and models,${RESET}\n"
  printf "  ${C_MUTED}then generates the configuration files needed to start${RESET}\n"
  printf "  ${C_MUTED}the platform. Takes about 2 minutes.${RESET}\n"
  printf "\n"
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
check_prereqs() {
  step "System Requirements"
  local failed=0
  for cmd in docker; do
    if command -v "$cmd" &>/dev/null; then
      ok "$cmd"
    else
      err "$cmd is not installed. Install it from https://docs.docker.com/get-docker/"
      failed=1
    fi
  done
  [ "$failed" -eq 0 ] || exit 1
}

# ─── Repo root check ──────────────────────────────────────────────────────────
check_repo_root() {
  if [ ! -f .env.example ]; then
    die "Please run this script from the Synteles repository root directory."
  fi
}

# ─── Provider definitions ─────────────────────────────────────────────────────
# Format: "id;Display Name;key~default|key~default|..."
#   id           — used as PLATFORM_SECRET_<ID> (uppercased) and in platform.toml
#   Display Name — shown in prompts
#   fields       — "|"-separated list of "key~default" pairs that form the
#                  PLATFORM_SECRET_* JSON object. An empty default means the
#                  user must fill in the value; a non-empty default is pre-filled.

PROVIDERS=(
  "openai;OpenAI;OPENAI_API_KEY~"
  "anthropic;Anthropic;ANTHROPIC_API_KEY~"
  "azure_ai;Azure AI;AZURE_AI_API_KEY~|AZURE_AI_API_BASE~"
  "bedrock;Amazon Bedrock;AWS_ACCESS_KEY_ID~|AWS_SECRET_ACCESS_KEY~|AWS_REGION_NAME~"
  "gemini;Google Gemini;GEMINI_API_KEY~"
  "mistral;Mistral AI;MISTRAL_API_KEY~"
  "ollama;Ollama (local);OLLAMA_API_BASE~http://localhost:11434"
)

# ─── Runtime state ────────────────────────────────────────────────────────────
SELECTED_INDICES=()   # indices into PROVIDERS for chosen providers
SELECTED_MODELS=()    # model IDs entered by the user, parallel to SELECTED_INDICES
CHAT_SEL_I=0          # index into SELECTED_INDICES for the chat model
TAVILY_KEY=""

# ─── Provider selection ───────────────────────────────────────────────────────
select_providers() {
  step "AI Providers"
  info "Which AI providers do you want to use?"
  dim "Enter one or more numbers separated by spaces (e.g. 1 2)."
  printf "\n"
  local i _pid pname _fields
  for i in "${!PROVIDERS[@]}"; do
    IFS=';' read -r _pid pname _fields <<< "${PROVIDERS[$i]}"
    printf "  ${C_HEAD}│${RESET}  ${BOLD}%d.${RESET}  %s\n" $((i + 1)) "$pname"
  done
  local other_idx=$(( ${#PROVIDERS[@]} + 1 ))
  printf "  ${C_HEAD}│${RESET}  ${BOLD}%d.${RESET}  ${C_MUTED}Other${RESET}\n" "$other_idx"
  printf "\n"
  ask "Selection (e.g. 1 2):"
  read -r raw

  local token selected_other=0
  for token in $raw; do
    if [[ "$token" =~ ^[0-9]+$ ]] && [ "$token" -ge 1 ] && [ "$token" -le "${#PROVIDERS[@]}" ]; then
      SELECTED_INDICES+=($((token - 1)))
    elif [[ "$token" =~ ^[0-9]+$ ]] && [ "$token" -eq "$other_idx" ]; then
      selected_other=1
    else
      warn "Ignoring invalid entry: $token"
    fi
  done

  if [ "$selected_other" -eq 1 ]; then
    printf "\n"
    note "You can add any unlisted provider manually after setup:"
    dim  "  • How to configure providers → docs/configuration.md"
    dim  "  • Full provider list → https://docs.litellm.ai/docs/providers"
  fi

  if [ "${#SELECTED_INDICES[@]}" -eq 0 ]; then
    [ "$selected_other" -eq 1 ] && exit 0
    die "No valid providers selected."
  fi

  printf "\n"
  local idx _f
  for idx in "${SELECTED_INDICES[@]}"; do
    IFS=';' read -r _pid pname _f <<< "${PROVIDERS[$idx]}"
    ok "$pname"
  done
}

# ─── Model ID collection ──────────────────────────────────────────────────────
select_models() {
  step "AI Models"
  info "Enter the model name to use for each provider."
  dim "Not sure which to pick? Check your provider's documentation."
  dim "Examples: gpt-4o · claude-sonnet-4-6 · gemini-2.0-flash"
  dim "For Azure AI, enter your deployment name."
  printf "\n"

  local sel_i
  for sel_i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$sel_i]}"
    local pid pname fields
    IFS=';' read -r pid pname fields <<< "${PROVIDERS[$idx]}"

    printf "  ${BOLD}%s${RESET}\n" "$pname"
    local model_val=""
    while [ -z "$model_val" ]; do
      ask "Model name:"
      read -r model_val
      [ -z "$model_val" ] && warn "Model name cannot be empty."
    done
    SELECTED_MODELS+=("$model_val")
    ok "  $model_val"
    printf "\n"
  done
}

# ─── Chat model selection ─────────────────────────────────────────────────────
select_chat_model() {
  if [ "${#SELECTED_INDICES[@]}" -eq 1 ]; then
    CHAT_SEL_I=0
    local idx="${SELECTED_INDICES[0]}"
    local _pid pname _f
    IFS=';' read -r _pid pname _f <<< "${PROVIDERS[$idx]}"
    printf "\n"
    warn "$pname will be used for both Synte chat assistant and platform default models."
    return
  fi

  step "Synte Chat Assistant"
  info "Synte is the AI assistant built into the platform UI."
  dim "Which of your configured providers should power it?"
  printf "\n"
  local i
  for i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$i]}"
    local _pid pname _f
    IFS=';' read -r _pid pname _f <<< "${PROVIDERS[$idx]}"
    printf "  ${C_HEAD}│${RESET}  ${BOLD}%d.${RESET}  %-20s  ${C_MUTED}%s${RESET}\n" \
      $((i + 1)) "$pname" "${SELECTED_MODELS[$i]}"
  done
  printf "\n"
  ask "Choice [1]:"
  read -r choice
  choice="${choice:-1}"

  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#SELECTED_INDICES[@]}" ]; then
    CHAT_SEL_I=$((choice - 1))
  else
    warn "Invalid — defaulting to first provider"
    CHAT_SEL_I=0
  fi

  local idx="${SELECTED_INDICES[$CHAT_SEL_I]}"
  local _pid pname _f
  IFS=';' read -r _pid pname _f <<< "${PROVIDERS[$idx]}"
  ok "Chat model: $pname — ${SELECTED_MODELS[$CHAT_SEL_I]}"
}

# ─── Tavily key ───────────────────────────────────────────────────────────────
ask_tavily() {
  step "Web Search (optional)"
  info "Tavily lets your AI workers search the web during task execution."
  dim "Get a free API key at https://app.tavily.com — press Enter to skip for now."
  printf "\n"
  ask "Tavily API key:"
  read -rs TAVILY_KEY; printf "\n"
  if [ -n "$TAVILY_KEY" ]; then
    ok "Web search enabled"
  else
    warn "Skipped — you can add a Tavily key to .env later to enable web search"
  fi
}

# ─── .env generation ──────────────────────────────────────────────────────────

# Build a JSON object from a fields string ("KEY~default|KEY~default").
# Values with a non-empty default are pre-filled; others are left as "".
_build_credential_json() {
  local fields="$1" json="{" first=1
  local field_defs field_def key default_val
  IFS='|' read -ra field_defs <<< "$fields"
  for field_def in "${field_defs[@]}"; do
    IFS='~' read -r key default_val <<< "$field_def"
    [ "$first" -eq 0 ] && json+=", "
    json+="\"${key}\": \"${default_val}\""
    first=0
  done
  printf '%s' "${json}}"
}

# True (returns 0) when the JSON contains at least one empty "" value.
_json_needs_fill() { [[ "$1" == *'""'* ]]; }

# Processes .env.example into .env, substituting TAVILY_API_KEY and
# SECRET_ENCRYPTION_KEY, and inserting PLATFORM_SECRET_* lines before the
# encryption key section. Uses mktemp + mv for an atomic write.
_write_env_from_template() {
  local enc_key="$1"

  local creds_tmp env_tmp
  creds_tmp=$(mktemp)
  env_tmp=$(mktemp)
  trap "rm -f '$creds_tmp' '$env_tmp'" RETURN

  local sel_i needs_fill=0
  for sel_i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$sel_i]}"
    local pid pname fields
    IFS=';' read -r pid pname fields <<< "${PROVIDERS[$idx]}"
    local var_name="PLATFORM_SECRET_$(printf '%s' "$pid" | tr '[:lower:]' '[:upper:]')"
    local json
    json=$(_build_credential_json "$fields")
    if _json_needs_fill "$json"; then
      printf "# %s — fill in your credentials\n%s=%s\n\n" "$pname" "$var_name" "$json"
      needs_fill=1
    else
      printf "# %s\n%s=%s\n\n" "$pname" "$var_name" "$json"
    fi
  done > "$creds_tmp"

  CREDS_FILE="$creds_tmp" TAVILY="$TAVILY_KEY" ENC_KEY="$enc_key" \
  awk '
    /^TAVILY_API_KEY=/ {
      print "TAVILY_API_KEY=" ENVIRON["TAVILY"]
      next
    }
    /^SECRET_ENCRYPTION_KEY=/ {
      creds_file = ENVIRON["CREDS_FILE"]
      while ((getline line < creds_file) > 0) print line
      close(creds_file)
      print "SECRET_ENCRYPTION_KEY=" ENVIRON["ENC_KEY"]
      next
    }
    { print }
  ' .env.example > "$env_tmp"

  mv "$env_tmp" .env
  if [ "$needs_fill" -eq 1 ]; then
    warn "LLM provider credentials are missing in .env — open it and replace"
    warn "the empty \"\" values with your API keys before starting the platform."
    note "Credential format reference → docs/configuration.md"
  fi
}

# Appends any PLATFORM_SECRET_* vars absent from the existing .env, and fills
# SECRET_ENCRYPTION_KEY / TAVILY_API_KEY if present but empty.
_merge_env() {
  local enc_key="$1"
  local changed=0 needs_fill=0

  local sel_i
  for sel_i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$sel_i]}"
    local pid pname fields
    IFS=';' read -r pid pname fields <<< "${PROVIDERS[$idx]}"
    local var_name="PLATFORM_SECRET_$(printf '%s' "$pid" | tr '[:lower:]' '[:upper:]')"
    local json
    json=$(_build_credential_json "$fields")
    if ! grep -q "^${var_name}=" .env; then
      if _json_needs_fill "$json"; then
        printf "\n# %s — fill in your credentials\n%s=%s\n" "$pname" "$var_name" "$json" >> .env
        needs_fill=1
      else
        printf "\n# %s\n%s=%s\n" "$pname" "$var_name" "$json" >> .env
      fi
      ok "  Added credentials for $pname"
      changed=1
    else
      dim "  $pname already configured — skipped"
    fi
  done

  if ! grep -q "^SECRET_ENCRYPTION_KEY=." .env; then
    local tmp; tmp=$(mktemp)
    if grep -q "^SECRET_ENCRYPTION_KEY=" .env; then
      awk -v k="$enc_key" \
        '/^SECRET_ENCRYPTION_KEY=/ { print "SECRET_ENCRYPTION_KEY=" k; next } { print }' \
        .env > "$tmp" && mv "$tmp" .env
    else
      printf "\nSECRET_ENCRYPTION_KEY=%s\n" "$enc_key" >> .env
    fi
    ok "  Generated encryption key"
    changed=1
  fi

  if [ -n "$TAVILY_KEY" ] && ! grep -q "^TAVILY_API_KEY=." .env; then
    local tmp; tmp=$(mktemp)
    if grep -q "^TAVILY_API_KEY=" .env; then
      awk -v k="$TAVILY_KEY" \
        '/^TAVILY_API_KEY=/ { print "TAVILY_API_KEY=" k; next } { print }' \
        .env > "$tmp" && mv "$tmp" .env
    else
      printf "\nTAVILY_API_KEY=%s\n" "$TAVILY_KEY" >> .env
    fi
    ok "  Set Tavily web search key"
    changed=1
  fi

  [ "$changed" -eq 1 ] && ok "Updated .env with new providers" || ok ".env is already up to date"
  if [ "$needs_fill" -eq 1 ]; then
    warn "LLM provider credentials are missing in .env — open it and replace"
    warn "the empty \"\" values with your API keys before starting the platform."
    note "Credential format reference → docs/configuration.md"
  fi
}

generate_env() {
  step "Credentials & Config"

  local mode="create"
  if [ -f .env ]; then
    ask ".env already exists. [O]verwrite / [m]erge new providers / [s]kip [O/m/s]:"
    read -r _c
    case "${_c:-O}" in
      [Mm]) mode="merge" ;;
      [Ss]) warn "Keeping existing .env unchanged"; return ;;
    esac
  fi

  grep -qxF '.env' .gitignore 2>/dev/null \
    || warn ".env is not in .gitignore — add it to prevent accidentally committing secrets to git"

  local enc_key
  enc_key=$(od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n')

  if [ "$mode" = "create" ]; then
    _write_env_from_template "$enc_key"
    ok "Generated .env"
  else
    _merge_env "$enc_key"
  fi
}

# ─── platform.toml generation ─────────────────────────────────────────────────
generate_platform_toml() {
  step "Model Configuration"

  confirm_overwrite platform.toml || return

  local chat_idx="${SELECTED_INDICES[$CHAT_SEL_I]}"
  local chat_pid _pname _fields
  IFS=';' read -r chat_pid _pname _fields <<< "${PROVIDERS[$chat_idx]}"
  local chat_model="${SELECTED_MODELS[$CHAT_SEL_I]}"

  local tmp
  tmp=$(mktemp)

  {
    printf "# Generated by install.sh\n\n"
    printf "# ── Chat engine ─────────────────────────────────────────────────────────────\n"
    printf "[chat]\n"
    printf "model_id    = \"%s/%s\"\n" "$chat_pid" "$chat_model"
    printf "secret_name = \"%s\"\n" "$chat_pid"
    printf "\n"
    printf "# ── Platform default models ──────────────────────────────────────────────────\n"

    local sel_i
    for sel_i in "${!SELECTED_INDICES[@]}"; do
      local idx="${SELECTED_INDICES[$sel_i]}"
      local pid pname fields
      IFS=';' read -r pid pname fields <<< "${PROVIDERS[$idx]}"
      local model="${SELECTED_MODELS[$sel_i]}"
      local safe_id
      safe_id=$(printf '%s' "$pid" | tr -d '_')

      printf "\n[[model]]\n"
      printf "id                  = \"platform_%s\"\n" "$safe_id"
      printf "label               = \"%s\"\n" "${model##*/}"
      printf "provider            = \"%s\"\n" "$pid"
      printf "model_id            = \"%s\"\n" "$model"
      printf "secret_name         = \"%s\"\n" "$pid"
      printf "default_temperature = 1.0\n"
    done
  } > "$tmp"

  mv "$tmp" platform.toml
  ok "Generated platform.toml"
}

# ─── Build durable-agentlet image ────────────────────────────────────────────
build_durable_agentlet() {
  step "Docker Image"
  dim "Building the image needed for long-running workflow support."
  dim "This may take a minute on first run."
  printf "\n"
  docker compose build durable-agentlet > /dev/null 2>&1 &
  local _bpid=$!
  _spinner "$_bpid" "Building image …"
  if wait "$_bpid"; then
    ok "Docker image built successfully"
  else
    warn "Docker image build failed — run 'docker compose build durable-agentlet' to retry"
  fi
}

# ─── Done ─────────────────────────────────────────────────────────────────────
# Box geometry: total width 70
#   "  ╔"(3) + 66×═ + "╗"(1) = 70
#   "  ║  "(5) + content(62) + "  ║"(3) = 70
print_done() {
  local thick; thick=$(_repeat ═ 66)
  printf "\n"
  printf "  ${BOLD}${GREEN}╔%s╗${RESET}\n" "$thick"
  _box_row ""
  _box_row "✓  Setup complete!"
  _box_row ""
  _box_div
  _box_row ""
  _box_row "Files written:"
  _box_row "  .env            LLM credentials, service config & secrets"
  _box_row "  platform.toml   model IDs and provider routing"
  _box_row ""
  _box_div
  _box_row ""
  _box_row "Next steps:"
  _box_row ""
  _box_row "  1.  Open .env and fill in your LLM provider API keys."
  _box_row "      Replace each empty \"\" value with the real credential."
  _box_row "      docs/configuration.md — credential format reference"
  _box_row "      https://docs.litellm.ai/docs/providers — provider list"
  _box_row ""
  _box_row "  2.  (Optional) Review platform.toml to adjust model IDs"
  _box_row "      or add additional providers."
  _box_row ""
  _box_row "  3.  Start the platform:"
  _box_row ""
  _box_row "        docker compose up -d"
  _box_row ""
  _box_row "  ⚠  Never commit .env to git — it contains secrets."
  _box_row ""
  printf "  ${BOLD}${GREEN}╚%s╝${RESET}\n" "$thick"
  printf "\n"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
  print_banner
  check_prereqs
  check_repo_root
  select_providers
  select_models
  select_chat_model
  ask_tavily
  generate_env
  generate_platform_toml
  build_durable_agentlet
  print_done
}

main "$@"
