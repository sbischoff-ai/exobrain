use crate::application::errors::{ApplicationError, ApplicationResult};

use crate::domain::{ListEntitiesByTypeQuery, ListEntitiesByTypeResult};

use crate::application::pagination::{
    LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE, LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE,
};
use crate::application::KnowledgeApplication;

pub(crate) async fn list_entities_by_type(
    app: &KnowledgeApplication,
    mut query: ListEntitiesByTypeQuery,
) -> ApplicationResult<ListEntitiesByTypeResult> {
    query.user_id = query.user_id.trim().to_string();
    if query.user_id.is_empty() {
        return Err(ApplicationError::validation("user_id is required"));
    }

    query.type_id = query.type_id.trim().to_string();
    if query.type_id.is_empty() {
        return Err(ApplicationError::validation("type_id is required"));
    }

    query.page_size = Some(
        query
            .page_size
            .unwrap_or(LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE)
            .clamp(1, LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE),
    );

    query.page_token = query
        .page_token
        .as_ref()
        .map(|token| token.trim().to_string())
        .filter(|token| !token.is_empty());

    query.offset = Some(match query.offset {
        Some(offset) => offset,
        None => query
            .page_token
            .as_deref()
            .map(|token| {
                token.parse::<u64>().map_err(|_| {
                    ApplicationError::validation("page_token must be a valid pagination cursor")
                })
            })
            .transpose()?
            .unwrap_or_default(),
    });

    Ok(app.graph_repository.list_entities_by_type(&query).await?)
}
