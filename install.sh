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

# ─── Colours & formatting ─────────────────────────────────────────────────────
if [ -t 1 ] && tput colors &>/dev/null 2>&1 && [ "$(tput colors)" -ge 8 ]; then
  BOLD=$(tput bold)
  RED=$(tput setaf 1); GREEN=$(tput setaf 2); YELLOW=$(tput setaf 3)
  BLUE=$(tput setaf 4); CYAN=$(tput setaf 6)
  DIM=$(tput dim 2>/dev/null || tput setaf 8 2>/dev/null || printf '')
  RESET=$(tput sgr0)
else
  BOLD=''; RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; DIM=''; RESET=''
fi

ok()   { printf "  ${GREEN}✓${RESET}  %s\n" "$1"; }
warn() { printf "  ${YELLOW}⚠${RESET}  %s\n" "$1"; }
err()  { printf "  ${RED}✗${RESET}  %s\n" "$1" >&2; }
info() { printf "  %s\n" "$1"; }
dim()  { printf "  ${DIM}%s${RESET}\n" "$1"; }
step() { printf "\n${BOLD}${BLUE}  ── %s ──${RESET}\n\n" "$1"; }
ask()  { printf "  ${CYAN}?${RESET}  %s " "$1"; }
die()  { err "$1"; exit 1; }

