#!/usr/bin/env bash
set -euo pipefail

MIN_CACHE_TTL_SECONDS=300
MAX_CACHE_TTL_SECONDS=900

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    exit 1
  fi
}

normalize_cache_ttl() {
  local ttl_value="${CLAUDE_CODE_PROXY_CACHE_TTL_SECONDS:-$MIN_CACHE_TTL_SECONDS}"

  if ! [[ "$ttl_value" =~ ^[0-9]+$ ]]; then
    ttl_value="$MIN_CACHE_TTL_SECONDS"
  fi
  if (( ttl_value < MIN_CACHE_TTL_SECONDS )); then
    ttl_value="$MIN_CACHE_TTL_SECONDS"
  fi
  if (( ttl_value > MAX_CACHE_TTL_SECONDS )); then
    ttl_value="$MAX_CACHE_TTL_SECONDS"
  fi

  printf '%s\n' "$ttl_value"
}

load_cached_key() {
  local cache_path="$1"
  local now_epoch="$2"
  local virtual_key=""
  local expires_at_epoch=""

  if [[ ! -f "$cache_path" ]]; then
    return 1
  fi

  virtual_key="$(jq -r '.virtual_key // empty' "$cache_path" 2>/dev/null || true)"
  expires_at_epoch="$(jq -r '.expires_at_epoch // empty' "$cache_path" 2>/dev/null || true)"

  if [[ -z "$virtual_key" || -z "$expires_at_epoch" ]]; then
    return 1
  fi
  if [[ "$virtual_key" != vk_* ]]; then
    return 1
  fi
  if ! [[ "$expires_at_epoch" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  if (( expires_at_epoch <= now_epoch )); then
    return 1
  fi

  printf '%s\n' "$virtual_key"
}

store_cached_key() {
  local cache_path="$1"
  local virtual_key="$2"
  local now_epoch="$3"
  local ttl_seconds="$4"
  local expires_at_epoch=$((now_epoch + ttl_seconds))
  local cache_dir=""
  local temp_file=""

  cache_dir="$(dirname "$cache_path")"
  mkdir -p "$cache_dir"
  temp_file="$(mktemp "${cache_dir}/cache.XXXXXX")"
  jq -n \
    --arg virtual_key "$virtual_key" \
    --argjson expires_at_epoch "$expires_at_epoch" \
    '{virtual_key: $virtual_key, expires_at_epoch: $expires_at_epoch}' >"$temp_file"
  mv "$temp_file" "$cache_path"
}

load_aws_credentials() {
  local export_output=""
  local export_command=(aws configure export-credentials --format env)

  if [[ -n "${AWS_PROFILE:-}" ]]; then
    export_command+=(--profile "$AWS_PROFILE")
  fi

  if ! export_output="$("${export_command[@]}" 2>/dev/null)"; then
    if [[ -n "${AWS_PROFILE:-}" ]]; then
      echo "ERROR: aws sso login --profile ${AWS_PROFILE} 를 실행하세요." >&2
    else
      echo "ERROR: aws sso login 또는 유효한 AWS 자격 증명을 준비하세요." >&2
    fi
    exit 1
  fi

  eval "$export_output"
}

fetch_virtual_key() {
  local token_service_url="$1"
  local aws_region="$2"
  local timeout_seconds="$3"
  local response=""
  local token=""

  if ! response="$(curl -sS -X POST "$token_service_url" \
    --max-time "$timeout_seconds" \
    --aws-sigv4 "aws:amz:${aws_region}:execute-api" \
    --user "${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}" \
    -H "x-amz-security-token: ${AWS_SESSION_TOKEN:-}" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null)"; then
    echo "ERROR: Failed to connect to Token Service." >&2
    exit 1
  fi

  token="$(printf '%s' "$response" | jq -r '.virtual_key // .token // empty' 2>/dev/null || true)"
  if [[ -z "$token" || "$token" != vk_* ]]; then
    echo "ERROR: Token Service에서 유효한 virtual key를 받지 못했습니다: $response" >&2
    exit 1
  fi

  printf '%s\n' "$token"
}

require_command aws
require_command curl
require_command jq

TOKEN_SERVICE_URL="${CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL:-${TOKEN_SERVICE_URL:-}}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
CACHE_PATH="${CLAUDE_CODE_PROXY_CACHE_PATH:-$HOME/.claude-code-proxy/cache.json}"
CACHE_TTL_SECONDS="$(normalize_cache_ttl)"
REQUEST_TIMEOUT_SECONDS="${CLAUDE_CODE_PROXY_REQUEST_TIMEOUT_SECONDS:-2}"
NOW_EPOCH="$(date -u +%s)"

if [[ -z "$TOKEN_SERVICE_URL" || -z "$AWS_REGION" ]]; then
  echo "ERROR: CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL and AWS_REGION must be configured." >&2
  exit 1
fi

if CACHED_KEY="$(load_cached_key "$CACHE_PATH" "$NOW_EPOCH")"; then
  printf '%s\n' "$CACHED_KEY"
  exit 0
fi

load_aws_credentials
VIRTUAL_KEY="$(fetch_virtual_key "$TOKEN_SERVICE_URL" "$AWS_REGION" "$REQUEST_TIMEOUT_SECONDS")"
store_cached_key "$CACHE_PATH" "$VIRTUAL_KEY" "$NOW_EPOCH" "$CACHE_TTL_SECONDS"
printf '%s\n' "$VIRTUAL_KEY"
