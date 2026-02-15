FROM rust:1.85 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler \
  && rm -rf /var/lib/apt/lists/*
COPY apps/knowledge-interface .
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/exobrain-knowledge-interface /usr/local/bin/exobrain-knowledge-interface
EXPOSE 50051
CMD ["exobrain-knowledge-interface"]
