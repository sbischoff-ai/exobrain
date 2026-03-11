use crate::application::errors::{AppResult, ApplicationError};
use crate::application::KnowledgeApplication;
use crate::domain::{TypeMatchingQuery, TypeMatchingResult, TypeScoredCandidate};

const DEFAULT_LIMIT: usize = 10;
const MAX_LIMIT: usize = 100;

pub(crate) async fn find_node_type_candidates(
    app: &KnowledgeApplication,
    query: TypeMatchingQuery,
) -> AppResult<TypeMatchingResult> {
    find_type_candidates(app, query, true).await
}

pub(crate) async fn find_edge_type_candidates(
    app: &KnowledgeApplication,
    query: TypeMatchingQuery,
) -> AppResult<TypeMatchingResult> {
    find_type_candidates(app, query, false).await
}

async fn find_type_candidates(
    app: &KnowledgeApplication,
    mut query: TypeMatchingQuery,
    node_types: bool,
) -> AppResult<TypeMatchingResult> {
    query.name = query.name.trim().to_string();
    query.description = query.description.trim().to_string();

    if query.name.is_empty() && query.description.is_empty() {
        return Err(ApplicationError::validation(
            "name or description is required",
        ));
    }

    let limit = query.limit.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT) as u64;

    let embedding_input = if node_types {
        format!(
            "entity type: {}\n\ndescription:\n{}",
            query.name, query.description
        )
    } else {
        format!(
            "relationship type: {}\n\ndescription:\n{}",
            query.name, query.description
        )
    };

    let query_vector = app
        .embedder
        .embed_texts(&[embedding_input])
        .await?
        .into_iter()
        .next()
        .ok_or_else(|| {
            ApplicationError::Internal(anyhow::anyhow!(
                "embedder returned no vectors for type matching"
            ))
        })?;

    let repo = app.type_vector_repository.as_ref().ok_or_else(|| {
        ApplicationError::failed_precondition("type vector repository is not configured")
    })?;

    let candidates = if node_types {
        repo.search_node_type_vectors(&query_vector, limit).await?
    } else {
        repo.search_edge_type_vectors(&query_vector, limit).await?
    };

    Ok(TypeMatchingResult {
        candidates: candidates
            .into_iter()
            .map(|candidate| TypeScoredCandidate {
                type_id: candidate.type_id,
                name: candidate.name,
                description: candidate.description,
                score: candidate.score,
            })
            .collect(),
    })
}
