use std::collections::HashSet;
use std::sync::Arc;

#[cfg(test)]
use anyhow::{anyhow, Result};

#[cfg(test)]
use crate::domain::EmbeddedBlock;

use crate::{
    domain::{
        BlockNode, EntityNode, ExtractionUniverse, FindEntityCandidatesQuery,
        FindEntityCandidatesResult, FullSchema, GetEntityContextQuery, GetEntityContextResult,
        GraphDelta, GraphEdge, ListEntitiesByTypeQuery, ListEntitiesByTypeResult, PropertyScalar,
        PropertyValue, SchemaKind, SchemaType, UniverseNode, UpsertSchemaTypeCommand,
        UserInitGraphNodeIds, Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository, TypeVectorRepository},
};

pub(crate) mod errors;
pub(crate) mod graph_resolution;
pub(crate) mod pagination;
pub(crate) mod type_hierarchy;
pub mod use_cases;
pub(crate) mod validation;

use self::errors::{AppResult, ApplicationError};
use self::validation::is_global_property_owner;
use tracing::{error, info};

pub(crate) use use_cases::extraction_schema::{
    build_entity_type_property_context, build_extraction_edge_types_from_input,
    build_extraction_entity_types_from_input, EntityTypePropertyContext,
    EntityTypePropertyContextOptions, ExtractionEdgeType, ExtractionEntityType,
    ExtractionPropertyContext, ExtractionSchemaBuildInput, ExtractionSchemaOptions,
    ExtractionUniverseContext,
};

const EXOBRAIN_USER_ID: &str = "exobrain";
pub(crate) const COMMON_UNIVERSE_ID: &str = "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f";
const COMMON_UNIVERSE_NAME: &str = "Real World";
const COMMON_EXOBRAIN_ENTITY_ID: &str = "8c75cc89-6204-4fed-aec1-34d032ff95ee";
const COMMON_EXOBRAIN_BLOCK_ID: &str = "ea5ca80f-346b-4f66-bff2-d307ce5d7da9";
pub struct KnowledgeApplication {
    schema_repository: Arc<dyn SchemaRepository>,
    graph_repository: Arc<dyn GraphRepository>,
    embedder: Arc<dyn Embedder>,
    type_vector_repository: Option<Arc<dyn TypeVectorRepository>>,
}

impl KnowledgeApplication {
    pub fn new(
        schema_repository: Arc<dyn SchemaRepository>,
        graph_repository: Arc<dyn GraphRepository>,
        embedder: Arc<dyn Embedder>,
    ) -> Self {
        Self {
            schema_repository,
            graph_repository,
            embedder,
            type_vector_repository: None,
        }
    }

    pub fn with_type_vector_repository(
        mut self,
        type_vector_repository: Arc<dyn TypeVectorRepository>,
    ) -> Self {
        self.type_vector_repository = Some(type_vector_repository);
        self
    }

    pub async fn get_schema(&self) -> AppResult<FullSchema> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let edge_types = self.schema_repository.get_by_kind(SchemaKind::Edge).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let properties = self.schema_repository.get_all_properties().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        let hydrated_nodes = node_types
            .into_iter()
            .map(|schema_type| {
                let node_id = schema_type.id.clone();
                let type_properties = properties
                    .iter()
                    .filter(|p| {
                        p.owner_type_id == node_id
                            || is_global_property_owner(&node_id, &p.owner_type_id)
                    })
                    .cloned()
                    .collect();
                let parents = inheritance
                    .iter()
                    .filter(|i| i.child_type_id == node_id)
                    .cloned()
                    .collect();

                crate::domain::SchemaNodeTypeHydrated {
                    schema_type,
                    properties: type_properties,
                    parents,
                }
            })
            .collect();

