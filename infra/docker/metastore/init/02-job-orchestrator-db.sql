SELECT 'CREATE ROLE job_orchestrator LOGIN PASSWORD ''job_orchestrator''' 
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'job_orchestrator'
)\gexec

SELECT 'CREATE DATABASE job_orchestrator_db OWNER job_orchestrator'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'job_orchestrator_db'
)\gexec

REVOKE ALL ON DATABASE job_orchestrator_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE job_orchestrator_db TO job_orchestrator;

\connect job_orchestrator_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
