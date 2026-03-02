#!/usr/bin/env bash
set -euo pipefail

KNOWLEDGE_GRPC_TARGET=${KNOWLEDGE_GRPC_TARGET:-127.0.0.1:50051}
INIT_REQUEST_PATH=${INIT_REQUEST_PATH:-apps/assistant-backend/mock-data/knowledge/initialize-user-graph.request.json}
DELTA_TEMPLATE_PATH=${DELTA_TEMPLATE_PATH:-apps/assistant-backend/mock-data/knowledge/upsert-graph-delta.request.template.json}

if ! command -v grpcurl >/dev/null 2>&1; then
  echo "error: grpcurl is required but not installed" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required but not installed" >&2
  exit 1
fi

if [[ ! -f "$INIT_REQUEST_PATH" ]]; then
  echo "error: initialize request json not found at $INIT_REQUEST_PATH" >&2
  exit 1
fi

if [[ ! -f "$DELTA_TEMPLATE_PATH" ]]; then
  echo "error: upsert delta template json not found at $DELTA_TEMPLATE_PATH" >&2
  exit 1
fi

if ! grpcurl -plaintext -d '{}' "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/Health >/dev/null 2>&1; then
  echo "error: unable to reach knowledge-interface gRPC health endpoint at $KNOWLEDGE_GRPC_TARGET" >&2
  echo "hint: start dependencies (Memgraph/Qdrant) and run ./scripts/local/run-knowledge-interface.sh" >&2
  exit 1
fi

echo "Initializing graph for assistant-backend test user via $KNOWLEDGE_GRPC_TARGET..."
init_reply=$(grpcurl -plaintext -d @ "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/InitializeUserGraph < "$INIT_REQUEST_PATH")
universe_id=$(echo "$init_reply" | jq -r '.universeId // empty')

if [[ -z "$universe_id" ]]; then
  echo "error: InitializeUserGraph reply did not include universeId" >&2
  echo "$init_reply" >&2
  exit 1
fi

tmp_delta=$(mktemp)
cleanup() {
  rm -f "$tmp_delta"
}
trap cleanup EXIT

jq --arg universe_id "$universe_id" '
  .entities |= map(
    if .universe_id == "__UNIVERSE_ID__" then
      .universe_id = $universe_id
    else
      .
    end
  )
' "$DELTA_TEMPLATE_PATH" > "$tmp_delta"

echo "Upserting graph delta with universe_id=$universe_id..."
upsert_reply=$(grpcurl -plaintext -d @ "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta < "$tmp_delta")

echo "InitializeUserGraph reply:"
echo "$init_reply" | jq
echo
echo "UpsertGraphDelta reply:"
echo "$upsert_reply" | jq