# ─── Banner ───────────────────────────────────────────────────────────────────
print_banner() {
  printf "\n"
  printf "${BOLD}${CYAN}  ┌────────────────────────────────────────┐${RESET}\n"
  printf "${BOLD}${CYAN}  │      Synteles  ·  Platform Setup       │${RESET}\n"
  printf "${BOLD}${CYAN}  └────────────────────────────────────────┘${RESET}\n"
  printf "\n"
  dim  "Configures LLM providers, generates .env"
  dim  "and config/platform.toml, then pulls the stack image."
  printf "\n"
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
check_prereqs() {
  step "Prerequisites"
  local failed=0
  for cmd in docker; do
    if command -v "$cmd" &>/dev/null; then
      ok "$cmd"
    else
      err "$cmd not found — please install it first"
      failed=1
    fi
  done
  [ "$failed" -eq 0 ] || exit 1
}

# ─── Repo root check ──────────────────────────────────────────────────────────
check_repo_root() {
  if [ ! -f .env.example ]; then
    die "Run this script from the repo root (can't find .env.example)"
  fi
}

# ─── Provider definitions ─────────────────────────────────────────────────────
# PROVIDER_FIELDS format: fields separated by "|", each field: "key~Label~is_secret~default"
#   is_secret : 1 = hidden input  |  0 = visible input
#   default   : empty = required  |  non-empty = optional, shown in prompt, used on Enter
#
# PROVIDER_MODELS: "|"-separated model list shown at model-selection step.
#   "__deployment__" is a sentinel meaning the model was already collected as a credential.

PROVIDER_IDS=(   openai      anthropic    azure_ai     bedrock      gemini       mistral              nebius                ollama       )
PROVIDER_NAMES=( "OpenAI"    "Anthropic"  "Azure AI" "Amazon Bedrock" "Google Gemini" "Mistral AI"  "Nebius AI"           "Ollama (local)" )

PROVIDER_FIELDS=(
  "OPENAI_API_KEY~OpenAI API Key~1~"
  "ANTHROPIC_API_KEY~Anthropic API Key~1~"
  "AZURE_AI_API_KEY~Azure API Key~1~|AZURE_AI_API_BASE~Azure endpoint URL~0~|deployment_name~Deployment name~0~"
  "AWS_ACCESS_KEY_ID~Access Key ID~0~|AWS_SECRET_ACCESS_KEY~Secret Access Key~1~|AWS_REGION_NAME~Region (e.g. us-east-1)~0~"
  "GEMINI_API_KEY~Gemini API Key~1~"
  "MISTRAL_API_KEY~Mistral API Key~1~"
  "NEBIUS_API_KEY~Nebius API Key~1~"
  "OLLAMA_API_BASE~Ollama server URL~0~http://localhost:11434"
)

PROVIDER_MODELS=(
  "gpt-4o|gpt-4o-mini|gpt-4.1|gpt-4.1-mini|o3"
  "claude-sonnet-4-6|claude-opus-4-7|claude-haiku-4-5"
  "__deployment__"
  "anthropic.claude-3-5-sonnet-20241022-v2:0|anthropic.claude-3-7-sonnet-20250219-v1:0|amazon.nova-pro-v1:0|amazon.nova-lite-v1:0"
  "gemini-2.0-flash|gemini-2.5-pro|gemini-2.0-flash-lite"
  "mistral-large-latest|mistral-medium-latest|mistral-small-latest|codestral-latest"
  "meta-llama/Meta-Llama-3.1-70B-Instruct-fast|meta-llama/Meta-Llama-3.1-8B-Instruct-fast|Qwen/Qwen2.5-72B-Instruct-fast"
  "llama3.2|llama3.1|mistral|gemma3|phi4|qwen2.5|deepseek-r1"
)

# ─── Runtime state ────────────────────────────────────────────────────────────
SELECTED_INDICES=()   # indices into PROVIDER_* arrays for chosen providers
CRED_JSONS=()         # env var blocks (KEY=value lines), parallel to SELECTED_INDICES
SELECTED_MODELS=()    # chosen model IDs, parallel to SELECTED_INDICES
AZURE_DEPLOYMENT=""
CHAT_SEL_I=0          # index into SELECTED_INDICES for the chat model
TAVILY_KEY=""

# ─── Provider selection ───────────────────────────────────────────────────────
select_providers() {
  step "LLM Providers"
  info "Select one or more providers to configure (space-separated numbers):"
  printf "\n"
  local i
  for i in "${!PROVIDER_IDS[@]}"; do
    printf "  ${BOLD}%d)${RESET} %s\n" $((i + 1)) "${PROVIDER_NAMES[$i]}"
  done
  printf "\n"
  ask "Selection (e.g. 1 2):"
  read -r raw

  local token
  for token in $raw; do
    if [[ "$token" =~ ^[0-9]+$ ]] && [ "$token" -ge 1 ] && [ "$token" -le "${#PROVIDER_IDS[@]}" ]; then
      SELECTED_INDICES+=($((token - 1)))
    else
      warn "Ignoring invalid entry: $token"
    fi
  done

  [ "${#SELECTED_INDICES[@]}" -gt 0 ] || die "No valid providers selected."

  printf "\n"
  local idx
  for idx in "${SELECTED_INDICES[@]}"; do
    ok "${PROVIDER_NAMES[$idx]}"
  done
}

# ─── Credential collection ────────────────────────────────────────────────────
collect_credentials() {
  step "Credentials"
  dim "API keys will not be echoed to the terminal."

  local sel_i
  for sel_i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$sel_i]}"
    local pid="${PROVIDER_IDS[$idx]}"
    local pname="${PROVIDER_NAMES[$idx]}"
    local fields="${PROVIDER_FIELDS[$idx]}"

    printf "\n  ${BOLD}%s${RESET}\n" "$pname"

    local json="{"
    local json_first=1
    local field_defs field_def
    IFS='|' read -ra field_defs <<< "$fields"

    for field_def in "${field_defs[@]}"; do
      local key label is_secret default_val value prompt_hint
      IFS='~' read -r key label is_secret default_val <<< "$field_def"
      value=""
      prompt_hint=""
      [ -n "$default_val" ] && prompt_hint=" [${default_val}]"

      while true; do
        if [ "$is_secret" = "1" ]; then
          ask "${label}${prompt_hint}:"
          read -rs value; printf "\n"
        else
          ask "${label}${prompt_hint}:"
          read -r value
        fi

        if [ -z "$value" ] && [ -n "$default_val" ]; then
          value="$default_val"
          break
        elif [ -z "$value" ]; then
          warn "Cannot be empty. Try again."
        else
          break
        fi
      done

      # Azure deployment name is a model identifier, not a credential
      if [ "$pid" = "azure_ai" ] && [ "$key" = "deployment_name" ]; then
        AZURE_DEPLOYMENT="$value"
        continue
      fi

      value="${value//\\/\\\\}"; value="${value//\"/\\\"}"
      [ "$json_first" -eq 0 ] && json+=", "
      json+="\"${key}\": \"${value}\""
      json_first=0
    done

    json+="}"
    CRED_JSONS+=("$json")
  done
}

