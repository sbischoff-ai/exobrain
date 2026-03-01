use std::env;

#[derive(Debug, Clone)]
pub struct AppConfig {
    pub app_env: String,
    pub log_level: String,
    pub metastore_dsn: String,
    pub memgraph_addr: String,
    pub memgraph_database: String,
    pub qdrant_addr: String,
    pub model_provider_base_url: String,
    pub embedding_model_alias: String,
    pub use_mock_embedder: bool,
}

impl AppConfig {
    pub fn from_env() -> Result<Self, Box<dyn std::error::Error>> {
        let _ = dotenvy::from_path_override(".env");
        let _ = dotenvy::dotenv();

        let app_env = env::var("APP_ENV").unwrap_or_else(|_| "local".to_string());
        let default_log_level = match app_env.as_str() {
            "local" => "DEBUG",
            _ => "INFO",
        };
        let log_level = env::var("LOG_LEVEL").unwrap_or_else(|_| default_log_level.to_string());
        let metastore_dsn = env::var("KNOWLEDGE_SCHEMA_DSN")
            .or_else(|_| env::var("METASTORE_DSN"))
            .map_err(|_| "KNOWLEDGE_SCHEMA_DSN or METASTORE_DSN is required")?;

        Ok(Self {
            app_env,
            log_level,
            metastore_dsn,
            memgraph_addr: env::var("MEMGRAPH_BOLT_ADDR")?,
            memgraph_database: env::var("MEMGRAPH_DB").unwrap_or_else(|_| "memgraph".to_string()),
            qdrant_addr: env::var("QDRANT_ADDR")?,
            model_provider_base_url: env::var("MODEL_PROVIDER_BASE_URL")
                .unwrap_or_else(|_| "http://localhost:8010/v1".to_string()),
            embedding_model_alias: env::var("MODEL_PROVIDER_EMBEDDING_ALIAS")
                .unwrap_or_else(|_| "all-purpose".to_string()),
            use_mock_embedder: env::var("EMBEDDING_USE_MOCK")
                .map(|v| v.eq_ignore_ascii_case("true") || v == "1")
                .unwrap_or(false),
        })
    }

    pub fn enable_reflection(&self) -> bool {
        self.app_env == "local"
    }
}

#[cfg(test)]
mod tests {
    use super::AppConfig;
    use std::collections::HashMap;
    use std::sync::{Mutex, OnceLock};

    const ENV_KEYS: [&str; 7] = [
        "APP_ENV",
        "LOG_LEVEL",
        "KNOWLEDGE_SCHEMA_DSN",
        "METASTORE_DSN",
        "MEMGRAPH_BOLT_ADDR",
        "MEMGRAPH_DB",
        "QDRANT_ADDR",
    ];

    fn env_mutex() -> &'static Mutex<()> {
        static ENV_MUTEX: OnceLock<Mutex<()>> = OnceLock::new();
        ENV_MUTEX.get_or_init(|| Mutex::new(()))
    }

    struct EnvSnapshot {
        values: HashMap<&'static str, Option<String>>,
    }

    impl EnvSnapshot {
        fn capture() -> Self {
            let values = ENV_KEYS
                .into_iter()
                .map(|key| (key, std::env::var(key).ok()))
                .collect();
            Self { values }
        }

        fn clear_all(&self) {
            for key in ENV_KEYS {
                std::env::remove_var(key);
            }
        }
    }

    impl Drop for EnvSnapshot {
        fn drop(&mut self) {
            for key in ENV_KEYS {
                if let Some(value) = self.values.get(key).and_then(Clone::clone) {
                    std::env::set_var(key, value);
                } else {
                    std::env::remove_var(key);
                }
            }
        }
    }

    #[test]
    fn reflection_enabled_for_local() {
        let cfg = AppConfig {
            app_env: "local".to_string(),
            log_level: "DEBUG".to_string(),
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            memgraph_database: "memgraph".to_string(),
            qdrant_addr: "http://example".to_string(),
            model_provider_base_url: "http://localhost:8010/v1".to_string(),
            embedding_model_alias: "all-purpose".to_string(),
            use_mock_embedder: false,
        };

        assert!(cfg.enable_reflection());
    }

    #[test]
    fn defaults_memgraph_database_to_memgraph() {
        let _guard = env_mutex().lock().expect("env mutex poisoned");
        let snapshot = EnvSnapshot::capture();
        snapshot.clear_all();

        std::env::set_var("APP_ENV", "local");
        std::env::set_var("KNOWLEDGE_SCHEMA_DSN", "postgresql://example");
        std::env::set_var("MEMGRAPH_BOLT_ADDR", "bolt://example");
        std::env::remove_var("MEMGRAPH_DB");
        std::env::set_var("QDRANT_ADDR", "http://example");

        let cfg = AppConfig::from_env().expect("config should load");

        assert_eq!(cfg.memgraph_database, "memgraph");
    }

    #[test]
    fn from_env_errors_when_no_metastore_dsn_is_present() {
        let _guard = env_mutex().lock().expect("env mutex poisoned");
        let snapshot = EnvSnapshot::capture();
        snapshot.clear_all();

        std::env::set_var("APP_ENV", "local");
        std::env::set_var("MEMGRAPH_BOLT_ADDR", "bolt://example");
        std::env::set_var("QDRANT_ADDR", "http://example");

        let err = AppConfig::from_env().expect_err("config should fail without metastore DSN");

        assert_eq!(
            err.to_string(),
            "KNOWLEDGE_SCHEMA_DSN or METASTORE_DSN is required"
        );
    }

    #[test]
    fn reflection_disabled_for_non_local() {
        let cfg = AppConfig {
            app_env: "cluster".to_string(),
            log_level: "INFO".to_string(),
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            memgraph_database: "memgraph".to_string(),
            qdrant_addr: "http://example".to_string(),
            model_provider_base_url: "http://localhost:8010/v1".to_string(),
            embedding_model_alias: "all-purpose".to_string(),
            use_mock_embedder: false,
        };

        assert!(!cfg.enable_reflection());
    }
}
