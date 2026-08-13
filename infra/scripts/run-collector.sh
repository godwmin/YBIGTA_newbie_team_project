#!/usr/bin/env bash
set -euo pipefail

app_dir="${YBIGTA_APP_DIR:-$HOME/ybigta}"
image_ref="$(cat "$app_dir/collector-image")"

docker pull "$image_ref"
docker run --rm \
  --env-file "$app_dir/collector.env" \
  "$image_ref"
