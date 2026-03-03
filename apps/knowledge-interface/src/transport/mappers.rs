use std::collections::HashMap;

use tonic::Status;

use crate::domain::{
    BlockNode, EdgeEndpointRule, EntityCandidate, EntityNode, FindEntityCandidatesQuery,
    GetEntityContextQuery, GetEntityContextResult, GraphEdge, ListEntitiesByTypeQuery,
    ListEntitiesByTypeResult, NeighborDirection, PropertyScalar, PropertyValue, SchemaKind,
    SchemaType, TypeInheritance, TypeProperty, TypedEntityListItem, UniverseNode, Visibility,
};

use super::proto;

pub(crate) fn to_proto_schema_type(schema_type: SchemaType) -> proto::SchemaType {
    let kind = schema_type
        .schema_kind()
        .map(SchemaKind::as_proto_str)
        .unwrap_or(schema_type.kind.as_str())
        .to_string();

    proto::SchemaType {
        id: schema_type.id,
        kind,
        name: schema_type.name,
        description: schema_type.description,
        active: schema_type.active,
    }
}

pub(crate) fn to_proto_type_property(property: TypeProperty) -> proto::TypeProperty {
    proto::TypeProperty {
        owner_type_id: property.owner_type_id,
        prop_name: property.prop_name,
        value_type: property.value_type,
        required: property.required,
        readable: property.readable,
        writable: property.writable,
        active: property.active,
        description: property.description,
    }
}

pub(crate) fn to_proto_type_inheritance(inheritance: TypeInheritance) -> proto::TypeInheritance {
    proto::TypeInheritance {
        child_type_id: inheritance.child_type_id,
        parent_type_id: inheritance.parent_type_id,
        description: inheritance.description,
        active: inheritance.active,
    }
}

pub(crate) fn to_proto_edge_endpoint_rule(rule: EdgeEndpointRule) -> proto::EdgeEndpointRule {
    proto::EdgeEndpointRule {
        edge_type_id: rule.edge_type_id,
        from_node_type_id: rule.from_node_type_id,
        to_node_type_id: rule.to_node_type_id,
        active: rule.active,
        description: rule.description,
    }
}

pub(crate) fn to_domain_universe_node(
    universe: proto::UniverseNode,
) -> Result<UniverseNode, Status> {
    Ok(UniverseNode {
        id: universe.id,
        name: universe.name,
        user_id: universe.user_id,
        visibility: map_visibility(universe.visibility)?,
    })
}

pub(crate) fn to_domain_entity_node(entity: proto::EntityNode) -> Result<EntityNode, Status> {
    Ok(EntityNode {
        id: entity.id,
        type_id: entity.type_id,
        universe_id: entity.universe_id,
        user_id: entity.user_id,
        visibility: map_visibility(entity.visibility)?,
        properties: entity
            .properties
            .into_iter()
            .map(to_domain_property_value)
            .collect::<Result<Vec<_>, _>>()?,
        resolved_labels: vec![],
    })
}

pub(crate) fn to_domain_block_node(block: proto::BlockNode) -> Result<BlockNode, Status> {
    Ok(BlockNode {
        id: block.id,
        type_id: block.type_id,
        user_id: block.user_id,
        visibility: map_visibility(block.visibility)?,
        properties: block
            .properties
            .into_iter()
            .map(to_domain_property_value)
            .collect::<Result<Vec<_>, _>>()?,
        resolved_labels: vec![],
    })
}

