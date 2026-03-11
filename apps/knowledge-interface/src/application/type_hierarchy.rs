use std::collections::HashSet;

use crate::domain::TypeInheritance;

pub(crate) fn resolve_labels_for_type(
    type_id: &str,
    inheritance: &[TypeInheritance],
) -> Vec<String> {
    let mut chain = vec![type_id.to_string()];
    let mut current = type_id.to_string();
    loop {
        let parent = inheritance
            .iter()
            .find(|edge| edge.child_type_id == current)
            .map(|edge| edge.parent_type_id.clone());
        match parent {
            Some(next) => {
                chain.push(next.clone());
                current = next;
            }
            None => break,
        }
    }

    chain
        .into_iter()
        .rev()
        .map(|id| id.trim_start_matches("node.").to_string())
        .map(|label| {
            let mut chars = label.chars();
            match chars.next() {
                Some(first) => format!(
                    "{}{}",
                    first.to_ascii_uppercase(),
                    chars.collect::<String>()
                ),
                None => label,
            }
        })
        .collect()
}

pub(crate) fn is_assignable(actual: &str, expected: &str, inheritance: &[TypeInheritance]) -> bool {
    if actual == expected {
        return true;
    }

    let mut stack = vec![actual.to_string()];
    let mut seen = HashSet::new();
    while let Some(current) = stack.pop() {
        if !seen.insert(current.clone()) {
            continue;
        }
        for parent in inheritance.iter().filter(|i| i.child_type_id == current) {
            if parent.parent_type_id == expected {
                return true;
            }
            stack.push(parent.parent_type_id.clone());
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolve_labels_builds_capitalized_hierarchy_order() {
        let inheritance = vec![
            TypeInheritance {
                child_type_id: "node.person".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.celebrity".to_string(),
                parent_type_id: "node.person".to_string(),
                description: String::new(),
                active: true,
            },
        ];

        assert_eq!(
            resolve_labels_for_type("node.celebrity", &inheritance),
            vec!["Entity", "Person", "Celebrity"]
        );
    }

    #[test]
    fn assignable_checks_transitive_parent_chain() {
        let inheritance = vec![
            TypeInheritance {
                child_type_id: "node.task".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.todo".to_string(),
                parent_type_id: "node.task".to_string(),
                description: String::new(),
                active: true,
            },
        ];

        assert!(is_assignable("node.todo", "node.entity", &inheritance));
        assert!(!is_assignable("node.entity", "node.todo", &inheritance));
    }
}
