# syntax=docker/dockerfile:1.10.0
FROM rust:1.99.0-bookworm AS builder
WORKDIR /build
COPY service/ service/
RUN cargo build --manifest-path service/Cargo.toml --locked --release --target x86_64-unknown-linux-gnu --message-format=json-render-diagnostics > /build/cargo-messages.jsonl && rustc -Vv > /build/rustc-version.txt && sh service/tools/collect-notices.sh /build/licenses
FROM debian:bookworm-slim AS runtime
WORKDIR /app
COPY --from=builder /build/service/target/x86_64-unknown-linux-gnu/release/catalog-service /usr/local/bin/catalog-service
COPY config/service.toml /app/service.toml
COPY --from=builder /build/licenses /usr/share/licenses/catalog-service
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/catalog-service"]
CMD ["/app/service.toml"]
