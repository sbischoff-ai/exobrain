use serde_json::Error as SerdeJsonError;

use crate::presentation::upsert_delta_json_schema::upsert_graph_delta_json_schema_value;

pub fn generate_upsert_graph_delta_json_schema_string() -> Result<String, SerdeJsonError> {
    serde_json::to_string_pretty(&upsert_graph_delta_json_schema_value())
}

#[cfg(test)]
mod tests {
    use super::generate_upsert_graph_delta_json_schema_string;

    #[test]
    fn generator_returns_schema_json() {
        let schema = generate_upsert_graph_delta_json_schema_string()
            .expect("schema generation should serialize successfully");

        assert!(schema.contains("$schema"));
        assert!(schema.contains("$id"));
    }
}