        let hydrated_edges = edge_types
            .into_iter()
            .map(|schema_type| {
                let edge_id = schema_type.id.clone();
                let type_properties = properties
                    .iter()
                    .filter(|p| {
                        p.owner_type_id == edge_id
                            || is_global_property_owner(&edge_id, &p.owner_type_id)
                    })
                    .cloned()
                    .collect();
                let rules = edge_rules
                    .iter()
                    .filter(|r| r.edge_type_id == edge_id)
                    .cloned()
                    .collect();

                crate::domain::SchemaEdgeTypeHydrated {
                    schema_type,
                    properties: type_properties,
                    rules,
                }
            })
            .collect();

        Ok(FullSchema {
            node_types: hydrated_nodes,
            edge_types: hydrated_edges,
        })
    }

    pub async fn get_entity_extraction_schema_types(
        &self,
        options: ExtractionSchemaOptions,
    ) -> AppResult<Vec<ExtractionEntityType>> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;

        Ok(build_extraction_entity_types_from_input(
            ExtractionSchemaBuildInput {
                node_types,
                edge_types: Vec::new(),
                inheritance,
                edge_rules: Vec::new(),
            },
            options,
        ))
    }

    pub async fn get_edge_extraction_schema_types(
        &self,
        first_entity_type: &str,
        second_entity_type: &str,
        options: ExtractionSchemaOptions,
    ) -> AppResult<Vec<ExtractionEdgeType>> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let edge_types = self.schema_repository.get_by_kind(SchemaKind::Edge).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        Ok(build_extraction_edge_types_from_input(
            ExtractionSchemaBuildInput {
                node_types,
                edge_types,
                inheritance,
                edge_rules,
            },
            first_entity_type,
            second_entity_type,
            options,
        ))
    }

    pub async fn get_extraction_universes(
        &self,
        user_id: &str,
    ) -> AppResult<Vec<ExtractionUniverseContext>> {
        let trimmed_user_id = user_id.trim();
        if trimmed_user_id.is_empty() {
            return Err(ApplicationError::validation("user_id is required"));
        }

        let mut universes = self
            .graph_repository
            .get_extraction_universes(trimmed_user_id)
            .await?
            .into_iter()
            .map(|universe: ExtractionUniverse| ExtractionUniverseContext {
                id: universe.id,
                name: universe.name,
                described_by_text: universe.described_by_text,
            })
            .collect::<Vec<_>>();
        universes.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(universes)
    }

    pub async fn get_entity_type_property_context(
        &self,
        type_id: &str,
        options: EntityTypePropertyContextOptions,
    ) -> AppResult<EntityTypePropertyContext> {
        let schema = self.get_schema().await?;
        build_entity_type_property_context(schema, type_id, options)
    }

    pub async fn upsert_schema_type(
        &self,
        command: UpsertSchemaTypeCommand,
    ) -> AppResult<SchemaType> {
        let schema_type = command.schema_type;

        let schema_kind = schema_type.schema_kind().ok_or_else(|| {
            ApplicationError::validation("schema kind must be one of: node, edge")
        })?;

        if matches!(schema_kind, SchemaKind::Edge) && command.parent_type_id.is_some() {
            return Err(ApplicationError::failed_precondition(
                "edge inheritance is out of scope",
            ));
        }

        if matches!(schema_kind, SchemaKind::Node) {
            if schema_type.id == "node.entity" {
                if command.parent_type_id.is_some() {
                    return Err(ApplicationError::failed_precondition(
                        "node.entity cannot declare a parent",
                    ));
                }
            } else {
                let parent_type_id = command.parent_type_id.clone().ok_or_else(|| {
                    ApplicationError::validation(
                        "node types (except node.entity) must declare parent_type_id",
                    )
                })?;

                let parent_schema = self
                    .schema_repository
                    .get_schema_type(&parent_type_id)
                    .await?
                    .ok_or_else(|| ApplicationError::validation("parent type does not exist"))?;

                if !matches!(parent_schema.schema_kind(), Some(SchemaKind::Node)) {
                    return Err(ApplicationError::validation("parent type must be a node"));
                }

                if !self
                    .schema_repository
                    .is_descendant_of_entity(&parent_type_id)
                    .await?
                {
                    return Err(ApplicationError::validation(
                        "node parent must descend from node.entity",
                    ));
                }

                if let Some(existing_parent) = self
                    .schema_repository
                    .get_parent_for_child(&schema_type.id)
                    .await?
                {
                    if existing_parent != parent_type_id {
                        return Err(ApplicationError::failed_precondition(
                            "a node type cannot have multiple parents",
                        ));
                    }
                }
            }
        }

        let previous_schema_type = self
            .schema_repository
            .get_schema_type(&schema_type.id)
            .await?;
        let upserted = self.schema_repository.upsert(&schema_type).await?;

        if let Err(sync_error) = self.sync_schema_type_vector(&upserted).await {
            self.rollback_schema_type_write(&upserted, previous_schema_type.as_ref())
                .await?;
            return Err(sync_error);
        }

        if matches!(upserted.schema_kind(), Some(SchemaKind::Node)) && upserted.id != "node.entity"
        {
            let parent = command.parent_type_id.as_ref().ok_or_else(|| {
                ApplicationError::validation("parent_type_id required for node subtype")
            })?;
            self.schema_repository
                .upsert_inheritance(
                    &upserted.id,
                    parent,
                    "Parent relation created via UpsertSchemaType",
                )
                .await?;
        }

        for property in &command.properties {
            self.schema_repository
                .upsert_type_property(&upserted.id, property)
                .await?;
        }

        Ok(upserted)
    }

    async fn sync_schema_type_vector(&self, schema_type: &SchemaType) -> AppResult<()> {
        let Some(type_vector_repository) = self.type_vector_repository.as_ref() else {
            info!(
                type_id = %schema_type.id,
                kind = %schema_type.kind,
                operation = "upsert",
                "schema type vector sync skipped; repository not configured"
            );
            return Ok(());
        };

        let embedding_input =
            crate::infrastructure::qdrant::render_schema_type_embedding_input(schema_type)?;

        info!(
            type_id = %schema_type.id,
            kind = %schema_type.kind,
            operation = "embed",
            "embedding schema type text for vector sync"
        );
        let embeddings = self.embedder.embed_texts(&[embedding_input]).await?;
        let vector = embeddings.into_iter().next().ok_or_else(|| {
            ApplicationError::Internal(anyhow::anyhow!(
                "embedder returned no vectors for schema type sync"
            ))
        })?;

        info!(
            type_id = %schema_type.id,
            kind = %schema_type.kind,
            operation = "upsert",
            "upserting schema type vector"
        );
        type_vector_repository
            .upsert_schema_type_vector(schema_type, &vector)
            .await
            .map_err(|error| {
                error!(
                    type_id = %schema_type.id,
                    kind = %schema_type.kind,
                    operation = "upsert",
                    error = %error,
                    "schema type vector upsert failed"
                );
                ApplicationError::Internal(anyhow::anyhow!(format!(
                    "failed to sync vector for schema type {} (kind {}): {error}",
                    schema_type.id, schema_type.kind
                )))
            })
    }

    async fn rollback_schema_type_write(
        &self,
        schema_type: &SchemaType,
        previous_schema_type: Option<&SchemaType>,
    ) -> AppResult<()> {
        info!(
            type_id = %schema_type.id,
            kind = %schema_type.kind,
            operation = "rollback",
            "rolling back schema type write after vector sync failure"
        );

        match previous_schema_type {
            Some(previous) => {
                self.schema_repository.upsert(previous).await?;
            }
            None => {
                self.schema_repository
                    .delete_schema_type(&schema_type.id)
                    .await?;
            }
        }

        Ok(())
    }

    pub async fn ensure_common_root_graph(&self) -> AppResult<()> {
        if self.graph_repository.common_root_graph_exists().await? {
            return Ok(());
        }

        self.upsert_graph_delta(Self::common_root_delta()).await
    }

    pub async fn get_user_init_graph(
        &self,
        user_id: &str,
        user_name: &str,
    ) -> AppResult<UserInitGraphNodeIds> {
        let trimmed_user_id = user_id.trim();
        if trimmed_user_id.is_empty() {
            return Err(ApplicationError::validation("user_id is required"));
        }

        let trimmed_user_name = user_name.trim();
        if trimmed_user_name.is_empty() {
            return Err(ApplicationError::validation("user_name is required"));
        }

        if self
            .graph_repository
            .user_graph_needs_initialization(trimmed_user_id)
            .await?
        {
            let delta = Self::user_init_delta(trimmed_user_id, trimmed_user_name);
            let node_ids = Self::user_init_graph_node_ids(&delta)?;
            self.apply_user_initialization_delta(trimmed_user_id, delta, &node_ids)
                .await?;
            return Ok(node_ids);
        }

        let node_ids = self
            .graph_repository
            .get_user_init_graph_node_ids(trimmed_user_id)
            .await?
            .ok_or_else(|| {
                ApplicationError::failed_precondition("user graph marker missing node ids")
            })?;

        self.graph_repository
            .update_person_name(&node_ids.person_entity_id, trimmed_user_name)
            .await?;

        Ok(node_ids)
    }

    fn common_root_delta() -> GraphDelta {
        GraphDelta {
            universes: vec![UniverseNode {
                id: COMMON_UNIVERSE_ID.to_string(),
                name: COMMON_UNIVERSE_NAME.to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
            }],
            entities: vec![EntityNode {
                id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                type_id: "node.concept".to_string(),
                universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Exobrain".to_string()),
                }],
                resolved_labels: vec![],
            }],
            blocks: vec![BlockNode {
                id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                type_id: "node.block".to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain is the shared platform for capturing and organizing knowledge, powering assistants and knowledge workflows.".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![
                GraphEdge {
                    from_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: EXOBRAIN_USER_ID.to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("bootstrap universe assignment"),
                },
                GraphEdge {
                    from_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                    to_id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: EXOBRAIN_USER_ID.to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("bootstrap description link"),
                },
            ],
        }
    }

    fn user_init_delta(user_id: &str, user_name: &str) -> GraphDelta {
        let person_entity_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("person:{user_id}").as_bytes(),
        )
        .to_string();
        let assistant_entity_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("assistant:{user_id}").as_bytes(),
        )
        .to_string();
        let assistant_block_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("assistant-block:{user_id}").as_bytes(),
        )
        .to_string();

        GraphDelta {
            universes: vec![],
            entities: vec![
                EntityNode {
                    id: person_entity_id.clone(),
                    type_id: "node.person".to_string(),
                    universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: vec![
                        PropertyValue {
                            key: "name".to_string(),
                            value: PropertyScalar::String(user_name.to_string()),
                        },
                        PropertyValue {
                            key: "aliases".to_string(),
                            value: PropertyScalar::Json("[\"me\",\"I\",\"myself\"]".to_string()),
                        },
                    ],
                    resolved_labels: vec![],
                },
                EntityNode {
                    id: assistant_entity_id.clone(),
                    type_id: "node.ai_agent".to_string(),
                    universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Exobrain Assistant".to_string()),
                    }],
                    resolved_labels: vec![],
                },
            ],
            blocks: vec![BlockNode {
                id: assistant_block_id.clone(),
                type_id: "node.block".to_string(),
                user_id: user_id.to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain Assistant is your personal assistant in Exobrain. It chats with you and helps organize your knowledge graph.".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![
                GraphEdge {
                    from_id: person_entity_id.clone(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("user universe assignment"),
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant universe assignment"),
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: person_entity_id,
                    edge_type: "RELATED_TO".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant relationship"),
                },
                GraphEdge {
                    from_id: assistant_entity_id,
                    to_id: assistant_block_id,
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant description link"),
                },
            ],
        }
    }

    fn user_init_graph_node_ids(delta: &GraphDelta) -> AppResult<UserInitGraphNodeIds> {
        let person_entity_id = delta
            .entities
            .iter()
            .find(|entity| entity.type_id == "node.person")
            .map(|entity| entity.id.clone())
            .ok_or_else(|| {
                ApplicationError::failed_precondition("missing person entity in user init delta")
            })?;
        let assistant_entity_id = delta
            .entities
            .iter()
            .find(|entity| entity.type_id == "node.ai_agent")
            .map(|entity| entity.id.clone())
            .ok_or_else(|| {
                ApplicationError::failed_precondition("missing assistant entity in user init delta")
            })?;

        Ok(UserInitGraphNodeIds {
            person_entity_id,
            assistant_entity_id,
        })
    }

    pub async fn find_entity_candidates(
        &self,
        query: FindEntityCandidatesQuery,
    ) -> AppResult<FindEntityCandidatesResult> {
        use_cases::entity_search::find_entity_candidates(self, query).await
    }

    pub async fn list_entities_by_type(
        &self,
        query: ListEntitiesByTypeQuery,
    ) -> AppResult<ListEntitiesByTypeResult> {
        use_cases::entity_listing::list_entities_by_type(self, query).await
    }

    pub async fn get_entity_context(
        &self,
        query: GetEntityContextQuery,
    ) -> AppResult<GetEntityContextResult> {
        use_cases::entity_context::get_entity_context(self, query).await
    }

    pub async fn upsert_graph_delta(&self, delta: GraphDelta) -> AppResult<()> {
        self.ensure_users_initialized_for_delta(&delta).await?;
        self.upsert_graph_delta_internal(delta).await
    }

    async fn apply_user_initialization_delta(
        &self,
        user_id: &str,
        delta: GraphDelta,
        node_ids: &UserInitGraphNodeIds,
    ) -> AppResult<()> {
        self.upsert_graph_delta_internal(delta).await?;
        self.graph_repository
            .mark_user_graph_initialized(user_id, node_ids)
            .await
            .map_err(Into::into)
    }

    async fn upsert_graph_delta_internal(&self, delta: GraphDelta) -> AppResult<()> {
        use_cases::upsert_graph_delta::upsert_graph_delta_internal(self, delta).await
    }

    async fn ensure_users_initialized_for_delta(&self, delta: &GraphDelta) -> AppResult<()> {
        let mut user_ids = HashSet::new();

        for universe in &delta.universes {
            user_ids.insert(universe.user_id.trim().to_string());
        }
        for entity in &delta.entities {
            user_ids.insert(entity.user_id.trim().to_string());
        }
        for block in &delta.blocks {
            user_ids.insert(block.user_id.trim().to_string());
        }
        for edge in &delta.edges {
            user_ids.insert(edge.user_id.trim().to_string());
        }

        for user_id in user_ids {
            if user_id.is_empty() || user_id == EXOBRAIN_USER_ID {
                continue;
            }
            if self
                .graph_repository
                .user_graph_needs_initialization(&user_id)
                .await?
            {
                // In implicit initialization flow, we deterministically reuse `user_id` as
                // `user_name` when no richer user profile is available in the request.
                let delta = Self::user_init_delta(&user_id, &user_id);
                let node_ids = Self::user_init_graph_node_ids(&delta)?;
                self.apply_user_initialization_delta(&user_id, delta, &node_ids)
                    .await?;
            }
        }

        Ok(())
    }
}

fn default_edge_properties(provenance_hint: &str) -> Vec<PropertyValue> {
    vec![
        PropertyValue {
            key: "confidence".to_string(),
            value: PropertyScalar::Float(1.0),
        },
        PropertyValue {
            key: "status".to_string(),
            value: PropertyScalar::String("asserted".to_string()),
        },
        PropertyValue {
            key: "provenance_hint".to_string(),
            value: PropertyScalar::String(provenance_hint.to_string()),
        },
    ]
}

#[cfg(test)]
mod tests;
