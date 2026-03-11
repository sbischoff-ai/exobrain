use crate::domain::{ListEntitiesByTypeQuery, ListEntitiesByTypeResult};

use crate::application::errors::{AppResult, ApplicationError};
use crate::application::pagination::{PageCursor, PageSize};
use crate::application::KnowledgeApplication;

pub(crate) async fn list_entities_by_type(
    app: &KnowledgeApplication,
    mut query: ListEntitiesByTypeQuery,
) -> AppResult<ListEntitiesByTypeResult> {
    query.user_id = query.user_id.trim().to_string();
    if query.user_id.is_empty() {
        return Err(ApplicationError::validation("user_id is required"));
    }

    query.type_id = query.type_id.trim().to_string();
    if query.type_id.is_empty() {
        return Err(ApplicationError::validation("type_id is required"));
    }

    let page_size = PageSize::from_requested(query.page_size);
    let normalized_page_token = PageCursor::normalize_optional(query.page_token.as_deref());

    query.page_size = Some(page_size.get());
    query.page_token = normalized_page_token.clone();

    query.offset = Some(match query.offset {
        Some(offset) => offset,
        None => PageCursor::parse_optional(normalized_page_token.as_deref())
            .map_err(|_| {
                ApplicationError::validation("page_token must be a valid pagination cursor")
            })?
            .map(PageCursor::get)
            .unwrap_or_default(),
    });

    app.graph_repository
        .list_entities_by_type(&query)
        .await
        .map_err(Into::into)
}