pub(crate) fn to_domain_graph_edge(edge: proto::GraphEdge) -> Result<GraphEdge, Status> {
    Ok(GraphEdge {
        from_id: edge.from_id,
        to_id: edge.to_id,
        edge_type: edge.edge_type,
        user_id: edge.user_id,
        visibility: map_visibility(edge.visibility)?,
        properties: edge
            .properties
            .into_iter()
            .map(to_domain_property_value)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

pub(crate) fn to_domain_find_entity_candidates_query(
    request: proto::FindEntityCandidatesRequest,
) -> FindEntityCandidatesQuery {
    FindEntityCandidatesQuery {
        names: request.names,
        potential_type_ids: request.potential_type_ids,
        short_description: (!request.short_description.trim().is_empty())
            .then_some(request.short_description),
        user_id: request.user_id,
        limit: request.limit.map(|value| value as usize),
    }
}

pub(crate) fn to_proto_entity_candidate(candidate: EntityCandidate) -> proto::EntityCandidate {
    proto::EntityCandidate {
        entity_id: candidate.id,
        entity_name: candidate.name,
        described_by_text: candidate.described_by_text.unwrap_or_default(),
        score: candidate.score,
        matched_name: candidate
            .matched_tokens
            .first()
            .cloned()
            .unwrap_or_default(),
        matched_alias: candidate.matched_tokens.get(1).cloned().unwrap_or_default(),
        entity_type_id: candidate.type_id,
    }
}

pub(crate) fn to_domain_get_entity_context_query(
    request: proto::GetEntityContextRequest,
) -> GetEntityContextQuery {
    GetEntityContextQuery {
        entity_id: request.entity_id,
        user_id: request.user_id,
        max_block_level: request.max_block_level,
    }
}

pub(crate) fn to_domain_list_entities_by_type_query(
    request: proto::ListEntitiesByTypeRequest,
) -> ListEntitiesByTypeQuery {
    ListEntitiesByTypeQuery {
        user_id: request.user_id,
        type_id: request.type_id,
        page_size: request.page_size,
        page_token: request.page_token,
        offset: None,
    }
}

pub(crate) fn to_proto_list_entities_by_type_item(
    item: TypedEntityListItem,
) -> proto::ListEntitiesByTypeItem {
    proto::ListEntitiesByTypeItem {
        id: item.id,
        name: item.name.unwrap_or_default(),
        updated_at: item.updated_at,
        description: item.description,
        score: None,
    }
}

pub(crate) fn to_proto_list_entities_by_type_reply(
    result: ListEntitiesByTypeResult,
) -> proto::ListEntitiesByTypeReply {
    let total_count =
        (result.offset.saturating_add(result.entities.len() as u64)).min(u64::from(u32::MAX));

    proto::ListEntitiesByTypeReply {
        entities: result
            .entities
            .into_iter()
            .map(to_proto_list_entities_by_type_item)
            .collect(),
        next_page_token: result.next_page_token,
        total_count: Some(total_count as u32),
    }
}

pub(crate) fn to_proto_get_entity_context_reply(
    result: GetEntityContextResult,
) -> proto::GetEntityContextReply {
    proto::GetEntityContextReply {
        entity: Some(proto::EntityContextCore {
            id: result.entity.id,
            type_id: result.entity.type_id,
            user_id: result.entity.user_id,
            visibility: to_proto_visibility(result.entity.visibility) as i32,
            name: result.entity.name,
            aliases: result.entity.aliases,
            created_at: result.entity.created_at,
            updated_at: result.entity.updated_at,
        }),
        entity_properties: to_proto_flat_property_map(result.entity.properties),
        blocks: result
            .blocks
            .into_iter()
            .map(|block| proto::EntityContextBlock {
                id: block.id,
                type_id: block.type_id,
                block_level: block.block_level,
                properties: to_proto_flat_property_map(block.properties),
                parent_block_id: block.parent_block_id,
                text: block.text,
                created_at: block.created_at,
                updated_at: block.updated_at,
                neighbors: block
                    .neighbors
                    .into_iter()
                    .map(to_proto_entity_context_neighbor)
                    .collect(),
            })
            .collect(),
        neighbors: result
            .neighbors
            .into_iter()
            .map(to_proto_entity_context_neighbor)
            .collect(),
    }
}

fn to_proto_entity_context_neighbor(
    neighbor: crate::domain::EntityContextNeighborItem,
) -> proto::EntityContextNeighbor {
    proto::EntityContextNeighbor {
        direction: to_proto_neighbor_direction(neighbor.direction) as i32,
        edge_type: neighbor.edge_type,
        edge_properties: to_proto_property_scalar_map(neighbor.edge_properties),
        other_entity: Some(proto::EntityContextOtherEntity {
            id: neighbor.other_entity.id,
            description: neighbor.other_entity.description,
        }),
    }
}

fn to_proto_flat_property_map(values: Vec<PropertyValue>) -> HashMap<String, String> {
    values
        .into_iter()
        .map(|value| {
            let PropertyValue { key, value } = value;
            (key, to_proto_json_scalar_string(value))
        })
        .collect()
}

fn to_proto_json_scalar_string(value: PropertyScalar) -> String {
    match value {
        PropertyScalar::String(v) => v,
        PropertyScalar::Float(v) => v.to_string(),
        PropertyScalar::Int(v) => v.to_string(),
        PropertyScalar::Bool(v) => v.to_string(),
        PropertyScalar::Datetime(v) => v,
        PropertyScalar::Json(v) => v,
    }
}

fn to_proto_property_scalar_map(
    values: Vec<PropertyValue>,
) -> HashMap<String, proto::PropertyScalarValue> {
    values
        .into_iter()
        .map(|value| {
            let PropertyValue { key, value } = value;
            (key, to_proto_property_scalar_value(value))
        })
        .collect()
}

fn to_proto_property_scalar_value(value: PropertyScalar) -> proto::PropertyScalarValue {
    let value = match value {
        PropertyScalar::String(v) => proto::property_scalar_value::Value::StringValue(v),
        PropertyScalar::Float(v) => proto::property_scalar_value::Value::FloatValue(v),
        PropertyScalar::Int(v) => proto::property_scalar_value::Value::IntValue(v),
        PropertyScalar::Bool(v) => proto::property_scalar_value::Value::BoolValue(v),
        PropertyScalar::Datetime(v) => proto::property_scalar_value::Value::DatetimeValue(v),
        PropertyScalar::Json(v) => proto::property_scalar_value::Value::JsonValue(v),
    };

    proto::PropertyScalarValue { value: Some(value) }
}

#[cfg(test)]
pub(crate) fn to_proto_property_value(value: PropertyValue) -> proto::PropertyValue {
    let PropertyValue { key, value } = value;

    let value = match value {
        PropertyScalar::String(v) => proto::property_value::Value::StringValue(v),
        PropertyScalar::Float(v) => proto::property_value::Value::FloatValue(v),
        PropertyScalar::Int(v) => proto::property_value::Value::IntValue(v),
        PropertyScalar::Bool(v) => proto::property_value::Value::BoolValue(v),
        PropertyScalar::Datetime(v) => proto::property_value::Value::DatetimeValue(v),
        PropertyScalar::Json(v) => proto::property_value::Value::JsonValue(v),
    };

    proto::PropertyValue {
        key,
        value: Some(value),
    }
}

pub(crate) fn to_domain_property_value(
    value: proto::PropertyValue,
) -> Result<PropertyValue, Status> {
    let scalar = match value
        .value
        .ok_or_else(|| Status::invalid_argument("property value is required"))?
    {
        proto::property_value::Value::StringValue(v) => PropertyScalar::String(v),
        proto::property_value::Value::FloatValue(v) => PropertyScalar::Float(v),
        proto::property_value::Value::IntValue(v) => PropertyScalar::Int(v),
        proto::property_value::Value::BoolValue(v) => PropertyScalar::Bool(v),
        proto::property_value::Value::DatetimeValue(v) => PropertyScalar::Datetime(v),
        proto::property_value::Value::JsonValue(v) => PropertyScalar::Json(v),
    };

    Ok(PropertyValue {
        key: value.key,
        value: scalar,
    })
}

pub(crate) fn map_visibility(value: i32) -> Result<Visibility, Status> {
    let visibility = proto::Visibility::try_from(value)
        .map_err(|_| Status::invalid_argument("visibility is invalid"))?;

    match visibility {
        proto::Visibility::Private => Ok(Visibility::Private),
        proto::Visibility::Shared => Ok(Visibility::Shared),
        proto::Visibility::Unspecified => Err(Status::invalid_argument("visibility is required")),
    }
}

fn to_proto_visibility(value: Visibility) -> proto::Visibility {
    match value {
        Visibility::Private => proto::Visibility::Private,
        Visibility::Shared => proto::Visibility::Shared,
    }
}

fn to_proto_neighbor_direction(value: NeighborDirection) -> proto::NeighborDirection {
    match value {
        NeighborDirection::Outgoing => proto::NeighborDirection::Outgoing,
        NeighborDirection::Incoming => proto::NeighborDirection::Incoming,
    }
}

#[cfg(test)]
mod tests {
    use tonic::Code;

    use super::{
        map_visibility, to_domain_find_entity_candidates_query, to_domain_get_entity_context_query,
        to_domain_list_entities_by_type_query, to_domain_property_value, to_proto_entity_candidate,
        to_proto_get_entity_context_reply, to_proto_list_entities_by_type_reply,
        to_proto_property_value,
    };
    use crate::domain::{
        EntityCandidate, EntityContextBlockItem, EntityContextEntitySnapshot,
        EntityContextNeighborItem, EntityContextOtherEntity, GetEntityContextResult,
        ListEntitiesByTypeResult, NeighborDirection, PropertyScalar, PropertyValue,
        TypedEntityListItem, Visibility,
    };
    use crate::transport::proto;

    #[test]
    fn to_domain_property_value_rejects_missing_value() {
        let result = to_domain_property_value(proto::PropertyValue {
            key: "name".to_string(),
            value: None,
        });

        let error = result.expect_err("expected missing value to fail");
        assert_eq!(error.code(), Code::InvalidArgument);
        assert_eq!(error.message(), "property value is required");
    }

    #[test]
    fn map_visibility_rejects_invalid_enum_value() {
        let result = map_visibility(99);

        let error = result.expect_err("expected invalid visibility enum to fail");
        assert_eq!(error.code(), Code::InvalidArgument);
        assert_eq!(error.message(), "visibility is invalid");
    }

    #[test]
    fn to_domain_find_entity_candidates_query_maps_empty_description_to_none() {
        let query = to_domain_find_entity_candidates_query(proto::FindEntityCandidatesRequest {
            names: vec!["Ada".to_string()],
            potential_type_ids: vec!["node.person".to_string()],
            short_description: "   ".to_string(),
            user_id: "u-1".to_string(),
            limit: Some(7),
        });

        assert_eq!(query.names, vec!["Ada".to_string()]);
        assert_eq!(query.short_description, None);
        assert_eq!(query.limit, Some(7));
    }

    #[test]
    fn to_proto_entity_candidate_maps_optional_fields_and_tokens() {
        let proto = to_proto_entity_candidate(EntityCandidate {
            id: "e-1".to_string(),
            name: "Ada Lovelace".to_string(),
            described_by_text: None,
            score: 0.97,
            type_id: "node.person".to_string(),
            matched_tokens: vec!["ada".to_string()],
        });

        assert_eq!(proto.entity_id, "e-1");
        assert!(proto.described_by_text.is_empty());
        assert_eq!(proto.matched_name, "ada");
        assert!(proto.matched_alias.is_empty());
    }

    #[test]
    fn to_domain_get_entity_context_query_maps_request_fields() {
        let query = to_domain_get_entity_context_query(proto::GetEntityContextRequest {
            entity_id: "entity-1".to_string(),
            user_id: "user-1".to_string(),
            max_block_level: 5,
        });

        assert_eq!(query.entity_id, "entity-1");
        assert_eq!(query.user_id, "user-1");
        assert_eq!(query.max_block_level, 5);
    }

    #[test]
    fn to_proto_property_value_maps_all_scalars() {
        let value = to_proto_property_value(PropertyValue {
            key: "weight".to_string(),
            value: PropertyScalar::Float(42.5),
        });

        assert_eq!(value.key, "weight");
        assert!(matches!(
            value.value,
            Some(proto::property_value::Value::FloatValue(v)) if v == 42.5
        ));
    }

    #[test]
    fn to_proto_property_value_maps_datetime_to_datetime_value() {
        let value = to_proto_property_value(PropertyValue {
            key: "updated_at".to_string(),
            value: PropertyScalar::Datetime(
                "2026-03-03T15:56:25.155889+00:00[Etc/UTC]".to_string(),
            ),
        });

        assert_eq!(value.key, "updated_at");
        assert!(matches!(
            value.value,
            Some(proto::property_value::Value::DatetimeValue(v))
                if v == "2026-03-03T15:56:25.155889+00:00[Etc/UTC]"
        ));
    }

    #[test]
    fn to_proto_get_entity_context_reply_maps_optional_fields_and_directions() {
        let reply = to_proto_get_entity_context_reply(GetEntityContextResult {
            entity: EntityContextEntitySnapshot {
                id: "e-1".to_string(),
                type_id: "node.person".to_string(),
                user_id: "u-1".to_string(),
                visibility: Visibility::Shared,
                name: Some("Ada".to_string()),
                aliases: vec!["Augusta Ada King".to_string()],
                created_at: Some("2026-01-01T00:00:00Z".to_string()),
                updated_at: Some("2026-01-01T00:00:01Z".to_string()),
                properties: vec![PropertyValue {
                    key: "age".to_string(),
                    value: PropertyScalar::Int(36),
                }],
            },
            blocks: vec![EntityContextBlockItem {
                id: "b-1".to_string(),
                type_id: "block.note".to_string(),
                block_level: 0,
                text: Some("Root summary".to_string()),
                created_at: Some("2026-01-01T00:00:02Z".to_string()),
                updated_at: Some("2026-01-01T00:00:03Z".to_string()),
                properties: vec![PropertyValue {
                    key: "source".to_string(),
                    value: PropertyScalar::String("import".to_string()),
                }],
                parent_block_id: None,
                neighbors: vec![],
            }],
            neighbors: vec![
                EntityContextNeighborItem {
                    direction: NeighborDirection::Outgoing,
                    edge_type: "RELATED_TO".to_string(),
                    edge_properties: vec![PropertyValue {
                        key: "confidence".to_string(),
                        value: PropertyScalar::Float(0.9),
                    }],
                    other_entity: EntityContextOtherEntity {
                        id: "e-2".to_string(),
                        description: Some("Mathematician".to_string()),
                    },
                },
                EntityContextNeighborItem {
                    direction: NeighborDirection::Incoming,
                    edge_type: "MENTIONS".to_string(),
                    edge_properties: vec![],
                    other_entity: EntityContextOtherEntity {
                        id: "e-3".to_string(),
                        description: None,
                    },
                },
            ],
        });

        let entity = reply.entity.expect("entity should be present");
        assert_eq!(entity.id, "e-1");
        assert_eq!(entity.visibility, proto::Visibility::Shared as i32);
        assert_eq!(entity.name.as_deref(), Some("Ada"));
        assert_eq!(reply.blocks[0].parent_block_id, None);
        assert_eq!(reply.blocks[0].text.as_deref(), Some("Root summary"));
        assert_eq!(reply.entity_properties.get("age"), Some(&"36".to_string()));
        assert_eq!(
            reply.blocks[0].properties.get("source"),
            Some(&"import".to_string())
        );
        assert!(matches!(
            reply.neighbors[0]
                .edge_properties
                .get("confidence")
                .and_then(|value| value.value.as_ref()),
            Some(proto::property_scalar_value::Value::FloatValue(v))
                if (*v - 0.9).abs() < f64::EPSILON
        ));
        assert_eq!(
            reply.neighbors[0]
                .other_entity
                .as_ref()
                .map(|e| e.id.as_str()),
            Some("e-2")
        );
        assert_eq!(
            reply.neighbors[0].direction,
            proto::NeighborDirection::Outgoing as i32
        );
        assert_eq!(
            reply.neighbors[1].direction,
            proto::NeighborDirection::Incoming as i32
        );
    }

    #[test]
    fn to_domain_list_entities_by_type_query_maps_pagination_fields() {
        let query = to_domain_list_entities_by_type_query(proto::ListEntitiesByTypeRequest {
            user_id: "user-1".to_string(),
            type_id: "node.person".to_string(),
            page_size: Some(30),
            page_token: Some("token-1".to_string()),
        });

        assert_eq!(query.user_id, "user-1");
        assert_eq!(query.type_id, "node.person");
        assert_eq!(query.page_size, Some(30));
        assert_eq!(query.page_token.as_deref(), Some("token-1"));
        assert_eq!(query.offset, None);
    }

    #[test]
    fn to_proto_list_entities_by_type_reply_maps_optional_fields_and_metadata() {
        let reply = to_proto_list_entities_by_type_reply(ListEntitiesByTypeResult {
            entities: vec![
                TypedEntityListItem {
                    id: "e-1".to_string(),
                    name: Some("Ada".to_string()),
                    updated_at: Some("2026-01-01T00:00:00Z".to_string()),
                    description: Some("Mathematician".to_string()),
                },
                TypedEntityListItem {
                    id: "e-2".to_string(),
                    name: None,
                    updated_at: None,
                    description: None,
                },
            ],
            page_size: 25,
            offset: 10,
            next_page_token: Some("next-25".to_string()),
        });

        assert_eq!(reply.entities.len(), 2);
        assert_eq!(reply.entities[0].id, "e-1");
        assert_eq!(reply.entities[0].name, "Ada");
        assert_eq!(reply.entities[1].name, "");
        assert_eq!(reply.entities[1].updated_at, None);
        assert_eq!(reply.entities[1].description, None);
        assert_eq!(reply.next_page_token.as_deref(), Some("next-25"));
        assert_eq!(reply.total_count, Some(12));
    }
}
