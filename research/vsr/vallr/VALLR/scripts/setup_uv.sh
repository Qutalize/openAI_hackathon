#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "${script_dir}/.." && pwd)"
env_root="${WORKON_HOME:-${HOME}/.virtualenvs}"
env_dir="${VALLR_ENV_DIR:-${env_root}/vallr-vsr}"

command -v uv >/dev/null

uv venv --python 3.10 "${env_dir}"
uv pip sync --python "${env_dir}/bin/python" "${repo_dir}/requirements-uv.lock"

printf 'VALLR environment: %s\n' "${env_dir}"
printf 'Activate with: source %s/bin/activate\n' "${env_dir}"

