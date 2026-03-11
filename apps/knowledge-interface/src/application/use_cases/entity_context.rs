use crate::application::errors::{ApplicationError, ApplicationResult};

use crate::domain::{GetEntityContextQuery, GetEntityContextResult};

use crate::application::KnowledgeApplication;

pub(crate) async fn get_entity_context(
    app: &KnowledgeApplication,
    mut query: GetEntityContextQuery,
) -> ApplicationResult<GetEntityContextResult> {
    query.entity_id = query.entity_id.trim().to_string();
    if query.entity_id.is_empty() {
        return Err(ApplicationError::validation("entity_id is required"));
    }

    query.user_id = query.user_id.trim().to_string();
    if query.user_id.is_empty() {
        return Err(ApplicationError::validation("user_id is required"));
    }

    query.max_block_level = query.max_block_level.min(32);

    Ok(app.graph_repository.get_entity_context(&query).await?)
}
