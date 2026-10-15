# syntax=docker/dockerfile:1.10.0
FROM rust:1.99.0-bookworm AS builder
WORKDIR /build
COPY service/ service/
RUN cargo build --manifest-path service/Cargo.toml --locked --release --target x86_64-unknown-linux-gnu
FROM debian:bookworm-slim AS runtime
WORKDIR /app
COPY --from=builder /build/service/target/x86_64-unknown-linux-gnu/release/catalog-service /usr/local/bin/catalog-service
COPY config/service.toml /app/service.toml
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/catalog-service"]
CMD ["/app/service.toml"]
