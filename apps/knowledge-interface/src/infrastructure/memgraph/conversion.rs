use anyhow::Result;
use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, NaiveTime};
use neo4rs::{BoltMap, BoltType};

use crate::domain::{PropertyScalar, PropertyValue};

pub(crate) fn bolt_map_remove_aliases(map: &mut BoltMap, key: &str) -> Vec<String> {
    let Some(value) = map.value.remove(key) else {
        return Vec::new();
    };

    match value {
        BoltType::List(list) => list
            .value
            .into_iter()
            .filter_map(|entry| match entry {
                BoltType::String(v) => Some(v.value),
                _ => None,
            })
            .collect(),
        BoltType::String(v) => {
            let raw = v.value.trim().to_string();
            if raw.starts_with('[') && raw.ends_with(']') {
                let parsed: Vec<String> = raw[1..raw.len() - 1]
                    .split(',')
                    .map(|item| item.trim().trim_matches('"').to_string())
                    .filter(|item| !item.is_empty())
                    .collect();
                if !parsed.is_empty() {
                    return parsed;
                }
            }
            if raw.is_empty() {
                Vec::new()
            } else {
                vec![raw]
            }
        }
        _ => Vec::new(),
    }
}

pub(crate) fn bolt_map_to_property_values(map: BoltMap) -> Vec<PropertyValue> {
    let mut properties: Vec<PropertyValue> = map
        .value
        .into_iter()
        .map(|(key, value)| PropertyValue {
            key: key.value,
            value: bolt_type_to_property_scalar(value),
        })
        .collect();
    properties.sort_by(|a, b| a.key.cmp(&b.key));
    properties
}

pub(crate) fn bolt_type_to_property_scalar(value: BoltType) -> PropertyScalar {
    match value {
        BoltType::String(v) => PropertyScalar::String(v.value),
        BoltType::Boolean(v) => PropertyScalar::Bool(v.value),
        BoltType::Integer(v) => PropertyScalar::Int(v.value),
        BoltType::Float(v) => PropertyScalar::Float(v.value),
        BoltType::Date(v) => temporal_scalar_from_date(v),
        BoltType::Time(v) => temporal_scalar_from_time(v),
        BoltType::LocalTime(v) => temporal_scalar_from_local_time(v),
        BoltType::DateTime(v) => temporal_scalar_from_datetime(v),
        BoltType::LocalDateTime(v) => temporal_scalar_from_local_datetime(v),
        BoltType::DateTimeZoneId(v) => temporal_scalar_from_datetime_zone_id(v),
        other => PropertyScalar::Json(format!("{other:?}")),
    }
}

fn temporal_scalar_from_date(value: neo4rs::BoltDate) -> PropertyScalar {
    let date: Result<NaiveDate, _> = (&value).try_into();
    match date {
        Ok(v) => PropertyScalar::Datetime(v.to_string()),
        Err(_) => PropertyScalar::Json(format!("{:?}", BoltType::Date(value))),
    }
}

fn temporal_scalar_from_time(value: neo4rs::BoltTime) -> PropertyScalar {
    let (time, offset): (NaiveTime, FixedOffset) = (&value).into();
    let value = format!("{}{}", time.format("%H:%M:%S%.f"), offset);
    PropertyScalar::Datetime(value)
}

fn temporal_scalar_from_local_time(value: neo4rs::BoltLocalTime) -> PropertyScalar {
    let time: NaiveTime = (&value).into();
    PropertyScalar::Datetime(time.format("%H:%M:%S%.f").to_string())
}

fn temporal_scalar_from_datetime(value: neo4rs::BoltDateTime) -> PropertyScalar {
    let datetime: Result<DateTime<FixedOffset>, _> = (&value).try_into();
    match datetime {
        Ok(v) => PropertyScalar::Datetime(v.to_rfc3339()),
        Err(_) => PropertyScalar::Json(format!("{:?}", BoltType::DateTime(value))),
    }
}

fn temporal_scalar_from_local_datetime(value: neo4rs::BoltLocalDateTime) -> PropertyScalar {
    let datetime: Result<NaiveDateTime, _> = (&value).try_into();
    match datetime {
        Ok(v) => PropertyScalar::Datetime(v.format("%Y-%m-%dT%H:%M:%S%.f").to_string()),
        Err(_) => PropertyScalar::Json(format!("{:?}", BoltType::LocalDateTime(value))),
    }
}

fn temporal_scalar_from_datetime_zone_id(value: neo4rs::BoltDateTimeZoneId) -> PropertyScalar {
    let tz_id = value.tz_id().to_string();
    let datetime: Result<DateTime<FixedOffset>, _> = (&value).try_into();
    match datetime {
        Ok(v) => PropertyScalar::Datetime(format!("{}[{tz_id}]", v.to_rfc3339())),
        Err(_) => PropertyScalar::Json(format!("{:?}", BoltType::DateTimeZoneId(value))),
    }
}

#[cfg(test)]
mod tests {
    use super::{bolt_map_remove_aliases, bolt_type_to_property_scalar};
    use chrono::{DateTime, FixedOffset, NaiveDate, NaiveDateTime, NaiveTime};
    use neo4rs::{BoltMap, BoltString, BoltType};

    #[test]
    fn parses_aliases_from_json_like_string() {
        let mut map = BoltMap::default();
        map.value.insert(
            BoltString::from("aliases"),
            BoltType::from("[\"alpha\",\"beta\"]"),
        );
        assert_eq!(
            bolt_map_remove_aliases(&mut map, "aliases"),
            vec!["alpha", "beta"]
        );
    }

    #[test]
    fn maps_bolt_datetime_variants() {
        let datetime = DateTime::parse_from_rfc3339("2026-03-03T15:56:25.155889+00:00").unwrap();
        let local_datetime =
            NaiveDateTime::parse_from_str("2026-03-03T15:56:25.155889", "%Y-%m-%dT%H:%M:%S%.f")
                .unwrap();
        let date = NaiveDate::from_ymd_opt(2026, 3, 3).unwrap();
        let time = NaiveTime::from_hms_nano_opt(15, 56, 25, 155_889_000).unwrap();
        let utc = FixedOffset::east_opt(0).unwrap();

        assert!(matches!(
            bolt_type_to_property_scalar(BoltType::DateTime(datetime.into())),
            crate::domain::PropertyScalar::Datetime(v)
                if v == "2026-03-03T15:56:25.155889+00:00"
        ));
        assert!(matches!(
            bolt_type_to_property_scalar(BoltType::LocalDateTime(local_datetime.into())),
            crate::domain::PropertyScalar::Datetime(v) if v == "2026-03-03T15:56:25.155889"
        ));
        assert!(matches!(
            bolt_type_to_property_scalar(BoltType::Date(date.into())),
            crate::domain::PropertyScalar::Datetime(v) if v == "2026-03-03"
        ));
        assert!(matches!(
            bolt_type_to_property_scalar(BoltType::Time((time, utc).into())),
            crate::domain::PropertyScalar::Datetime(v) if v == "15:56:25.155889+00:00"
        ));
    }
}
