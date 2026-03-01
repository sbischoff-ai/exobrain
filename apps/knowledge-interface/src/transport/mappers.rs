use tonic::Status;

use crate::domain::{
    BlockNode, EntityNode, GraphEdge, PropertyScalar, PropertyValue, UniverseNode, Visibility,
};

use super::proto;

pub fn map_universe(universe: proto::UniverseNode) -> Result<UniverseNode, Status> {
    Ok(UniverseNode {
        id: universe.id,
        name: universe.name,
        user_id: universe.user_id,
        visibility: map_visibility(universe.visibility)?,
    })
}

pub fn map_entity(entity: proto::EntityNode) -> Result<EntityNode, Status> {
    Ok(EntityNode {
        id: entity.id,
        type_id: entity.type_id,
        universe_id: entity.universe_id,
        user_id: entity.user_id,
        visibility: map_visibility(entity.visibility)?,
        properties: entity
            .properties
            .into_iter()
            .map(map_property_value)
            .collect::<Result<Vec<_>, _>>()?,
        resolved_labels: vec![],
    })
}

pub fn map_block(block: proto::BlockNode) -> Result<BlockNode, Status> {
    Ok(BlockNode {
        id: block.id,
        type_id: block.type_id,
        user_id: block.user_id,
        visibility: map_visibility(block.visibility)?,
        properties: block
            .properties
            .into_iter()
            .map(map_property_value)
            .collect::<Result<Vec<_>, _>>()?,
        resolved_labels: vec![],
    })
}

pub fn map_edge(edge: proto::GraphEdge) -> Result<GraphEdge, Status> {
    Ok(GraphEdge {
        from_id: edge.from_id,
        to_id: edge.to_id,
        edge_type: edge.edge_type,
        user_id: edge.user_id,
        visibility: map_visibility(edge.visibility)?,
        properties: edge
            .properties
            .into_iter()
            .map(map_property_value)
            .collect::<Result<Vec<_>, _>>()?,
    })
}

pub fn map_property_value(value: proto::PropertyValue) -> Result<PropertyValue, Status> {
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

pub fn map_visibility(value: i32) -> Result<Visibility, Status> {
    let visibility = proto::Visibility::try_from(value)
        .map_err(|_| Status::invalid_argument("visibility is invalid"))?;

    match visibility {
        proto::Visibility::Private => Ok(Visibility::Private),
        proto::Visibility::Shared => Ok(Visibility::Shared),
        proto::Visibility::Unspecified => Err(Status::invalid_argument("visibility is required")),
    }
}
