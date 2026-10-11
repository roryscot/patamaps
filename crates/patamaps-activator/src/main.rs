use patamaps_activator::{ActivationRequest, ProtectedHost};
use patamaps_contracts::{MAX_INPUT_BYTES, canonical_bytes, parse};
use std::{
    io::{Read, Write},
    process::ExitCode,
};
fn run() -> Result<u8, Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 2 || !["activate", "active", "trust-update"].contains(&args[1].as_str()) {
        return Err("Usage: patamaps-activator activate|active; configuration is installed adjacent trust.json".into());
    }
    let executable = std::env::current_exe()?;
    patamaps_activator::check_installed_runtime(&executable)?;
    let host = ProtectedHost::new(
        executable
            .parent()
            .ok_or("Missing installation directory")?
            .join("trust.json"),
    )?;
    let (bytes, code) = if args[1] == "trust-update" {
        let mut bytes = Vec::new();
        std::io::stdin()
            .take(MAX_INPUT_BYTES as u64 + 1)
            .read_to_end(&mut bytes)?;
        let trust: patamaps_governance::TrustedConsumer = parse(&bytes)?;
        (canonical_bytes(&host.replace_trust(&trust)?)?, 0)
    } else if args[1] == "active" {
        let current = host.read()?;
        (
            canonical_bytes(
                &serde_json::json!({"status":if current.is_some(){"active"}else{"empty"},"current":current}),
            )?,
            0,
        )
    } else {
        let mut bytes = Vec::new();
        std::io::stdin()
            .take(MAX_INPUT_BYTES as u64 + 1)
            .read_to_end(&mut bytes)?;
        let request: ActivationRequest = parse(&bytes)?;
        let outcome = host.activate(&request);
        (canonical_bytes(&outcome)?, outcome.exit_code())
    };
    let mut output = std::io::stdout().lock();
    output.write_all(&bytes)?;
    output.write_all(b"\n")?;
    Ok(code)
}
fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
