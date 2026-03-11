use std::collections::{HashMap, HashSet};

use crate::domain::{PropertyValue, SchemaKind, TypeId, TypeInheritance, TypeProperty};

use super::type_hierarchy::is_assignable;

pub(crate) fn validate_internal_timestamps_not_provided(
    subject_id: &str,
    provided: &[PropertyValue],
    errors: &mut Vec<String>,
) {
    for prop in provided {
        if prop.key == "created_at" || prop.key == "updated_at" {
            errors.push(format!(
                "{} cannot set internal property '{}'",
                subject_id, prop.key
            ));
        }
    }
}

fn schema_kind_for_type_id(value: &str) -> Option<SchemaKind> {
    let id = TypeId::parse(value).ok()?;
    let raw = id.as_str();
    let prefix = raw.split('.').next().unwrap_or(raw);
    SchemaKind::from_db_str(prefix)
}

pub(crate) fn is_global_property_owner(owner_type_id: &str, property_owner_type_id: &str) -> bool {
    let Some(owner_kind) = schema_kind_for_type_id(owner_type_id) else {
        return false;
    };

    property_owner_type_id == owner_kind.as_db_str()
}

pub(crate) fn validate_graph_id(id: &str, kind: &str) -> std::result::Result<(), String> {
    match kind {
        "entity" => crate::domain::EntityId::parse(id).map(|_| ()),
        "universe" => crate::domain::UniverseId::parse(id).map(|_| ()),
        _ => {
            if id.trim().is_empty() {
                return Err(format!("{kind} id is required"));
            }
            if uuid::Uuid::parse_str(id).is_err() {
                return Err(format!("{kind} id '{}' must be a valid UUID", id));
            }
            Ok(())
        }
    }
}

pub(crate) fn validate_properties(
    subject_id: &str,
    owner_type_id: &str,
    provided: &[PropertyValue],
    all_properties: &[TypeProperty],
    inheritance: &[TypeInheritance],
    errors: &mut Vec<String>,
) {
    let allowed = collect_allowed_properties(owner_type_id, all_properties, inheritance);
    let required: HashSet<String> = all_properties
        .iter()
        .filter(|p| {
            p.required
                && (p.owner_type_id == owner_type_id
                    || is_assignable(owner_type_id, &p.owner_type_id, inheritance)
                    || is_global_property_owner(owner_type_id, &p.owner_type_id))
        })
        .map(|p| p.prop_name.clone())
        .collect();

    for property in provided {
        if !allowed.contains_key(&property.key) {
            errors.push(format!(
                "{} property '{}' is not allowed for {}",
                subject_id, property.key, owner_type_id
            ));
        }
    }

    for req in required {
        if req == "id" {
            continue;
        }
        if !provided.iter().any(|p| p.key == req) {
            errors.push(format!(
                "{} is missing required property '{}'",
                subject_id, req
            ));
        }
    }
}

fn collect_allowed_properties(
    owner_type_id: &str,
    all_properties: &[TypeProperty],
    inheritance: &[TypeInheritance],
) -> HashMap<String, String> {
    all_properties
        .iter()
        .filter(|prop| {
            prop.owner_type_id == owner_type_id
                || is_assignable(owner_type_id, &prop.owner_type_id, inheritance)
                || is_global_property_owner(owner_type_id, &prop.owner_type_id)
        })
        .map(|prop| (prop.prop_name.clone(), prop.value_type.clone()))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::PropertyScalar;

    #[test]
    fn validate_graph_id_checks_kind_specific_and_uuid_rules() {
        assert!(validate_graph_id("11111111-1111-1111-1111-111111111111", "entity").is_ok());
        assert!(validate_graph_id("", "block").is_err());
        assert!(validate_graph_id("not-a-uuid", "block").is_err());
    }

    #[test]
    fn validate_properties_reports_disallowed_and_missing_required() {
        let inheritance = vec![TypeInheritance {
            child_type_id: "node.person".to_string(),
            parent_type_id: "node.entity".to_string(),
            description: String::new(),
            active: true,
        }];
        let all_properties = vec![TypeProperty {
            owner_type_id: "node.entity".to_string(),
            prop_name: "name".to_string(),
            value_type: "string".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        }];

        let provided = vec![PropertyValue {
            key: "unknown".to_string(),
            value: PropertyScalar::String("x".to_string()),
        }];

        let mut errors = vec![];
        validate_properties(
            "entity.person",
            "node.person",
            &provided,
            &all_properties,
            &inheritance,
            &mut errors,
        );

        assert_eq!(errors.len(), 2);
    }
}
