mod bindings;
#[path = "../contract/input_schema.rs"]
mod contract;
mod schema_bindings;
#[path = "../service/handlers/create_user.rs"]
mod service;
fn run() -> Result<serde_json::Value, String> {
    let mut args = std::env::args().skip(1);
    let id = args.next().ok_or("UNKNOWN_OPERATION")?;
    let native = bindings::SemanticId::parse(&id).ok_or("UNKNOWN_OPERATION")?;
    let schema = schema_bindings::SemanticId::parse(&id).ok_or("UNKNOWN_OPERATION")?;
    let input = args.next().ok_or("INVALID_CREATE_USER_INPUT")?;
    let normalized = schema_bindings::dispatch(schema, &input);
    let value: serde_json::Value =
        serde_json::from_str(&normalized).map_err(|_| "INVALID_CREATE_USER_INPUT")?;
    if value.get("error").is_some() {
        return Err("INVALID_CREATE_USER_INPUT".into());
    }
    serde_json::from_str(&bindings::dispatch(native, &normalized)).map_err(|e| e.to_string())
}
fn main() {
    match run() {
        Ok(v) => println!("{v}"),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(2)
        }
    }
}
