#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_NAME="ClaudeCodeProxyStack"
DEFAULT_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-northeast-2}}"
DEFAULT_HELPER_DIR="${HOME}/.claude/claude-code-proxy"
DEFAULT_SETTINGS_PATH="${HOME}/.claude/settings.json"
SOURCE_HELPER_PATH="${REPO_ROOT}/scripts/api_key_helper.sh"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "required command not found: $1" >&2
    exit 1
  fi
}

prompt_with_default() {
  local label="$1"
  local default_value="${2:-}"
  local response=""

  while true; do
    if [[ -n "$default_value" ]]; then
      read -r -p "${label} [${default_value}]: " response
      if [[ -z "$response" ]]; then
        printf '%s\n' "$default_value"
        return 0
      fi
    else
      read -r -p "${label}: " response
    fi

    if [[ -n "$response" ]]; then
      printf '%s\n' "$response"
      return 0
    fi

    echo "${label} is required."
  done
}

confirm_with_default_yes() {
  local prompt="$1"
  local response=""
  local normalized=""

  read -r -p "${prompt} [Y/n]: " response
  normalized="$(printf '%s' "$response" | tr '[:upper:]' '[:lower:]')"
  [[ -z "$normalized" || "$normalized" == "y" || "$normalized" == "yes" ]]
}

confirm_with_default_no() {
  local prompt="$1"
  local response=""
  local normalized=""

  read -r -p "${prompt} [y/N]: " response
  normalized="$(printf '%s' "$response" | tr '[:upper:]' '[:lower:]')"
  [[ "$normalized" == "y" || "$normalized" == "yes" ]]
}

get_stack_output() {
  local output_key="$1"

  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue | [0]" \
    --output text
}

verify_runtime_image_exists() {
  local repository_name="$1"
  local image_tag="$2"

  if ! aws ecr describe-images \
    --repository-name "$repository_name" \
    --image-ids "imageTag=${image_tag}" \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" >/dev/null 2>&1; then
    echo "Runtime image '${repository_name}:${image_tag}' was not found in private ECR." >&2
    echo "Push the runtime image to ECR and retry. Isolated subnets without NAT require a private ECR image." >&2
    exit 1
  fi
}

install_api_key_helper() {
  local helper_dir="$1"
  local settings_path="$2"
  local runtime_url="$3"
  local token_service_url="$4"
  local helper_path="${helper_dir}/api_key_helper.sh"
  local backup_path=""
  local temp_file=""

  mkdir -p "$helper_dir"
  install -m 755 "$SOURCE_HELPER_PATH" "$helper_path"

  mkdir -p "$(dirname "$settings_path")"
  if [[ -f "$settings_path" ]]; then
    backup_path="${settings_path}.bak.$(date +%s)"
    cp "$settings_path" "$backup_path"
  else
    printf '{}\n' >"$settings_path"
  fi

  temp_file="$(mktemp "$(dirname "$settings_path")/settings.XXXXXX")"
  jq \
    --arg helper_path "$helper_path" \
    --arg runtime_url "${runtime_url%/}" \
    --arg token_service_url "$token_service_url" \
    --arg aws_profile "$AWS_PROFILE" \
    --arg aws_region "$AWS_REGION" \
    '
      .apiKeyHelper = $helper_path
      | .env = (
          (.env // {})
          + {
              "ANTHROPIC_BASE_URL": $runtime_url,
              "CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL": $token_service_url,
              "AWS_PROFILE": $aws_profile,
              "AWS_REGION": $aws_region,
              "AWS_DEFAULT_REGION": $aws_region
            }
        )
    ' "$settings_path" >"$temp_file"
  mv "$temp_file" "$settings_path"
  chmod +x "$helper_path"
}

require_command aws
require_command cdk
require_command curl
require_command jq

if [[ -d "$REPO_ROOT/.venv" && "${VIRTUAL_ENV:-}" == "" ]]; then
  echo "Tip: activate the repo virtualenv with 'source .venv/bin/activate' before deploying."
fi

AWS_PROFILE="$(prompt_with_default "AWS profile" "${AWS_PROFILE:-}")"
if ! AWS_ACCOUNT_ID="$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query 'Account' --output text 2>/dev/null)"; then
  echo "AWS temporary credentials are not available for profile '$AWS_PROFILE'." >&2
  echo "Run 'aws sso login --profile $AWS_PROFILE' and retry." >&2
  exit 1
fi

AWS_REGION="$(prompt_with_default "AWS region" "$DEFAULT_REGION")"
ENVIRONMENT_NAME="$(prompt_with_default "Logical environment name" "$AWS_PROFILE")"
CLAUDE_CODE_PROXY_CERTIFICATE_ARN="$(prompt_with_default "ACM certificate ARN" "${CLAUDE_CODE_PROXY_CERTIFICATE_ARN:-}")"
CLAUDE_CODE_PROXY_WAF_ARN="$(prompt_with_default "WAF ARN" "${CLAUDE_CODE_PROXY_WAF_ARN:-}")"
CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME="$(
  prompt_with_default \
    "Runtime ECR repository name" \
    "${CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME:-claude-code-proxy/runtime}"
)"
CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG="$(
  prompt_with_default \
    "Runtime ECR image tag" \
    "${CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG:-latest}"
)"
verify_runtime_image_exists \
  "$CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME" \
  "$CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG"