# ─── Model selection ──────────────────────────────────────────────────────────
select_models() {
  step "Model Selection"
  info "Choose a default model for each configured provider."
  dim "This model will be used for platform defaults and the chat assistant."

  local sel_i
  for sel_i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$sel_i]}"
    local pid="${PROVIDER_IDS[$idx]}"
    local pname="${PROVIDER_NAMES[$idx]}"
    local models_raw="${PROVIDER_MODELS[$idx]}"

    printf "\n  ${BOLD}%s${RESET}\n" "$pname"

    # Azure: deployment name was already collected as a credential
    if [ "$models_raw" = "__deployment__" ]; then
      SELECTED_MODELS+=("$AZURE_DEPLOYMENT")
      dim "  Using deployment: $AZURE_DEPLOYMENT"
      continue
    fi

    local models
    IFS='|' read -ra models <<< "$models_raw"
    local custom_idx=$(( ${#models[@]} + 1 ))

    local i
    for i in "${!models[@]}"; do
      printf "  ${BOLD}%d)${RESET} %s\n" $((i + 1)) "${models[$i]}"
    done
    printf "  ${BOLD}%d)${RESET} ${DIM}Custom (enter model ID)${RESET}\n" "$custom_idx"
    printf "\n"
    ask "Choice [1]:"
    read -r choice
    choice="${choice:-1}"

    local model_val=""
    if [ "$choice" = "$custom_idx" ]; then
      while [ -z "$model_val" ]; do
        ask "Model ID:"
        read -r model_val
        [ -z "$model_val" ] && warn "Cannot be empty."
      done
    elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#models[@]}" ]; then
      model_val="${models[$((choice - 1))]}"
    else
      warn "Invalid — using default"
      model_val="${models[0]}"
    fi

    SELECTED_MODELS+=("$model_val")
    ok "Model: $model_val"
  done
}

# ─── Chat model selection ─────────────────────────────────────────────────────
select_chat_model() {
  if [ "${#SELECTED_INDICES[@]}" -eq 1 ]; then
    CHAT_SEL_I=0
    printf "\n"
    local idx="${SELECTED_INDICES[0]}"
    ok "Chat model: ${PROVIDER_NAMES[$idx]} — ${SELECTED_MODELS[0]}"
    return
  fi

  step "Chat Model"
  info "Which model should drive the Synte chat assistant?"
  printf "\n"
  local i
  for i in "${!SELECTED_INDICES[@]}"; do
    local idx="${SELECTED_INDICES[$i]}"
    printf "  ${BOLD}%d)${RESET} %-20s ${DIM}%s${RESET}\n" \
      $((i + 1)) "${PROVIDER_NAMES[$idx]}" "${SELECTED_MODELS[$i]}"
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
  ok "Chat model: ${PROVIDER_NAMES[$idx]} — ${SELECTED_MODELS[$CHAT_SEL_I]}"
}

# ─── Tavily key ───────────────────────────────────────────────────────────────
ask_tavily() {
  step "Web Search (optional)"
  dim "Tavily enables web search inside agentlets. Get a free key at https://app.tavily.com"
  dim "Press Enter to skip."
  printf "\n"
  ask "Tavily API key:"
  read -rs TAVILY_KEY; printf "\n"
  if [ -n "$TAVILY_KEY" ]; then
    ok "Tavily key set"
  else
    warn "Skipping — web search unavailable until configured"
  fi
}

# ─── .env generation ──────────────────────────────────────────────────────────
generate_env() {
  step ".env"

  if [ -f .env ]; then
    ask ".env already exists. Overwrite? [Y/n]:"
    read -r confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
      warn "Skipping .env — using existing file"
      return
    fi
  fi

  local enc_key
  enc_key=$(od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n')

  {
    printf "# Generated by install.sh — do not commit\n\n"

    if [ -n "$TAVILY_KEY" ]; then
      printf "TAVILY_API_KEY=%s\n" "$TAVILY_KEY"
    else
      printf "TAVILY_API_KEY=\n"
    fi
    printf "\n"

    local sel_i
    for sel_i in "${!SELECTED_INDICES[@]}"; do
      local idx="${SELECTED_INDICES[$sel_i]}"
      local pid="${PROVIDER_IDS[$idx]}"
      local pname="${PROVIDER_NAMES[$idx]}"
      local var_name
      var_name="PLATFORM_SECRET_$(printf '%s' "$pid" | tr '[:lower:]' '[:upper:]')"
      printf "# %s\n" "$pname"
      printf "%s=%s\n\n" "$var_name" "${CRED_JSONS[$sel_i]}"
    done

    printf "# Encryption key — never share or commit\n"
    printf "SECRET_ENCRYPTION_KEY=%s\n\n" "$enc_key"

    printf "# Keycloak — safe defaults for local dev\n"
    printf "KEYCLOAK_DEFAULT_USER=synteles\n"
    printf "KEYCLOAK_DEFAULT_PASSWORD=synteles\n"
    printf "KEYCLOAK_ADMIN_USER=admin\n"
    printf "KEYCLOAK_ADMIN_PASSWORD=admin\n"
    printf "OIDC_CLIENT_SECRET=synteles-dev-secret\n"
    printf "KEYCLOAK_PROVISIONER_CLIENT_SECRET=provisioner-dev-secret\n"
    printf "\n"
    printf "# Agentlet runtime image. 'edge' tracks the latest development build.\n"
    printf "# Pin to a release tag for stable/production deployments, e.g. synteles/agentlet:1.2.3\n"
    printf "AGENTLET_IMAGE=synteles/agentlet:edge\n"
  } > .env

  ok "Generated .env"
}

# ─── platform.toml generation ─────────────────────────────────────────────────
generate_platform_toml() {
  step "config/platform.toml"

  if [ -f config/platform.toml ]; then
    ask "config/platform.toml already exists. Overwrite? [Y/n]:"
    read -r confirm
    if [[ "$confirm" =~ ^[Nn]$ ]]; then
      warn "Skipping platform.toml — using existing file"
      return
    fi
  fi

  local chat_prov_idx="${SELECTED_INDICES[$CHAT_SEL_I]}"
  local chat_pid="${PROVIDER_IDS[$chat_prov_idx]}"
  local chat_model="${SELECTED_MODELS[$CHAT_SEL_I]}"
  local chat_litellm_id="${chat_pid}/${chat_model}"

  {
    printf "# Generated by install.sh\n\n"
    printf "# ── Chat engine ─────────────────────────────────────────────────────────────\n"
    printf "[chat]\n"
    printf "model_id    = \"%s\"\n" "$chat_litellm_id"
    printf "secret_name = \"%s\"\n" "$chat_pid"
    printf "\n"
    printf "# ── Platform default models ──────────────────────────────────────────────────\n"

    local sel_i
    for sel_i in "${!SELECTED_INDICES[@]}"; do
      local idx="${SELECTED_INDICES[$sel_i]}"
      local pid="${PROVIDER_IDS[$idx]}"
      local model="${SELECTED_MODELS[$sel_i]}"

      local model_basename="${model##*/}"
      local safe_id
      safe_id=$(printf '%s' "$pid" | tr -d '_')

      printf "\n[[model]]\n"
      printf "id                  = \"platform_%s\"\n" "$safe_id"
      printf "label               = \"%s\"\n" "$model_basename"
      printf "provider            = \"%s\"\n" "$pid"
      printf "model_id            = \"%s\"\n" "$model"
      printf "secret_name         = \"%s\"\n" "$pid"
      printf "default_temperature = 1.0\n"
    done
  } > config/platform.toml

  ok "Generated config/platform.toml"
}


# ─── Build durable-agentlet image ────────────────────────────────────────────
build_durable_agentlet() {
  step "Durable agentlet image"
  info "Building synteles/durable-agentlet:edge …"
  if docker compose build durable-agentlet; then
    ok "durable-agentlet image built"
  else
    warn "durable-agentlet build failed — durable executions will not work until it is rebuilt"
  fi
}

# ─── Done ─────────────────────────────────────────────────────────────────────
print_done() {
  printf "\n"
  printf "${BOLD}${GREEN}  ┌────────────────────────────────────────┐${RESET}\n"
  printf "${BOLD}${GREEN}  │           Setup complete!              │${RESET}\n"
  printf "${BOLD}${GREEN}  └────────────────────────────────────────┘${RESET}\n"
  printf "\n"
  printf "  Start the platform:\n\n"
  printf "    ${BOLD}docker compose up -d${RESET}\n\n"
  printf "  Files written:\n"
  printf "    ${DIM}.env${RESET}                  provider credentials & encryption key\n"
  printf "    ${DIM}config/platform.toml${RESET}  model wiring\n"
  printf "\n"
  printf "  ${YELLOW}Never commit .env — it contains secrets.${RESET}\n"
  printf "\n"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
  print_banner
  check_prereqs
  check_repo_root
  select_providers
  collect_credentials
  select_models
  select_chat_model
  ask_tavily
  generate_env
  generate_platform_toml
  build_durable_agentlet
  print_done
}

main "$@"
