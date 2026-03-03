use std::collections::{HashMap, HashSet};

use anyhow::{anyhow, Result};

use crate::domain::{GetEntityContextQuery, GetEntityContextResult};

use super::{
    KnowledgeApplication, BLOCK_CONTEXT_PROMOTED_FIELD_DENYLIST, CONTEXT_CORE_FIELD_DENYLIST,
    ENTITY_CONTEXT_PROMOTED_FIELD_DENYLIST,
};

pub(super) async fn get_entity_context(
    app: &KnowledgeApplication,
    mut query: GetEntityContextQuery,
) -> Result<GetEntityContextResult> {
    query.entity_id = query.entity_id.trim().to_string();
    if query.entity_id.is_empty() {
        return Err(anyhow!("entity_id is required"));
    }

    query.user_id = query.user_id.trim().to_string();
    if query.user_id.is_empty() {
        return Err(anyhow!("user_id is required"));
    }

    query.max_block_level = query.max_block_level.min(32);

    let mut result = app.graph_repository.get_entity_context(&query).await?;
    let property_allowlist = app
        .schema_repository
        .get_all_properties()
        .await?
        .into_iter()
        .filter(|property| property.active && property.readable)
        .fold(HashMap::new(), |mut allowlist, property| {
            allowlist
                .entry(property.owner_type_id)
                .or_insert_with(HashSet::new)
                .insert(property.prop_name);
            allowlist
        });

    let allowed_entity_properties = property_allowlist
        .get(&result.entity.type_id)
        .cloned()
        .unwrap_or_default();
    result.entity.properties.retain(|property| {
        allowed_entity_properties.contains(&property.key)
            && !CONTEXT_CORE_FIELD_DENYLIST.contains(&property.key.as_str())
            && !ENTITY_CONTEXT_PROMOTED_FIELD_DENYLIST.contains(&property.key.as_str())
    });

    for block in &mut result.blocks {
        let allowed_block_properties = property_allowlist
            .get(&block.type_id)
            .cloned()
            .unwrap_or_default();
        block.properties.retain(|property| {
            allowed_block_properties.contains(&property.key)
                && !CONTEXT_CORE_FIELD_DENYLIST.contains(&property.key.as_str())
                && !BLOCK_CONTEXT_PROMOTED_FIELD_DENYLIST.contains(&property.key.as_str())
        });
    }

    Ok(result)
}
