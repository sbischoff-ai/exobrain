use anyhow::anyhow;

use crate::application::errors::{AppResult, ApplicationError};
use crate::application::KnowledgeApplication;
use crate::domain::{FindTypeCandidatesQuery, FindTypeCandidatesResult, SchemaKind, SchemaType};
use crate::infrastructure::qdrant::render_schema_type_embedding_input;

const DEFAULT_LIMIT: usize = 10;
const MAX_LIMIT: usize = 100;

pub(crate) async fn find_type_candidates(
    app: &KnowledgeApplication,
    kind: SchemaKind,
    mut query: FindTypeCandidatesQuery,
) -> AppResult<FindTypeCandidatesResult> {
    query.name = query.name.trim().to_lowercase();
    query.description = query.description.trim().to_string();

    if query.name.is_empty() && query.description.is_empty() {
        return Err(ApplicationError::validation(
            "name or description is required",
        ));
    }

    let limit = query.limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT);
    let embedding_input = render_schema_type_embedding_input(&SchemaType {
        id: "query".to_string(),
        kind: kind.as_db_str().to_string(),
        name: query.name,
        description: query.description,
        active: true,
    })?;

    let vectors = app.embedder.embed_texts(&[embedding_input]).await?;
    let query_vector = vectors
        .first()
        .ok_or_else(|| ApplicationError::Internal(anyhow!("embedder returned no vectors")))?;

    let type_vector_repository = app.type_vector_repository.as_ref().ok_or_else(|| {
        ApplicationError::failed_precondition("type vector repository not configured")
    })?;

    type_vector_repository
        .search_schema_type_vectors(kind, query_vector, limit)
        .await
        .map_err(Into::into)
}
