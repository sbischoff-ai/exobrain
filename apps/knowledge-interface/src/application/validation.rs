use std::collections::{HashMap, HashSet};
use std::str::FromStr;

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
    let id = TypeId::from_str(value).ok()?;
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
        "entity" => crate::domain::EntityId::from_str(id)
            .map(|_| ())
            .map_err(|err| err.to_string()),
        "universe" => crate::domain::UniverseId::from_str(id)
            .map(|_| ())
            .map_err(|err| err.to_string()),
        _ => id.parse::<uuid::Uuid>().map(|_| ()).map_err(|_| {
            if id.trim().is_empty() {
                format!("{kind} id is required")
            } else {
                format!("{kind} id '{}' must be a valid UUID", id)
            }
        }),
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
        assert_eq!(
            validate_graph_id("", "block").expect_err("empty block id should fail"),
            "block id is required"
        );
        assert_eq!(
            validate_graph_id("not-a-uuid", "block").expect_err("invalid block id should fail"),
            "block id 'not-a-uuid' must be a valid UUID"
        );
    }

    #[test]
    fn validate_graph_id_maps_domain_errors() {
        assert_eq!(
            validate_graph_id("", "entity").expect_err("empty entity id should fail"),
            "entity id is required"
        );
        assert_eq!(
            validate_graph_id("bad", "universe").expect_err("invalid universe id should fail"),
            "universe id 'bad' must be a valid UUID"
        );
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
