use tonic::Status;

use crate::domain::{
    BlockNode, EdgeEndpointRule, EntityCandidate, EntityNode, FindEntityCandidatesQuery, GraphEdge,
    PropertyScalar, PropertyValue, SchemaType, TypeInheritance, TypeProperty, UniverseNode,
    Visibility,
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

#[cfg(test)]
mod tests {
    use tonic::Code;

    use super::{
        map_visibility, to_domain_find_entity_candidates_query, to_domain_property_value,
        to_proto_entity_candidate,
    };
    use crate::domain::EntityCandidate;
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
}
