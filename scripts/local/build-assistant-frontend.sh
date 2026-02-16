#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"
app_dir="${repo_root}/apps/assistant-frontend"
lockfile="${app_dir}/package-lock.json"
stamp_file="${app_dir}/node_modules/.package-lock.sha256"

cd "${app_dir}"

need_install=0
if [[ ! -d node_modules ]]; then
  need_install=1
elif [[ ! -f "${stamp_file}" ]]; then
  need_install=1
elif [[ -f "${lockfile}" ]]; then
  current_hash="$(sha256sum "${lockfile}" | awk '{print $1}')"
  recorded_hash="$(cat "${stamp_file}")"
  if [[ "${current_hash}" != "${recorded_hash}" ]]; then
    need_install=1
  fi
fi

if [[ "${need_install}" -eq 1 ]]; then
  npm ci
  mkdir -p "$(dirname "${stamp_file}")"
  if [[ -f "${lockfile}" ]]; then
    sha256sum "${lockfile}" | awk '{print $1}' > "${stamp_file}"
  fi
fi

npm run build
