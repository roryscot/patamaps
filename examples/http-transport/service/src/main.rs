mod api;
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
    println!("LISTEN {}", listener.local_addr()?);
    axum::serve(listener, api::router()).await?;
    Ok(())
}
