#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-exobrain-dev}
K3S_IMAGE=${K3S_IMAGE:-rancher/k3s:v1.29.4-k3s1}
AGENTS=${AGENTS:-2}

k3d cluster create "$CLUSTER_NAME" \
  --agents "$AGENTS" \
  --servers 1 \
  --k3s-arg "--disable=traefik@server:0" \
  --image "$K3S_IMAGE" \
  --port "8080:80@loadbalancer" \
  --port "8443:443@loadbalancer"
