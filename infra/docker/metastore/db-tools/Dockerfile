FROM rust:1.88-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    clang \
    libclang-dev \
    gcc \
    make \
 && rm -rf /var/lib/apt/lists/*

RUN cargo install --locked reshape

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/cargo/bin/reshape /usr/local/bin/reshape
COPY infra/docker/metastore/init/01-assistant-db.sql /opt/exobrain/sql/init/01-assistant-db.sql
COPY infra/metastore/assistant-backend/migrations /opt/exobrain/assistant-backend/migrations
COPY infra/metastore/assistant-backend/seeds /opt/exobrain/assistant-backend/seeds
COPY infra/metastore/job-orchestrator/migrations /opt/exobrain/job-orchestrator/migrations

CMD ["bash"]
COPY infra/metastore/knowledge-interface/migrations /opt/exobrain/knowledge-interface/migrations
COPY infra/metastore/knowledge-interface/seeds /opt/exobrain/knowledge-interface/seeds
