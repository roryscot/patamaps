//! Original CLI argument and stream decisions; no admission or activation.
use crate::legacy_reporting::{LegacyReportText as T, js_text};
use crate::legacy_workspace::{
    error, get, has_errors, list, locale, obj, observed, parse, pretty, raw, scalar, text, truthy,
};
use crate::{
    LegacyReferenceOperation, LegacyReferenceRequest, LegacyReportingAction,
    LegacyReportingRequest, LegacyWorkspaceError, LegacyWorkspaceRequest, legacy_reference_request,
    legacy_reporting_request,
};
use patamaps_contracts::{LegacyOrderedJson as J, LegacyReadOnlyJson as Data};
use std::collections::HashMap;
fn value(t: T) -> J {
    Data::string_value(&t.0)
}
fn join(v: &[T]) -> J {
    value(T::join(v, ""))
}
fn stream(t: T) -> J {
    join(&[t, "\n".into()])
}
fn response(code: usize, stdout: J, stderr: J) -> J {
    obj(vec![
        ("exitCode", J::Number(code as f64)),
        ("stdout", stdout),
        ("stderr", stderr),
    ])
}
fn result(code: usize, out: &str, err: &str) -> J {
    response(code, scalar(out), scalar(err))
}
fn usage() -> J {
    result(
        2,
        "",
        &format!("{}\n", include_str!("legacy_cli_usage.txt")),
    )
}
fn source(s: &str) -> T {
    T::source(s)
}
fn upper(mut value: T) -> T {
    for unit in &mut value.0 {
        if matches!(*unit, 97..=122) {
            *unit -= 32
        }
    }
    value
}
fn field(v: &J, k: &str) -> T {
    js_text(v.get(k))
}
fn pack_list(p: Vec<J>) -> J {
    J::Array(p)
}
fn plan(input: &J) -> Result<J, LegacyWorkspaceError> {
    let args = list(input, "args")?;
    let Some(command) = args.first().and_then(J::string) else {
        return Ok(usage());
    };
    let args = &args[1..];
    if !matches!(
        command,
        "validate" | "diff" | "trace" | "authority" | "generate" | "check" | "migrate-sources"
    ) {
        if matches!(
            command,
            "compose"
                | "compile"
                | "promote"
                | "protected-promote"
                | "active"
                | "impact"
                | "link"
                | "sources"
                | "provenance"
                | "capture"
                | "replay"
                | "compare"
                | "repair"
                | "explain"
                | "inspect"
        ) {
            return Err(error(
                "Error",
                "This original CLI workflow is not yet implemented in Patamaps",
            ));
        }
        return Ok(usage());
    }
    let mut positions = Vec::new();
    let mut packs = Vec::new();
    if matches!(command, "generate" | "check" | "migrate-sources") {
        positions.extend_from_slice(args)
    } else {
        let mut i = 0;
        while i < args.len() {
            let arg = args[i]
                .string()
                .ok_or_else(|| error("TypeError", "CLI arguments require strings"))?;
            if !arg.starts_with("--") {
                positions.push(args[i].clone());
                i += 1;
                continue;
            }
            if arg != "--relation-pack" {
                return Err(error("Error", &format!("Unknown option {arg}")));
            }
            let Some(v) = args
                .get(i + 1)
                .and_then(J::string)
                .filter(|v| !v.is_empty() && !v.starts_with("--"))
            else {
                return Err(error("Error", "--relation-pack requires a value"));
            };
            packs.push(J::String(v.into()));
            i += 2;
        }
    }
    let valid = positions
        .first()
        .and_then(J::string)
        .is_some_and(|v| !v.is_empty())
        && match command {
            "validate" => positions.len() == 1,
            "diff" => positions.len() == 2 && positions[1].string().is_some_and(|v| !v.is_empty()),
            "authority" => {
                positions.len() == 3
                    && positions[1..]
                        .iter()
                        .all(|v| v.string().is_some_and(|v| !v.is_empty()))
            }
            "trace" => {
                positions
                    .get(1)
                    .and_then(J::string)
                    .is_some_and(|v| !v.is_empty())
                    && positions.get(2).is_none_or(|v| {
                        v.string()
                            .is_some_and(|v| matches!(v, "incoming" | "outgoing" | "both"))
                    })
            }
            _ => true,
        };
    if !valid {
        return Ok(usage());
    }
    let mut fields = vec![
        ("command", J::String(command.into())),
        ("positions", J::Array(positions.clone())),
        ("packPaths", pack_list(packs)),
    ];
    if matches!(command, "generate" | "check") {
        fields.push((
            "useCache",
            J::Bool(positions.get(1).and_then(J::string) != Some("--no-cache")),
        ))
    }
    if command == "trace" {
        let direction = positions.get(2).cloned().unwrap_or_else(|| scalar("both"));
        let depth = positions.get(3).and_then(J::string).unwrap_or("1");
        let trimmed = Data::string_units(depth);
        let trimmed = trimmed
            .iter()
            .copied()
            .skip_while(|u| {
                char::from_u32(u32::from(*u)).is_some_and(|c| c.is_whitespace() || c == '\u{feff}')
            })
            .collect::<Vec<_>>();
        let mut digits = trimmed.as_slice();
        let negative = digits.first() == Some(&45);
        if matches!(digits.first(), Some(43 | 45)) {
            digits = &digits[1..]
        }
        let digits = digits
            .iter()
            .take_while(|u| matches!(u, 48..=57))
            .copied()
            .collect::<Vec<_>>();
        let parsed = if digits.is_empty() {
            None
        } else {
            let s = String::from_utf16(&digits).expect("ASCII digits");
            Some(s.parse::<f64>().unwrap_or(f64::INFINITY) * if negative { -1.0 } else { 1.0 })
        };
        fields.push(("direction", direction));
        fields.push((
            "depthKind",
            scalar(match parsed {
                None => "nan",
                Some(n) if n == f64::INFINITY => "positive-infinity",
                Some(n) if n == f64::NEG_INFINITY => "negative-infinity",
                _ => "finite",
            }),
        ));
        if let Some(n) = parsed.filter(|n| n.is_finite()) {
            fields.push(("depth", J::Number(n)))
        }
    }
    Ok(obj(fields))
}
fn issues(issues: &[J]) -> J {
    value(T::join(
        &issues
            .iter()
            .map(|v| {
                T::join(
                    &[
                        upper(field(v, "severity")),
                        " ".into(),
                        field(v, "code"),
                        if truthy(v.get("path")) {
                            T::join(&[" ".into(), field(v, "path")], "")
                        } else {
                            "".into()
                        },
                        ": ".into(),
                        field(v, "message"),
                        "\n".into(),
                    ],
                    "",
                )
            })
            .collect::<Vec<_>>(),
        "",
    ))
}
fn report(input: &J) -> Result<J, LegacyWorkspaceError> {
    let request = LegacyReportingRequest {
        action: LegacyReportingAction::DriftReport { input: raw(input)? },
        locale: "en-US".into(),
    };
    legacy_reporting_request(request)
        .map(observed)
        .map_err(|e| error(&e.name, &e.message))
}
fn render(input: &J, language: &str) -> Result<J, LegacyWorkspaceError> {
    let plan = get(input, "plan")?;
    let command = text(plan, "command")?;
    let data = get(input, "data")?;
    Ok(match command {
        "validate" => {
            let entries = list(data, "issues")?;
            let errors = entries
                .iter()
                .filter(|v| v.get("severity").and_then(J::string) == Some("error"))
                .count();
            let valid = truthy(data.get("valid"));
            response(
                if valid { 0 } else { 1 },
                join(&[
                    source(issues(entries).string().expect("issue text")),
                    if valid {
                        "VALID".into()
                    } else {
                        "INVALID".into()
                    },
                    ": ".into(),
                    errors.into(),
                    " error(s), ".into(),
                    (entries.len() - errors).into(),
                    " warning(s)\n".into(),
                ]),
                scalar(""),
            )
        }
        "diff" => {
            let validations = list(data, "validations")?;
            if validations.iter().any(|v| !truthy(v.get("valid"))) {
                let all = validations
                    .iter()
                    .flat_map(|v| v.get("issues").and_then(J::array).unwrap_or(&[]))
                    .cloned()
                    .collect::<Vec<_>>();
                response(1, issues(&all), scalar(""))
            } else {
                response(
                    0,
                    pretty(get(data, "diff")?, &locale(language)?)?,
                    scalar(""),
                )
            }
        }
        "trace" => {
            if let Some(validation) = data.get("validationIssues") {
                response(
                    1,
                    issues(validation.array().expect("trace issues")),
                    scalar(""),
                )
            } else {
                let visits = list(data, "visits")?;
                let mut lines = Vec::new();
                for visit in visits {
                    let depth = match visit.get("depth") {
                        Some(J::Number(n)) => *n as usize,
                        _ => return Err(error("Error", "Expected trace depth")),
                    };
                    let mut line = vec![
                        "  ".repeat(depth).into(),
                        field(get(visit, "entity")?, "id"),
                    ];
                    if let Some(via) = visit.get("viaMapping") {
                        line.extend([
                            " via ".into(),
                            field(via, "relation"),
                            " (".into(),
                            field(via, "id"),
                            ")".into(),
                        ])
                    }
                    line.push("\n".into());
                    lines.push(T::join(&line, ""))
                }
                response(
                    if visits.is_empty() { 1 } else { 0 },
                    value(T::join(&lines, "")),
                    scalar(""),
                )
            }
        }
        "authority" => response(0, pretty(data, &locale(language)?)?, scalar("")),
        "check" => response(
            if has_errors(data)? { 1 } else { 0 },
            stream(source(report(data)?.string().expect("report string"))),
            scalar(""),
        ),
        "generate" => {
            if has_errors(data)? {
                let mut with_diff = data.clone();
                let J::Object(entries) = &mut with_diff else {
                    unreachable!()
                };
                entries.push((
                    "diff".into(),
                    obj(vec![
                        ("changes", J::Array(vec![])),
                        (
                            "counts",
                            obj(vec![
                                ("added", J::Number(0.0)),
                                ("removed", J::Number(0.0)),
                                ("changed", J::Number(0.0)),
                            ]),
                        ),
                    ]),
                ));
                response(
                    1,
                    scalar(""),
                    join(&[
                        source(report(&with_diff)?.string().expect("report")),
                        "\nGeneration refused because Metamap has errors.\n".into(),
                    ]),
                )
            } else {
                let graph = get(data, "graph")?;
                let config = get(input, "config")?;
                let mut r = response(
                    0,
                    join(&[
                        "Generated ".into(),
                        field(get(config, "outputs")?, "graph"),
                        ": ".into(),
                        list(graph, "entities")?.len().into(),
                        " entities, ".into(),
                        list(graph, "mappings")?.len().into(),
                        " mappings, ".into(),
                        list(graph, "authorities")?.len().into(),
                        " authorities\n".into(),
                    ]),
                    scalar(""),
                );
                if let J::Object(v) = &mut r {
                    v.push(("writeWorkspace".into(), J::Bool(true)))
                }
                r
            }
        }
        "migrate-sources" => {
            let positions = list(plan, "positions")?;
            if !truthy(data.get("valid")) {
                response(
                    1,
                    scalar(""),
                    join(&[
                        js_text(positions.first()),
                        " is not a legacy sources-of-truth document\n".into(),
                    ]),
                )
            } else {
                let result = get(data, "result")?;
                let warnings = list(result, "warnings")?;
                let stderr = value(T::join(
                    &warnings
                        .iter()
                        .map(|w| {
                            T::join(
                                &[
                                    "WARNING ".into(),
                                    field(w, "code"),
                                    " ".into(),
                                    field(w, "entryId"),
                                    ": ".into(),
                                    field(w, "message"),
                                    "\n".into(),
                                ],
                                "",
                            )
                        })
                        .collect::<Vec<_>>(),
                    "",
                ));
                let bytes = Data::pretty_bytes(get(result, "document")?)
                    .map_err(|e| error("Error", &e.to_string()))?;
                let serialized = scalar(std::str::from_utf8(&bytes).expect("pretty JSON"));
                if positions.get(1).is_some_and(|v| truthy(Some(v))) {
                    let output = positions[1].clone();
                    let mut r = response(
                        0,
                        join(&["Wrote ".into(), js_text(Some(&output)), "\n".into()]),
                        stderr,
                    );
                    if let J::Object(v) = &mut r {
                        v.push((
                            "writeFile".into(),
                            obj(vec![("path", output), ("content", serialized)]),
                        ))
                    }
                    r
                } else {
                    response(0, serialized, stderr)
                }
            }
        }
        _ => return Err(error("Error", "Unknown legacy CLI render operation")),
    })
}
fn reference(operation: LegacyReferenceOperation, input: J) -> Result<J, LegacyWorkspaceError> {
    legacy_reference_request(LegacyReferenceRequest {
        operation,
        input: raw(&input)?,
    })
    .and_then(|r| {
        Data::parse(r.get(), patamaps_contracts::COMPATIBILITY_JSON_LIMITS)
            .map(|d| d.value().clone())
            .map_err(|e| crate::LegacyReferenceError {
                code: "LEGACY_REFERENCE_INPUT".into(),
                name: "Error".into(),
                message: e.to_string(),
            })
    })
    .map_err(|e| error(&e.name, &e.message))
}
fn urn(namespace: &J, kind: &str, v: T) -> Result<J, LegacyWorkspaceError> {
    reference(
        LegacyReferenceOperation::Urn,
        obj(vec![
            ("namespace", namespace.clone()),
            ("kind", scalar(kind)),
            ("value", value(v)),
        ]),
    )
}
fn path_uri(path: &J, repository: &J) -> Result<J, LegacyWorkspaceError> {
    reference(
        LegacyReferenceOperation::RepositoryUri,
        obj(vec![
            ("path", path.clone()),
            ("repository", repository.clone()),
        ]),
    )
}
fn valid_migration(v: &J) -> bool {
    v.get("sourcesOfTruth")
        .and_then(J::array)
        .is_some_and(|entries| {
            entries.iter().all(|e| {
                e.get("id").and_then(J::string).is_some()
                    && e.get("label").and_then(J::string).is_some()
                    && ["paths", "outputs"].iter().all(|k| {
                        e.get(k)
                            .and_then(J::array)
                            .is_some_and(|a| a.iter().all(|v| v.string().is_some()))
                    })
            })
        })
}
fn migration(input: &J) -> Result<J, LegacyWorkspaceError> {
    let legacy = get(input, "legacy")?;
    let empty = obj(vec![]);
    let options = input.get("options").unwrap_or(&empty);
    let default_namespace = scalar("metamap");
    let default_repository = scalar("repository");
    let namespace = options
        .get("namespace")
        .filter(|v| !matches!(v, J::Null))
        .unwrap_or(&default_namespace);
    let repository = options
        .get("repository")
        .filter(|v| !matches!(v, J::Null))
        .unwrap_or(&default_repository);
    let provenance = input.get("provenance").cloned().unwrap_or_else(|| {
        obj(vec![
            ("status", scalar("declared")),
            ("assertedBy", scalar("adapter:legacy-sources-of-truth")),
        ])
    });
    let mut entities = Vec::<J>::new();
    let mut indices = HashMap::<String, usize>::new();
    let mut mappings = Vec::new();
    let mut authorities = Vec::new();
    let mut warnings = Vec::new();
    let mut undefined = Vec::new();
    let mut add = |e: J| {
        let key = e
            .get("id")
            .and_then(J::string)
            .expect("generated id")
            .to_owned();
        if let Some(i) = indices.get(&key) {
            entities[*i] = e
        } else {
            indices.insert(key, entities.len());
            entities.push(e)
        }
    };
    for entry in list(legacy, "sourcesOfTruth")? {
        let concept = urn(namespace, "concept", field(entry, "id"))?;
        let mut attributes = Vec::new();
        for k in ["updateSteps", "note"] {
            if let Some(v) = entry.get(k).filter(|v| truthy(Some(v))) {
                attributes.push((k.into(), v.clone()))
            }
        }
        add(obj(vec![
            ("id", concept.clone()),
            ("kind", scalar("concept")),
            ("label", get(entry, "label")?.clone()),
            ("attributes", J::Object(attributes)),
            ("provenance", provenance.clone()),
        ]));
        let paths = list(entry, "paths")?;
        let mode = if paths.len() == 1 {
            "canonical"
        } else {
            "candidate"
        };
        if paths.len() > 1 {
            warnings.push(obj(vec![
                ("code", scalar("LEGACY_MULTIPLE_SOURCES")),
                (
                    "message",
                    join(&[
                        field(entry, "id"),
                        " has ".into(),
                        paths.len().into(),
                        " sources with no fact-level ownership".into(),
                    ]),
                ),
                ("entryId", get(entry, "id")?.clone()),
            ]))
        }
        for (i, path) in paths.iter().enumerate() {
            let id = urn(&default_namespace, "legacy-artifact", js_text(Some(path)))?;
            add(obj(vec![
                ("id", id.clone()),
                ("kind", scalar("artifact")),
                ("label", path.clone()),
                (
                    "locators",
                    J::Array(vec![obj(vec![("uri", path_uri(path, repository)?)])]),
                ),
                ("attributes", obj(vec![("rawPath", path.clone())])),
                ("provenance", provenance.clone()),
            ]));
            mappings.push(obj(vec![
                (
                    "id",
                    urn(
                        &default_namespace,
                        "mapping",
                        T::join(&[field(entry, "id"), ":references:".into(), i.into()], ""),
                    )?,
                ),
                ("relation", scalar("core:references")),
                ("sources", J::Array(vec![concept.clone()])),
                ("targets", J::Array(vec![id.clone()])),
                ("cardinality", scalar("one-to-one")),
                ("lossiness", scalar("unknown")),
                ("provenance", provenance.clone()),
            ]));
            authorities.push(obj(vec![
                (
                    "id",
                    urn(
                        &default_namespace,
                        "authority",
                        T::join(&[field(entry, "id"), ":".into(), i.into()], ""),
                    )?,
                ),
                ("concept", concept.clone()),
                ("source", id),
                ("facts", J::Array(vec![scalar("*")])),
                ("mode", scalar(mode)),
                ("provenance", provenance.clone()),
            ]));
            for (op, code, suffix) in [
                (
                    LegacyReferenceOperation::AmbiguousPath,
                    "LEGACY_AMBIGUOUS_PATH",
                    " contains prose where a resolvable locator is required",
                ),
                (
                    LegacyReferenceOperation::PathPattern,
                    "LEGACY_PATH_PATTERN",
                    " uses a path pattern that requires an adapter to resolve",
                ),
            ] {
                if truthy(Some(&reference(op, obj(vec![("path", path.clone())]))?)) {
                    warnings.push(obj(vec![
                        ("code", scalar(code)),
                        ("message", join(&[field(entry, "id"), suffix.into()])),
                        ("entryId", get(entry, "id")?.clone()),
                        ("value", path.clone()),
                    ]))
                }
            }
        }
        for (i, output) in list(entry, "outputs")?.iter().enumerate() {
            let id = urn(&default_namespace, "legacy-output", js_text(Some(output)))?;
            let looks = Data::string_units(output.string().expect("output string"));
            let mut fields = vec![
                ("id", id.clone()),
                ("kind", scalar("projection")),
                ("label", output.clone()),
            ];
            if looks.contains(&47) && !looks.contains(&32) {
                fields.push((
                    "locators",
                    J::Array(vec![obj(vec![("uri", path_uri(output, repository)?)])]),
                ))
            }
            fields.extend([
                (
                    "attributes",
                    obj(vec![("legacyDescription", output.clone())]),
                ),
                ("provenance", provenance.clone()),
            ]);
            add(obj(fields));
            mappings.push(obj(vec![
                (
                    "id",
                    urn(
                        &default_namespace,
                        "mapping",
                        T::join(&[field(entry, "id"), ":generates:".into(), i.into()], ""),
                    )?,
                ),
                ("relation", scalar("core:generates")),
                ("sources", J::Array(vec![concept.clone()])),
                ("targets", J::Array(vec![id])),
                ("cardinality", scalar("one-to-one")),
                ("lossiness", scalar("unknown")),
                ("provenance", provenance.clone()),
            ]));
        }
        if let Some(spec) = entry.get("specDoc").filter(|v| truthy(Some(v))) {
            let id = urn(&default_namespace, "legacy-artifact", js_text(Some(spec)))?;
            add(obj(vec![
                ("id", id.clone()),
                ("kind", scalar("specification")),
                ("label", spec.clone()),
                (
                    "locators",
                    J::Array(vec![obj(vec![("uri", path_uri(spec, repository)?)])]),
                ),
                ("attributes", obj(vec![("rawPath", spec.clone())])),
                ("provenance", provenance.clone()),
            ]));
            mappings.push(obj(vec![
                (
                    "id",
                    urn(
                        &default_namespace,
                        "mapping",
                        T::join(&[field(entry, "id"), ":specified-by".into()], ""),
                    )?,
                ),
                ("relation", scalar("core:specified_by")),
                ("sources", J::Array(vec![concept])),
                ("targets", J::Array(vec![id])),
                ("cardinality", scalar("one-to-one")),
                ("lossiness", scalar("unknown")),
                ("provenance", provenance.clone()),
            ]))
        }
    }
    for (i, e) in entities.iter().enumerate() {
        if e.get("kind").and_then(J::string) == Some("projection") && e.get("locators").is_none() {
            undefined.push(J::Number(i as f64))
        }
    }
    let default_id = urn(namespace, "metamap", T::from("legacy-sources-of-truth"))?;
    let label = scalar("Imported sources of truth");
    let description = scalar("");
    let document = obj(vec![
        ("$schema", scalar("./schemas/metamap-graph.schema.json")),
        ("schemaVersion", scalar("2.0.0")),
        (
            "id",
            options
                .get("documentId")
                .filter(|v| !matches!(v, J::Null))
                .unwrap_or(&default_id)
                .clone(),
        ),
        ("namespace", namespace.clone()),
        (
            "label",
            options
                .get("label")
                .filter(|v| !matches!(v, J::Null))
                .unwrap_or(&label)
                .clone(),
        ),
        (
            "relationPacks",
            J::Array(vec![obj(vec![
                ("id", scalar("urn:metamap:relation-pack:core")),
                ("version", scalar("1.0.0")),
            ])]),
        ),
        ("entities", J::Array(entities)),
        ("mappings", J::Array(mappings)),
        ("authorities", J::Array(authorities)),
        (
            "metadata",
            obj(vec![
                ("adapter", scalar("legacy-sources-of-truth")),
                (
                    "legacyDescription",
                    legacy
                        .get("description")
                        .filter(|v| !matches!(v, J::Null))
                        .unwrap_or(&description)
                        .clone(),
                ),
            ]),
        ),
    ]);
    Ok(obj(vec![
        (
            "value",
            obj(vec![
                ("document", document),
                ("warnings", J::Array(warnings)),
            ]),
        ),
        ("undefinedLocators", J::Array(undefined)),
    ]))
}
pub fn legacy_cli_request(
    request: LegacyWorkspaceRequest,
) -> Result<Box<serde_json::value::RawValue>, LegacyWorkspaceError> {
    let input = parse(&request.input)?;
    let output = match request.operation.as_str() {
        "plan" => plan(&input)?,
        "validate" => {
            let document = Data::projected_value(get(&input, "document")?)
                .map_err(|e| error("Error", &e.to_string()))?;
            let registry: crate::LegacyGraphRegistry = serde_json::from_value(
                Data::projected_value(get(&input, "registry")?)
                    .map_err(|e| error("Error", &e.to_string()))?,
            )
            .map_err(|e| error("Error", &e.to_string()))?;
            crate::legacy_workspace::native(crate::validate_legacy_document(&document, &registry))
        }
        "render" => render(&input, &request.locale)?,
        "failure" => response(
            1,
            scalar(""),
            join(&[
                input
                    .get("stderr")
                    .map(|v| js_text(Some(v)))
                    .unwrap_or_else(|| "".into()),
                field(&input, "message"),
                "\n".into(),
            ]),
        ),
        "is-migration" => J::Bool(valid_migration(get(&input, "value")?)),
        "migration" => migration(&input)?,
        _ => return Err(error("Error", "Unknown legacy CLI operation")),
    };
    Data::json_raw(&output).map_err(|e| error("Error", &e.to_string()))
}
