use std::num::{NonZeroU32, ParseIntError};
use std::str::FromStr;

pub(crate) const LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE: u32 = 50;
pub(crate) const LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE: u32 = 200;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct PageCursor(u64);

impl PageCursor {
    pub(crate) fn get(self) -> u64 {
        self.0
    }

    pub(crate) fn parse_optional(token: Option<&str>) -> Result<Option<Self>, ParseIntError> {
        Self::normalize_optional(token)
            .as_deref()
            .map(str::parse)
            .transpose()
    }

    pub(crate) fn normalize_optional(token: Option<&str>) -> Option<String> {
        token
            .map(str::trim)
            .filter(|token| !token.is_empty())
            .map(ToOwned::to_owned)
    }
}

impl FromStr for PageCursor {
    type Err = ParseIntError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        s.trim().parse().map(Self)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct PageSize(NonZeroU32);

impl PageSize {
    pub(crate) fn from_requested(requested: Option<u32>) -> Self {
        let raw = requested.unwrap_or(LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE);
        let clamped = raw.clamp(1, LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE);
        Self(NonZeroU32::new(clamped).expect("clamped page size must be non-zero"))
    }

    pub(crate) fn get(self) -> u32 {
        self.0.get()
    }
}

#[cfg(test)]
mod tests {
    use super::{
        PageCursor, PageSize, LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE,
        LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE,
    };

    #[test]
    fn page_cursor_optional_normalizes_whitespace_to_none() {
        let cursor = PageCursor::normalize_optional(Some("   "));
        assert_eq!(cursor, None);
    }

    #[test]
    fn page_cursor_optional_rejects_invalid_token() {
        let err = PageCursor::parse_optional(Some("not-a-number"))
            .expect_err("invalid cursor should fail");
        assert!(err.to_string().contains("invalid digit"));
    }

    #[test]
    fn page_size_uses_default_when_request_missing() {
        let page_size = PageSize::from_requested(None);
        assert_eq!(page_size.get(), LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE);
    }

    #[test]
    fn page_size_clamps_to_max_bound() {
        let page_size = PageSize::from_requested(Some(u32::MAX));
        assert_eq!(page_size.get(), LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE);
    }
}
