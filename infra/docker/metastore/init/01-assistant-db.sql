SELECT 'CREATE ROLE assistant_backend LOGIN PASSWORD ''assistant_backend''' 
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'assistant_backend'
)\gexec

SELECT 'CREATE DATABASE assistant_db OWNER assistant_backend'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'assistant_db'
)\gexec

REVOKE ALL ON DATABASE assistant_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE assistant_db TO assistant_backend;

SELECT 'CREATE ROLE knowledge_schema LOGIN PASSWORD ''knowledge_schema''' 
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'knowledge_schema'
)\gexec

SELECT 'CREATE DATABASE knowledge_graph_schema OWNER knowledge_schema'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'knowledge_graph_schema'
)\gexec

REVOKE ALL ON DATABASE knowledge_graph_schema FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE knowledge_graph_schema TO knowledge_schema;

\connect assistant_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\connect knowledge_graph_schema
CREATE EXTENSION IF NOT EXISTS pgcrypto;
