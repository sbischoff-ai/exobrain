use crate::application::errors::{ApplicationError, ApplicationResult};

use crate::domain::{FindEntityCandidatesQuery, FindEntityCandidatesResult};

use crate::application::KnowledgeApplication;

pub(crate) async fn find_entity_candidates(
    app: &KnowledgeApplication,
    mut query: FindEntityCandidatesQuery,
) -> ApplicationResult<FindEntityCandidatesResult> {
    query.names = query
        .names
        .iter()
        .map(|name| name.trim().to_lowercase())
        .filter(|name| !name.is_empty())
        .collect();

    query.potential_type_ids = query
        .potential_type_ids
        .iter()
        .map(|type_id| type_id.trim().to_string())
        .filter(|type_id| !type_id.is_empty())
        .collect();

    query.user_id = query.user_id.trim().to_string();
    if query.user_id.is_empty() {
        return Err(ApplicationError::validation("user_id is required"));
    }

    query.short_description = query
        .short_description
        .as_ref()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());

    if query.names.is_empty() && query.short_description.is_none() {
        return Err(ApplicationError::validation(
            "at least one name or short_description is required",
        ));
    }

    let description_vectors = match &query.short_description {
        Some(description) => app.embedder.embed_texts(&[description.clone()]).await?,
        None => Vec::new(),
    };
    let query_vector = description_vectors.first().map(Vec::as_slice);

    let mut candidates = app
        .graph_repository
        .find_entity_candidates(&query, query_vector)
        .await?;

    candidates.sort_by(|a, b| b.score.total_cmp(&a.score));

    if let Some(limit) = query.limit {
        candidates.truncate(limit);
    }

    Ok(FindEntityCandidatesResult { candidates })
}