INSTALL_CLAUDE_HELPER="false"
CLAUDE_HELPER_DIR="$DEFAULT_HELPER_DIR"
CLAUDE_SETTINGS_PATH="$DEFAULT_SETTINGS_PATH"
if confirm_with_default_yes "Install apiKeyHelper into Claude Code settings after deploy?"; then
  INSTALL_CLAUDE_HELPER="true"
  CLAUDE_HELPER_DIR="$(prompt_with_default "Claude helper install directory" "$DEFAULT_HELPER_DIR")"
  CLAUDE_SETTINGS_PATH="$(prompt_with_default "Claude settings path" "$DEFAULT_SETTINGS_PATH")"
fi

echo
echo "Deployment summary"
echo "  Stack: $STACK_NAME"
echo "  AWS profile: $AWS_PROFILE"
echo "  AWS account: $AWS_ACCOUNT_ID"
echo "  AWS region: $AWS_REGION"
echo "  Environment name: $ENVIRONMENT_NAME"
echo "  Certificate ARN: $CLAUDE_CODE_PROXY_CERTIFICATE_ARN"
echo "  WAF ARN: $CLAUDE_CODE_PROXY_WAF_ARN"
echo "  Runtime image: $CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME:$CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG"
if [[ "$INSTALL_CLAUDE_HELPER" == "true" ]]; then
  echo "  Claude helper dir: $CLAUDE_HELPER_DIR"
  echo "  Claude settings path: $CLAUDE_SETTINGS_PATH"
fi
echo

if ! confirm_with_default_no "Continue with cdk synth and cdk deploy?"; then
  echo "deployment cancelled" >&2
  exit 1
fi

export AWS_PROFILE
export AWS_REGION
export AWS_DEFAULT_REGION="$AWS_REGION"
export CLAUDE_CODE_PROXY_CERTIFICATE_ARN
export CLAUDE_CODE_PROXY_WAF_ARN
export CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME
export CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG

echo "Running cdk synth..."
(
  cd "$REPO_ROOT"
  cdk synth "$STACK_NAME" --profile "$AWS_PROFILE" -c "envName=${ENVIRONMENT_NAME}"
)

echo "Running cdk deploy..."
(
  cd "$REPO_ROOT"
  cdk deploy "$STACK_NAME" --profile "$AWS_PROFILE" --require-approval never -c "envName=${ENVIRONMENT_NAME}"
)

if [[ "$INSTALL_CLAUDE_HELPER" == "true" ]]; then
  echo "Resolving deployed endpoint outputs..."
  RUNTIME_ENDPOINT_URL="$(get_stack_output "RuntimeEndpointUrl")"
  TOKEN_SERVICE_ENDPOINT_URL="$(get_stack_output "TokenServiceEndpointUrl")"

  if [[ -z "$RUNTIME_ENDPOINT_URL" || "$RUNTIME_ENDPOINT_URL" == "None" || "$RUNTIME_ENDPOINT_URL" == "null" ]]; then
    echo "RuntimeEndpointUrl stack output is missing." >&2
    exit 1
  fi
  if [[ -z "$TOKEN_SERVICE_ENDPOINT_URL" || "$TOKEN_SERVICE_ENDPOINT_URL" == "None" || "$TOKEN_SERVICE_ENDPOINT_URL" == "null" ]]; then
    echo "TokenServiceEndpointUrl stack output is missing." >&2
    exit 1
  fi

  echo "Installing apiKeyHelper into Claude Code..."
  install_api_key_helper "$CLAUDE_HELPER_DIR" "$CLAUDE_SETTINGS_PATH" "$RUNTIME_ENDPOINT_URL" "$TOKEN_SERVICE_ENDPOINT_URL"
  echo "Installed apiKeyHelper at ${CLAUDE_HELPER_DIR}/api_key_helper.sh"
  echo "Updated Claude settings at ${CLAUDE_SETTINGS_PATH}"
fi

echo "Deployment finished successfully."
