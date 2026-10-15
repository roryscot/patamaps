use catalog_service::{CreateItemRequest, OperationError, create_item};
use std::{env, fs::File, io::Read};
use tiny_http::{Header, Response, Server, StatusCode};
fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut args = env::args().skip(1);
    let path = args.next().ok_or("configuration path required")?;
    let mut text = String::new();
    File::open(path)?.take(65537).read_to_string(&mut text)?;
    if text.len() > 65536 {
        return Err("configuration too large".into());
    }
    let config = toml_edit::Document::parse(text)?;
    let listen = config["http"]["listen"]
        .as_str()
        .ok_or("http.listen required")?;
    let address = args.next().unwrap_or_else(|| listen.to_owned());
    if args.next().is_some() {
        return Err("unexpected arguments".into());
    }
    let server = Server::http(&address)?;
    println!("LISTEN {}", server.server_addr());
    for mut request in server.incoming_requests() {
        let (status, body) = if request.method().as_str() == "GET" && request.url() == "/health" {
            (200, serde_json::json!({"status":"ok"}))
        } else if request.method().as_str() == "POST" && request.url() == "/items" {
            let mut raw = Vec::new();
            request.as_reader().take(8193).read_to_end(&mut raw)?;
            if raw.len() > 8192 {
                (413, serde_json::json!({"error":"input-limit"}))
            } else {
                match serde_json::from_slice::<CreateItemRequest>(&raw) {
                    Err(_) => (400, serde_json::json!({"error":"invalid-request"})),
                    Ok(value) => match create_item(value) {
                        Ok(value) => (201, serde_json::to_value(value)?),
                        Err(OperationError::InvalidName) => {
                            (400, serde_json::json!({"error":"invalid-name"}))
                        }
                        Err(OperationError::BackendFailure) => {
                            (500, serde_json::json!({"error":"backend-failure"}))
                        }
                    },
                }
            }
        } else {
            (404, serde_json::json!({"error":"not-found"}))
        };
        let response = Response::from_string(serde_json::to_string(&body)?)
            .with_status_code(StatusCode(status))
            .with_header(
                Header::from_bytes("content-type", "application/json").expect("static header"),
            );
        request.respond(response)?;
    }
    Ok(())
}
