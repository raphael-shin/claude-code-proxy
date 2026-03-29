from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def test_deploy_script_runs_cdk_and_installs_api_key_helper(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "deploy_claude_code_proxy.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cdk_log = tmp_path / "cdk.log"
    home_dir = tmp_path / "home"
    settings_path = home_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"model": "opus", "env": {"EXISTING": "1"}}))

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "sts" && "$2" == "get-caller-identity" ]]; then
  if [[ "${AWS_STS_SHOULD_FAIL:-0}" == "1" ]]; then
    exit 255
  fi
  echo "123456789012"
  exit 0
fi

if [[ "$1" == "cloudformation" && "$2" == "describe-stacks" ]]; then
  query=""
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --query)
        query="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
  if [[ "$query" == *"RuntimeEndpointUrl"* ]]; then
    echo "https://proxy.example.com"
    exit 0
  fi
  if [[ "$query" == *"TokenServiceEndpointUrl"* ]]; then
    echo "https://token.example.com/token-service/get-or-create-key"
    exit 0
  fi
fi

if [[ "$1" == "ecr" && "$2" == "describe-images" ]]; then
  echo '{"imageDetails":[{"imageTags":["2026-03-29"]}]}'
  exit 0
fi

echo "unexpected aws command: $*" >&2
exit 1
"""
    )
    aws_stub.chmod(0o755)

    cdk_stub = fake_bin / "cdk"
    cdk_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$PWD|$*" >> "{cdk_log}"
"""
    )
    cdk_stub.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        input=(
            "my-sandbox\n"
            "ap-northeast-2\n"
            "personal-dev\n"
            "arn:aws:acm:ap-northeast-2:123456789012:certificate/real-cert\n"
            "arn:aws:wafv2:ap-northeast-2:123456789012:regional/webacl/real-waf/12345678-1234-1234-1234-123456789012\n"
            "team/proxy-runtime\n"
            "2026-03-29\n"
            "y\n"
            "\n"
            "\n"
            "y\n"
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr

    helper_path = home_dir / ".claude" / "claude-code-proxy" / "api_key_helper.sh"
    assert helper_path.exists()
    helper_contents = helper_path.read_text()
    assert "aws configure export-credentials" in helper_contents
    assert "curl -sS -X POST" in helper_contents

    settings_payload = json.loads(settings_path.read_text())
    assert settings_payload["model"] == "opus"
    assert settings_payload["apiKeyHelper"] == str(helper_path)
    assert settings_payload["env"]["EXISTING"] == "1"
    assert settings_payload["env"]["ANTHROPIC_BASE_URL"] == "https://proxy.example.com"
    assert (
        settings_payload["env"]["CLAUDE_CODE_PROXY_TOKEN_SERVICE_URL"]
        == "https://token.example.com/token-service/get-or-create-key"
    )
    assert settings_payload["env"]["AWS_PROFILE"] == "my-sandbox"
    assert settings_payload["env"]["AWS_REGION"] == "ap-northeast-2"

    cdk_commands = cdk_log.read_text().splitlines()
    assert any("synth ClaudeCodeProxyStack --profile my-sandbox -c envName=personal-dev" in line for line in cdk_commands)
    assert any("deploy ClaudeCodeProxyStack --profile my-sandbox --require-approval never -c envName=personal-dev" in line for line in cdk_commands)


def test_deploy_script_exits_with_login_instruction_when_credentials_are_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "deploy_claude_code_proxy.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cdk_log = tmp_path / "cdk.log"
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "sts" && "$2" == "get-caller-identity" ]]; then
  exit 255
fi
exit 1
"""
    )
    aws_stub.chmod(0o755)

    cdk_stub = fake_bin / "cdk"
    cdk_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$PWD|$*" >> "{cdk_log}"
"""
    )
    cdk_stub.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        input="my-sandbox\n",
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "aws sso login --profile my-sandbox" in completed.stderr
    assert not cdk_log.exists()


def test_deploy_script_exits_before_cdk_when_runtime_image_is_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "deploy_claude_code_proxy.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cdk_log = tmp_path / "cdk.log"
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    aws_stub = fake_bin / "aws"
    aws_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "sts" && "$2" == "get-caller-identity" ]]; then
  echo "123456789012"
  exit 0
fi
if [[ "$1" == "ecr" && "$2" == "describe-images" ]]; then
  exit 254
fi
exit 1
"""
    )
    aws_stub.chmod(0o755)

    cdk_stub = fake_bin / "cdk"
    cdk_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$PWD|$*" >> "{cdk_log}"
"""
    )
    cdk_stub.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        input=(
            "my-sandbox\n"
            "ap-northeast-2\n"
            "personal-dev\n"
            "arn:aws:acm:ap-northeast-2:123456789012:certificate/real-cert\n"
            "arn:aws:wafv2:ap-northeast-2:123456789012:regional/webacl/real-waf/12345678-1234-1234-1234-123456789012\n"
            "team/proxy-runtime\n"
            "missing-tag\n"
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "private ECR image" in completed.stderr
    assert not cdk_log.exists()
