use std::collections::HashMap;

use anyhow::{anyhow, Result};

use crate::domain::{
    EntityCandidate, FindEntityCandidatesQuery, FindEntityCandidatesResult, RawEntityCandidateData,
};

use crate::application::KnowledgeApplication;

const LEXICAL_WEIGHT: f64 = 0.55;
const SEMANTIC_WEIGHT: f64 = 0.45;

pub(crate) async fn find_entity_candidates(
    app: &KnowledgeApplication,
    mut query: FindEntityCandidatesQuery,
) -> Result<FindEntityCandidatesResult> {
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
        return Err(anyhow!("user_id is required"));
    }

    query.short_description = query
        .short_description
        .as_ref()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());

    if query.names.is_empty() && query.short_description.is_none() {
        return Err(anyhow!(
            "at least one name or short_description is required"
        ));
    }

    let description_vectors = match &query.short_description {
        Some(description) => {
            app.embedder
                .embed_texts(std::slice::from_ref(description))
                .await?
        }
        None => Vec::new(),
    };
    let query_vector = description_vectors.first().map(Vec::as_slice);

    let raw_candidates = app
        .graph_repository
        .find_entity_candidates(&query, query_vector)
        .await?;

    let mut candidates = compose_candidates(raw_candidates);
    candidates.sort_by(|a, b| {
        b.score
            .total_cmp(&a.score)
            .then_with(|| a.id.cmp(&b.id))
            .then_with(|| a.name.cmp(&b.name))
    });

    if let Some(limit) = query.limit {
        candidates.truncate(limit);
    }

    Ok(FindEntityCandidatesResult { candidates })
}

fn compose_candidates(raw: RawEntityCandidateData) -> Vec<EntityCandidate> {
    let mut by_id: HashMap<String, EntityCandidate> = HashMap::new();

    for lexical in raw.lexical_matches {
        by_id.insert(
            lexical.id.clone(),
            EntityCandidate {
                id: lexical.id,
                name: lexical.name,
                described_by_text: None,
                score: LEXICAL_WEIGHT * lexical.score,
                type_id: lexical.type_id,
                matched_tokens: lexical.matched_tokens,
            },
        );
    }

    for semantic in raw.semantic_hits {
        let entry = by_id
            .entry(semantic.entity_id.clone())
            .or_insert_with(|| EntityCandidate {
                id: semantic.entity_id,
                name: semantic.name,
                described_by_text: semantic.described_by_text.clone(),
                score: 0.0,
                type_id: semantic.type_id,
                matched_tokens: Vec::new(),
            });

        entry.score += SEMANTIC_WEIGHT * semantic.score;

        if entry.described_by_text.is_none() {
            entry.described_by_text = semantic.described_by_text;
        }
    }

    by_id.into_values().collect()
}
