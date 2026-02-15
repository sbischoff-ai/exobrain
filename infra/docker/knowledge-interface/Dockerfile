FROM rust:1.76 as builder
WORKDIR /app
COPY apps/knowledge-interface .
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/exobrain-knowledge-interface /usr/local/bin/exobrain-knowledge-interface
EXPOSE 50051
CMD ["exobrain-knowledge-interface"]
