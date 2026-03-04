#!/usr/bin/env bash
set -euo pipefail

KNOWLEDGE_GRPC_TARGET=${KNOWLEDGE_GRPC_TARGET:-127.0.0.1:50051}
INIT_REQUEST_PATH=${INIT_REQUEST_PATH:-apps/knowledge-interface/mock-data/knowledge/initialize-user-graph.request.json}
DELTA_TEMPLATE_PATH=${DELTA_TEMPLATE_PATH:-apps/knowledge-interface/mock-data/knowledge/upsert-graph-delta.request.template.json}

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
  echo "hint: start dependencies (Memgraph/Qdrant) and run ./scripts/agent/run-knowledge-interface-native.sh (or ./scripts/local/run-knowledge-interface.sh in docker-compose workflows)" >&2
  exit 1
fi

echo "Getting/initializing user graph for assistant-backend test user via $KNOWLEDGE_GRPC_TARGET..."
init_reply=$(grpcurl -plaintext -d @ "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/GetUserInitGraph < "$INIT_REQUEST_PATH")
person_entity_id=$(echo "$init_reply" | jq -r '.personEntityId // empty')
assistant_entity_id=$(echo "$init_reply" | jq -r '.assistantEntityId // empty')

if [[ -z "$person_entity_id" || -z "$assistant_entity_id" ]]; then
  echo "error: GetUserInitGraph reply did not include expected entity ids" >&2
  echo "$init_reply" >&2
  exit 1
fi

tmp_delta=$(mktemp)
cleanup() {
  rm -f "$tmp_delta"
}
trap cleanup EXIT

jq --arg person_entity_id "$person_entity_id" --arg assistant_entity_id "$assistant_entity_id" '
  .edges |= map(
    .from_id =
      if .from_id == "__PERSON_ENTITY_ID__" then $person_entity_id
      elif .from_id == "__ASSISTANT_ENTITY_ID__" then $assistant_entity_id
      else .from_id end
    | .to_id =
      if .to_id == "__PERSON_ENTITY_ID__" then $person_entity_id
      elif .to_id == "__ASSISTANT_ENTITY_ID__" then $assistant_entity_id
      else .to_id end
  )
' "$DELTA_TEMPLATE_PATH" > "$tmp_delta"

echo "Upserting graph delta..."
upsert_reply=$(grpcurl -plaintext -d @ "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta < "$tmp_delta")

echo "GetUserInitGraph reply:"
echo "$init_reply" | jq
echo
echo "UpsertGraphDelta reply:"
echo "$upsert_reply" | jq
