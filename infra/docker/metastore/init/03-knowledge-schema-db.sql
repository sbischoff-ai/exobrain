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

\connect knowledge_graph_schema
CREATE EXTENSION IF NOT EXISTS pgcrypto;
