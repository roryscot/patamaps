use patamaps_scientific_lookup_example::{Lookup, SemanticId};
fn run() -> Result<serde_json::Value, String> {
    let lookup = Lookup::from_static()?;
    if let Some(id) = std::env::args().nth(1) {
        lookup.lookup(SemanticId::parse(&id).ok_or("UNKNOWN_OPERATION")?)
    } else {
        lookup
            .subjects()
            .map(|id| lookup.lookup(id))
            .collect::<Result<Vec<_>, _>>()
            .map(serde_json::Value::Array)
    }
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
