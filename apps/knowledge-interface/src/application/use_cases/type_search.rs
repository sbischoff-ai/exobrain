use crate::application::errors::{AppResult, ApplicationError};
use crate::application::KnowledgeApplication;
use crate::domain::{FindTypeCandidatesQuery, FindTypeCandidatesResult, SchemaKind};

const DEFAULT_LIMIT: usize = 10;
const MAX_LIMIT: usize = 50;

pub(crate) async fn find_node_type_candidates(
    app: &KnowledgeApplication,
    query: FindTypeCandidatesQuery,
) -> AppResult<FindTypeCandidatesResult> {
    find_type_candidates(app, query, SchemaKind::Node).await
}

pub(crate) async fn find_edge_type_candidates(
    app: &KnowledgeApplication,
    query: FindTypeCandidatesQuery,
) -> AppResult<FindTypeCandidatesResult> {
    find_type_candidates(app, query, SchemaKind::Edge).await
}

async fn find_type_candidates(
    app: &KnowledgeApplication,
    mut query: FindTypeCandidatesQuery,
    kind: SchemaKind,
) -> AppResult<FindTypeCandidatesResult> {
    query.name = query.name.trim().to_lowercase();
    query.description = query.description.trim().to_lowercase();

    if query.name.is_empty() && query.description.is_empty() {
        return Err(ApplicationError::validation(
            "at least one of name or description is required",
        ));
    }

    let embedding_text = match kind {
        SchemaKind::Node => format!(
            "entity type: {}\n\ndescription:\n{}",
            query.name, query.description
        ),
        SchemaKind::Edge => format!(
            "relationship type: {}\n\ndescription:\n{}",
            query.name, query.description
        ),
    };

    let vector = app
        .embedder
        .embed_texts(&[embedding_text])
        .await?
        .into_iter()
        .next()
        .ok_or_else(|| ApplicationError::from(anyhow::anyhow!("embedder returned no vectors")))?;

    let limit = query.limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT) as u64;
    let repo = app.type_vector_repository.as_ref().ok_or_else(|| {
        ApplicationError::from(anyhow::anyhow!("type vector repository not configured"))
    })?;

    let mut candidates = match kind {
        SchemaKind::Node => repo.search_node_type_candidates(&vector, limit).await?,
        SchemaKind::Edge => repo.search_edge_type_candidates(&vector, limit).await?,
    };

    candidates.sort_by(|a, b| {
        b.score
            .total_cmp(&a.score)
            .then_with(|| a.type_id.cmp(&b.type_id))
    });

    Ok(FindTypeCandidatesResult { candidates })
}
