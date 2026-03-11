use schemars::JsonSchema;
use serde_json::{Map, Value};
use uuid::Uuid;

pub const UPSERT_GRAPH_DELTA_SCHEMA_ID: &str =
    "https://exobrain.dev/schemas/knowledge/upsert-graph-delta-request.json";

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct UpsertGraphDeltaRequestSchemaDto {
    universes: Vec<UniverseNodeSchemaDto>,
    entities: Vec<EntityNodeSchemaDto>,
    blocks: Vec<BlockNodeSchemaDto>,
    edges: Vec<GraphEdgeSchemaDto>,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct UniverseNodeSchemaDto {
    id: Uuid,
    name: String,
    user_id: Uuid,
    visibility: VisibilitySchemaDto,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct EntityNodeSchemaDto {
    id: Uuid,
    type_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    universe_id: Option<Uuid>,
    properties: Vec<PropertyValueSchemaDto>,
    user_id: Uuid,
    visibility: VisibilitySchemaDto,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct BlockNodeSchemaDto {
    id: Uuid,
    type_id: String,
    properties: Vec<PropertyValueSchemaDto>,
    user_id: Uuid,
    visibility: VisibilitySchemaDto,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct GraphEdgeSchemaDto {
    from_id: Uuid,
    to_id: Uuid,
    edge_type: String,
    properties: Vec<PropertyValueSchemaDto>,
    user_id: Uuid,
    visibility: VisibilitySchemaDto,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
#[schemars(rename_all = "SCREAMING_SNAKE_CASE")]
enum VisibilitySchemaDto {
    Private,
    Shared,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(untagged)]
enum PropertyValueSchemaDto {
    String(PropertyValueStringSchemaDto),
    Float(PropertyValueFloatSchemaDto),
    Int(PropertyValueIntSchemaDto),
    Bool(PropertyValueBoolSchemaDto),
    DateTime(PropertyValueDateTimeSchemaDto),
    Json(PropertyValueJsonSchemaDto),
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueStringSchemaDto {
    key: String,
    string_value: String,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueFloatSchemaDto {
    key: String,
    float_value: f64,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueIntSchemaDto {
    key: String,
    int_value: i64,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueBoolSchemaDto {
    key: String,
    bool_value: bool,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueDateTimeSchemaDto {
    key: String,
    #[schemars(with = "chrono::DateTime<chrono::Utc>")]
    datetime_value: String,
}

#[allow(dead_code)]
#[derive(JsonSchema)]
#[serde(deny_unknown_fields)]
struct PropertyValueJsonSchemaDto {
    key: String,
    json_value: Value,
}

pub fn upsert_graph_delta_json_schema_value() -> Value {
    let mut schema = serde_json::to_value(schemars::schema_for!(UpsertGraphDeltaRequestSchemaDto))
        .expect("schema generation should succeed");

    let root = schema
        .as_object_mut()
        .expect("generated schema should be an object");

    root.insert(
        "$schema".to_string(),
        Value::String("https://json-schema.org/draft/2020-12/schema".to_string()),
    );
    root.insert(
        "$id".to_string(),
        Value::String(UPSERT_GRAPH_DELTA_SCHEMA_ID.to_string()),
    );
    root.insert(
        "title".to_string(),
        Value::String("UpsertGraphDeltaRequest".to_string()),
    );

    sort_json_value(schema)
}

pub fn try_upsert_graph_delta_json_schema_string() -> Result<String, serde_json::Error> {
    serde_json::to_string_pretty(&upsert_graph_delta_json_schema_value())
}

fn sort_json_value(value: Value) -> Value {
    match value {
        Value::Object(object) => {
            let sorted = object
                .into_iter()
                .map(|(k, v)| (k, sort_json_value(v)))
                .collect::<std::collections::BTreeMap<_, _>>();

            let mut stable = Map::new();
            for (key, val) in sorted {
                stable.insert(key, val);
            }
            Value::Object(stable)
        }
        Value::Array(items) => Value::Array(items.into_iter().map(sort_json_value).collect()),
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        try_upsert_graph_delta_json_schema_string, upsert_graph_delta_json_schema_value,
        UPSERT_GRAPH_DELTA_SCHEMA_ID,
    };

    #[test]
    fn schema_includes_core_arrays() {
        let schema = upsert_graph_delta_json_schema_value();
        let properties = schema["properties"]
            .as_object()
            .expect("schema properties should be object");
        let mut required = schema["required"]
            .as_array()
            .expect("schema required should be an array")
            .iter()
            .filter_map(|value| value.as_str().map(ToString::to_string))
            .collect::<Vec<_>>();

        required.sort();

        assert!(properties.contains_key("universes"));
        assert!(properties.contains_key("entities"));
        assert!(properties.contains_key("blocks"));
        assert!(properties.contains_key("edges"));
        assert_eq!(required, vec!["blocks", "edges", "entities", "universes"]);
    }

    #[test]
    fn property_value_contains_all_typed_variants() {
        let schema = upsert_graph_delta_json_schema_value();
        let definitions = schema["definitions"]
            .as_object()
            .expect("definitions should exist");
        let variants = schema["definitions"]["PropertyValueSchemaDto"]["anyOf"]
            .as_array()
            .expect("property value should be represented as anyOf variants");

        assert_eq!(variants.len(), 6);

        let mut typed_fields = variants
            .iter()
            .filter_map(|variant| {
                let variant_ref = variant["$ref"].as_str()?;
                let variant_name = variant_ref.strip_prefix("#/definitions/")?;

                definitions[variant_name]["properties"]
                    .as_object()
                    .and_then(|properties| properties.keys().find(|field| *field != "key"))
                    .cloned()
            })
            .collect::<Vec<_>>();

        typed_fields.sort();

        assert_eq!(
            typed_fields,
            vec![
                "bool_value",
                "datetime_value",
                "float_value",
                "int_value",
                "json_value",
                "string_value",
            ]
        );
    }

    #[test]
    fn schema_metadata_and_string_are_stable() {
        let schema = upsert_graph_delta_json_schema_value();
        let first = try_upsert_graph_delta_json_schema_string().expect("schema should serialize");
        let second = try_upsert_graph_delta_json_schema_string().expect("schema should serialize");

        assert_eq!(
            schema["$id"],
            serde_json::json!(UPSERT_GRAPH_DELTA_SCHEMA_ID)
        );
        assert_eq!(
            schema["$schema"],
            serde_json::json!("https://json-schema.org/draft/2020-12/schema")
        );
        assert_eq!(first, second);
        assert!(first.contains(UPSERT_GRAPH_DELTA_SCHEMA_ID));
    }
}
