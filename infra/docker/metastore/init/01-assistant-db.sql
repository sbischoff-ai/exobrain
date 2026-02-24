SELECT 'CREATE ROLE assistant_backend LOGIN PASSWORD ''assistant_backend''' 
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'assistant_backend'
)\gexec

SELECT 'CREATE ROLE job_orchestrator LOGIN PASSWORD ''job_orchestrator''' 
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'job_orchestrator'
)\gexec

SELECT 'CREATE DATABASE assistant_db OWNER assistant_backend'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'assistant_db'
)\gexec

SELECT 'CREATE DATABASE job_orchestrator_db OWNER job_orchestrator'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'job_orchestrator_db'
)\gexec

REVOKE ALL ON DATABASE assistant_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE assistant_db TO assistant_backend;

REVOKE ALL ON DATABASE job_orchestrator_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE job_orchestrator_db TO job_orchestrator;

\connect assistant_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\connect job_orchestrator_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
