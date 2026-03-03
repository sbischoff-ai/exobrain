use serde_json::{json, Value};

pub const UPSERT_GRAPH_DELTA_SCHEMA_ID: &str =
    "https://exobrain.dev/schemas/knowledge/upsert-graph-delta-request.json";

pub fn upsert_graph_delta_json_schema_value() -> Value {
    json!({
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": UPSERT_GRAPH_DELTA_SCHEMA_ID,
      "title": "UpsertGraphDeltaRequest",
      "type": "object",
      "additionalProperties": false,
      "required": ["universes", "entities", "blocks", "edges"],
      "properties": {
        "universes": {
          "type": "array",
          "items": universe_node_schema()
        },
        "entities": {
          "type": "array",
          "items": entity_node_schema()
        },
        "blocks": {
          "type": "array",
          "items": block_node_schema()
        },
        "edges": {
          "type": "array",
          "items": graph_edge_schema()
        }
      }
    })
}

pub fn upsert_graph_delta_json_schema_string() -> String {
    try_upsert_graph_delta_json_schema_string()
        .expect("upsert graph delta json schema should always serialize")
}

pub fn try_upsert_graph_delta_json_schema_string() -> Result<String, serde_json::Error> {
    serde_json::to_string_pretty(&upsert_graph_delta_json_schema_value())
}

fn universe_node_schema() -> Value {
    json!({
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "name", "user_id", "visibility"],
      "properties": {
        "id": uuid_string_schema(),
        "name": { "type": "string" },
        "user_id": uuid_string_schema(),
        "visibility": visibility_schema()
      }
    })
}

fn entity_node_schema() -> Value {
    json!({
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "type_id", "properties", "user_id", "visibility"],
      "properties": {
        "id": uuid_string_schema(),
        "type_id": { "type": "string" },
        "properties": property_values_array_schema(),
        "user_id": uuid_string_schema(),
        "visibility": visibility_schema(),
        "universe_id": uuid_string_schema()
      }
    })
}

fn block_node_schema() -> Value {
    json!({
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "type_id", "properties", "user_id", "visibility"],
      "properties": {
        "id": uuid_string_schema(),
        "type_id": { "type": "string" },
        "properties": property_values_array_schema(),
        "user_id": uuid_string_schema(),
        "visibility": visibility_schema()
      }
    })
}

fn graph_edge_schema() -> Value {
    json!({
      "type": "object",
      "additionalProperties": false,
      "required": ["from_id", "to_id", "edge_type", "properties", "user_id", "visibility"],
      "properties": {
        "from_id": uuid_string_schema(),
        "to_id": uuid_string_schema(),
        "edge_type": { "type": "string" },
        "properties": property_values_array_schema(),
        "user_id": uuid_string_schema(),
        "visibility": visibility_schema()
      }
    })
}

fn property_values_array_schema() -> Value {
    json!({
      "type": "array",
      "items": property_value_schema()
    })
}

fn property_value_schema() -> Value {
    json!({
      "type": "object",
      "additionalProperties": false,
      "required": ["key"],
      "properties": {
        "key": { "type": "string" },
        "string_value": { "type": "string" },
        "float_value": { "type": "number" },
        "int_value": { "type": "integer" },
        "bool_value": { "type": "boolean" },
        "datetime_value": { "type": "string", "format": "date-time" },
        "json_value": {}
      },
      "oneOf": [
        { "required": ["string_value"] },
        { "required": ["float_value"] },
        { "required": ["int_value"] },
        { "required": ["bool_value"] },
        { "required": ["datetime_value"] },
        { "required": ["json_value"] }
      ],
      "minProperties": 2,
      "maxProperties": 2
    })
}

fn visibility_schema() -> Value {
    json!({
      "type": "string",
      "enum": ["PRIVATE", "SHARED"]
    })
}

fn uuid_string_schema() -> Value {
    json!({
      "type": "string",
      "format": "uuid"
    })
}

#[cfg(test)]
mod tests {
    use super::{
        upsert_graph_delta_json_schema_string, upsert_graph_delta_json_schema_value,
        UPSERT_GRAPH_DELTA_SCHEMA_ID,
    };

    #[test]
    fn schema_includes_core_arrays() {
        let schema = upsert_graph_delta_json_schema_value();
        let properties = schema["properties"]
            .as_object()
            .expect("schema properties should be object");

        assert!(properties.contains_key("universes"));
        assert!(properties.contains_key("entities"));
        assert!(properties.contains_key("blocks"));
        assert!(properties.contains_key("edges"));
    }

    #[test]
    fn property_value_requires_exactly_one_typed_field() {
        let schema = upsert_graph_delta_json_schema_value();
        let property_value =
            &schema["properties"]["entities"]["items"]["properties"]["properties"]["items"];

        assert_eq!(property_value["required"], serde_json::json!(["key"]));
        assert_eq!(property_value["minProperties"], serde_json::json!(2));
        assert_eq!(property_value["maxProperties"], serde_json::json!(2));
        assert_eq!(
            property_value["oneOf"].as_array().map(std::vec::Vec::len),
            Some(6)
        );
    }

    #[test]
    fn schema_string_is_deterministic() {
        let first = upsert_graph_delta_json_schema_string();
        let second = upsert_graph_delta_json_schema_string();

        assert_eq!(first, second);
        assert!(first.contains(UPSERT_GRAPH_DELTA_SCHEMA_ID));
    }
}
