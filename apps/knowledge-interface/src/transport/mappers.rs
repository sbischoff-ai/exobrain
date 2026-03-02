use tonic::Status;

use crate::domain::{
    BlockNode, EdgeEndpointRule, EntityCandidate, EntityNode, FindEntityCandidatesQuery,
    GetEntityContextQuery, GetEntityContextResult, GraphEdge, NeighborDirection, PropertyScalar,
    PropertyValue, SchemaType, TypeInheritance, TypeProperty, UniverseNode, Visibility,
};

use super::proto;

pub(crate) fn to_proto_schema_type(schema_type: SchemaType) -> proto::SchemaType {
    proto::SchemaType {
        id: schema_type.id,
        kind: schema_type.kind,
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

pub(crate) fn to_proto_get_entity_context_reply(
    result: GetEntityContextResult,
) -> proto::GetEntityContextReply {
    proto::GetEntityContextReply {
        entity: Some(proto::EntityContextCore {
            id: result.entity.id,
            type_id: result.entity.type_id,
            user_id: result.entity.user_id,
            visibility: to_proto_visibility(result.entity.visibility) as i32,
        }),
        entity_properties: result
            .entity
            .properties
            .into_iter()
            .map(to_proto_property_value)
            .collect(),
        blocks: result
            .blocks
            .into_iter()
            .map(|block| proto::EntityContextBlock {
                id: block.id,
                type_id: block.type_id,
                block_level: block.block_level,
                properties: block
                    .properties
                    .into_iter()
                    .map(to_proto_property_value)
                    .collect(),
                parent_block_id: block.parent_block_id,
                parent_entity_id: block.parent_entity_id,
            })
            .collect(),
        neighbors: result
            .neighbors
            .into_iter()
            .map(|neighbor| proto::EntityContextNeighbor {
                direction: to_proto_neighbor_direction(neighbor.direction) as i32,
                edge_type: neighbor.edge_type,
                edge_properties: neighbor
                    .edge_properties
                    .into_iter()
                    .map(to_proto_property_value)
                    .collect(),
                other_entity_id: neighbor.other_entity_id,
            })
            .collect(),
    }
}

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
        to_domain_property_value, to_proto_entity_candidate, to_proto_get_entity_context_reply,
        to_proto_property_value,
    };
    use crate::domain::{
        EntityCandidate, EntityContextBlockItem, EntityContextEntitySnapshot,
        EntityContextNeighborItem, GetEntityContextResult, NeighborDirection, PropertyScalar,
        PropertyValue, Visibility,
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
    fn to_domain_get_entity_context_query_preserves_empty_fields() {
        let query = to_domain_get_entity_context_query(proto::GetEntityContextRequest {
            entity_id: "".to_string(),
            user_id: "".to_string(),
            max_block_level: 5,
        });

        assert!(query.entity_id.is_empty());
        assert!(query.user_id.is_empty());
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
    fn to_proto_get_entity_context_reply_maps_optional_fields_and_directions() {
        let reply = to_proto_get_entity_context_reply(GetEntityContextResult {
            entity: EntityContextEntitySnapshot {
                id: "e-1".to_string(),
                type_id: "node.person".to_string(),
                user_id: "u-1".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Ada".to_string()),
                }],
            },
            blocks: vec![EntityContextBlockItem {
                id: "b-1".to_string(),
                type_id: "block.note".to_string(),
                block_level: 0,
                properties: vec![],
                parent_block_id: None,
                parent_entity_id: Some("e-1".to_string()),
            }],
            neighbors: vec![
                EntityContextNeighborItem {
                    direction: NeighborDirection::Outgoing,
                    edge_type: "DESCRIBED_BY".to_string(),
                    edge_properties: vec![],
                    other_entity_id: "e-2".to_string(),
                },
                EntityContextNeighborItem {
                    direction: NeighborDirection::Incoming,
                    edge_type: "MENTIONS".to_string(),
                    edge_properties: vec![],
                    other_entity_id: "e-3".to_string(),
                },
            ],
        });

        let entity = reply.entity.expect("entity should be present");
        assert_eq!(entity.id, "e-1");
        assert_eq!(entity.visibility, proto::Visibility::Shared as i32);
        assert_eq!(reply.blocks[0].parent_block_id, None);
        assert_eq!(reply.blocks[0].parent_entity_id.as_deref(), Some("e-1"));
        assert_eq!(
            reply.neighbors[0].direction,
            proto::NeighborDirection::Outgoing as i32
        );
        assert_eq!(
            reply.neighbors[1].direction,
            proto::NeighborDirection::Incoming as i32
        );
    }
}
