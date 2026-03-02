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

make_uuid() {
  cat /proc/sys/kernel/random/uuid
}

task_id=$(make_uuid)
block1_id=$(make_uuid)
block2_id=$(make_uuid)
block3_id=$(make_uuid)
block4_id=$(make_uuid)
block5_id=$(make_uuid)
block6_id=$(make_uuid)
block7_id=$(make_uuid)

tmp_delta=$(mktemp)
cleanup() {
  rm -f "$tmp_delta"
}
trap cleanup EXIT

jq   --arg task_id "$task_id"   --arg block1_id "$block1_id"   --arg block2_id "$block2_id"   --arg block3_id "$block3_id"   --arg block4_id "$block4_id"   --arg block5_id "$block5_id"   --arg block6_id "$block6_id"   --arg block7_id "$block7_id" '
  def remap_id($id):
    if $id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1" then $task_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1" then $block1_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2" then $block2_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3" then $block3_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb4" then $block4_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb5" then $block5_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb6" then $block6_id
    elif $id == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb7" then $block7_id
    else $id end;

  .entities |= map(
    .id = remap_id(.id)
    | if .universe_id == "__UNIVERSE_ID__" then del(.universe_id) else . end
  )
  | .blocks |= map(.id = remap_id(.id))
  | .edges |= map(.from_id = remap_id(.from_id) | .to_id = remap_id(.to_id))
' "$DELTA_TEMPLATE_PATH" > "$tmp_delta"

echo "Upserting graph delta..."
upsert_reply=$(grpcurl -plaintext -d @ "$KNOWLEDGE_GRPC_TARGET" exobrain.knowledge.v1.KnowledgeInterface/UpsertGraphDelta < "$tmp_delta")

echo "GetUserInitGraph reply:"
echo "$init_reply" | jq
echo
echo "UpsertGraphDelta reply:"
echo "$upsert_reply" | jq
