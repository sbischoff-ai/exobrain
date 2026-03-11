use anyhow::Result;
use async_trait::async_trait;
use sqlx::{postgres::PgPoolOptions, PgPool, Row};

use crate::{
    domain::{
        EdgeEndpointRule, SchemaKind, SchemaType, TypeInheritance, TypeProperty,
        UpsertSchemaTypePropertyInput,
    },
    ports::SchemaRepository,
};

pub struct PostgresSchemaRepository {
    pool: PgPool,
}

impl PostgresSchemaRepository {
    pub async fn new(dsn: &str) -> Result<Self> {
        let pool = PgPoolOptions::new().max_connections(5).connect(dsn).await?;
        Ok(Self { pool })
    }
}

#[async_trait]
impl SchemaRepository for PostgresSchemaRepository {
    async fn get_by_kind(&self, kind: SchemaKind) -> Result<Vec<SchemaType>> {
        let rows = sqlx::query(
            "SELECT id, kind, name, description, active FROM knowledge_graph_schema_types WHERE kind = $1 AND active = TRUE ORDER BY name",
        )
        .bind(kind.as_db_str())
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| SchemaType {
                id: row.get("id"),
                kind: row.get("kind"),
                name: row.get("name"),
                description: row.get("description"),
                active: row.get("active"),
            })
            .collect())
    }

    async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
        let row = sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_types (id, kind, name, description, active)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id)
            DO UPDATE SET kind = EXCLUDED.kind, name = EXCLUDED.name, description = EXCLUDED.description, active = EXCLUDED.active, updated_at = NOW()
            RETURNING id, kind, name, description, active"#,
        )
        .bind(&schema_type.id)
        .bind(&schema_type.kind)
        .bind(&schema_type.name)
        .bind(&schema_type.description)
        .bind(schema_type.active)
        .fetch_one(&self.pool)
        .await?;

        Ok(SchemaType {
            id: row.get("id"),
            kind: row.get("kind"),
            name: row.get("name"),
            description: row.get("description"),
            active: row.get("active"),
        })
    }

    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
        let rows = sqlx::query(
            "SELECT child_type_id, parent_type_id, description, active FROM knowledge_graph_schema_type_inheritance WHERE active = TRUE ORDER BY child_type_id, parent_type_id",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| TypeInheritance {
                child_type_id: row.get("child_type_id"),
                parent_type_id: row.get("parent_type_id"),
                description: row.get("description"),
                active: row.get("active"),
            })
            .collect())
    }

    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
        let rows = sqlx::query(
            "SELECT owner_type_id, prop_name, value_type, required, readable, writable, active, description FROM knowledge_graph_schema_type_properties WHERE active = TRUE ORDER BY owner_type_id, prop_name",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| TypeProperty {
                owner_type_id: row.get("owner_type_id"),
                prop_name: row.get("prop_name"),
                value_type: row.get("value_type"),
                required: row.get("required"),
                readable: row.get("readable"),
                writable: row.get("writable"),
                active: row.get("active"),
                description: row.get("description"),
            })
            .collect())
    }

    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        let rows = sqlx::query(
            "SELECT edge_type_id, from_node_type_id, to_node_type_id, active, description FROM knowledge_graph_schema_edge_rules WHERE active = TRUE ORDER BY edge_type_id, from_node_type_id, to_node_type_id",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| EdgeEndpointRule {
                edge_type_id: row.get("edge_type_id"),
                from_node_type_id: row.get("from_node_type_id"),
                to_node_type_id: row.get("to_node_type_id"),
                active: row.get("active"),
                description: row.get("description"),
            })
            .collect())
    }

    async fn get_schema_type(&self, id: &str) -> Result<Option<SchemaType>> {
        let row = sqlx::query(
            "SELECT id, kind, name, description, active FROM knowledge_graph_schema_types WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|row| SchemaType {
            id: row.get("id"),
            kind: row.get("kind"),
            name: row.get("name"),
            description: row.get("description"),
            active: row.get("active"),
        }))
    }

    async fn get_parent_for_child(&self, child_type_id: &str) -> Result<Option<String>> {
        let row = sqlx::query(
            "SELECT parent_type_id FROM knowledge_graph_schema_type_inheritance WHERE child_type_id = $1 AND active = TRUE LIMIT 1",
        )
        .bind(child_type_id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|r| r.get("parent_type_id")))
    }

    async fn is_descendant_of_entity(&self, node_type_id: &str) -> Result<bool> {
        if node_type_id == "node.entity" {
            return Ok(true);
        }

        let row = sqlx::query(
            r#"WITH RECURSIVE lineage AS (
                SELECT child_type_id, parent_type_id
                FROM knowledge_graph_schema_type_inheritance
                WHERE child_type_id = $1 AND active = TRUE
                UNION ALL
                SELECT i.child_type_id, i.parent_type_id
                FROM knowledge_graph_schema_type_inheritance i
                JOIN lineage l ON i.child_type_id = l.parent_type_id
                WHERE i.active = TRUE
            )
            SELECT 1 AS found FROM lineage WHERE parent_type_id = 'node.entity' LIMIT 1"#,
        )
        .bind(node_type_id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.is_some())
    }

    async fn upsert_inheritance(
        &self,
        child_type_id: &str,
        parent_type_id: &str,
        description: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_type_inheritance (child_type_id, parent_type_id, active, description, universe_id)
            VALUES ($1, $2, TRUE, $3, NULL)
            ON CONFLICT (child_type_id, parent_type_id)
            DO UPDATE SET active = TRUE, description = EXCLUDED.description"#,
        )
        .bind(child_type_id)
        .bind(parent_type_id)
        .bind(description)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn upsert_type_property(
        &self,
        owner_type_id: &str,
        property: &UpsertSchemaTypePropertyInput,
    ) -> Result<()> {
        sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_type_properties (owner_type_id, prop_name, value_type, required, readable, writable, active, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (owner_type_id, prop_name)
            DO UPDATE SET
              value_type = EXCLUDED.value_type,
              required = EXCLUDED.required,
              readable = EXCLUDED.readable,
              writable = EXCLUDED.writable,
              active = EXCLUDED.active,
              description = EXCLUDED.description"#,
        )
        .bind(owner_type_id)
        .bind(&property.prop_name)
        .bind(&property.value_type)
        .bind(property.required)
        .bind(property.readable)
        .bind(property.writable)
        .bind(property.active)
        .bind(&property.description)
        .execute(&self.pool)
        .await?;

        Ok(())
    }
}
