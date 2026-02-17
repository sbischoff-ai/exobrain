DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'assistant_backend') THEN
      CREATE ROLE assistant_backend LOGIN PASSWORD 'assistant_backend';
   END IF;
END
$$;

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'assistant_db') THEN
      CREATE DATABASE assistant_db OWNER assistant_backend;
   END IF;
END
$$;

REVOKE ALL ON DATABASE assistant_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE assistant_db TO assistant_backend;

\connect assistant_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
