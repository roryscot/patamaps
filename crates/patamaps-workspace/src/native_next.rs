//! Captured Next App Router build observations. Never executes config, regex or HTTP.
use crate::Error;
use patamaps_contracts::{SafeInteger, byte_digest, parse};
use serde::Deserialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct NextBuildConfig {
    pub nonsecret_inputs: bool,
    pub routes_manifest: String,
    pub app_paths_manifest: String,
    pub configuration_projection: String,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Projection {
    profile: String,
    framework_version: String,
    build_receipt_digest: String,
    routes_digest: String,
    app_paths_digest: String,
    configuration: Configuration,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Configuration {
    base_path: String,
    output: String,
    trailing_slash: bool,
    environment: BTreeMap<String, String>,
    secret_references: BTreeMap<String, String>,
    transpile_packages: Vec<String>,
    server_actions: Option<ServerActions>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct ServerActions {
    body_size_limit: Option<String>,
    allowed_origins: Vec<String>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Manifest {
    version: SafeInteger,
    pages404: bool,
    app_type: String,
    case_sensitive: bool,
    base_path: String,
    redirects: Vec<Value>,
    headers: Vec<Value>,
    rewrites: Rewrites,
    dynamic_routes: Vec<Route>,
    static_routes: Vec<Route>,
    data_routes: Vec<Value>,
    rsc: Value,
    rewrite_headers: Value,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Rewrites {
    before_files: Vec<Value>,
    after_files: Vec<Value>,
    fallback: Vec<Value>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Route {
    page: String,
    regex: String,
    route_keys: BTreeMap<String, String>,
    named_regex: String,
}
fn refuse() -> Error {
    Error::refused(
        "NATIVE_NEXT_BUILD",
        "Unsupported, inconsistent or oversized Next build observation",
    )
}
fn bounded(value: &str) -> bool {
    value.len() <= 8192 && !value.chars().any(char::is_control)
}
fn route_path(value: &str) -> bool {
    value.starts_with('/')
        && bounded(value)
        && !value.contains(['\\', '?', '#'])
        && !value.split('/').any(|p| p == "." || p == "..")
}
fn env_name(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .enumerate()
            .all(|(i, b)| b == b'_' || b.is_ascii_uppercase() || i > 0 && b.is_ascii_digit())
}
fn public_environment_name(value: &str) -> bool {
    if !env_name(value) || !value.starts_with("NEXT_PUBLIC_") {
        return false;
    }
    let words = value.split('_').collect::<BTreeSet<_>>();
    let credential_words = [
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "PASSWD",
        "CREDENTIAL",
        "CREDENTIALS",
        "BEARER",
    ];
    !credential_words.iter().any(|word| words.contains(word))
        && !["_PRIVATE_KEY", "_SIGNING_KEY", "_ENCRYPTION_KEY"]
            .iter()
            .any(|suffix| value.contains(suffix))
}
fn version(value: &str) -> bool {
    let parts = value.split('.').collect::<Vec<_>>();
    parts.len() == 3
        && parts[0] == "16"
        && parts.iter().all(|p| {
            !p.is_empty()
                && p.bytes().all(|b| b.is_ascii_digit())
                && (*p == "0" || !p.starts_with('0'))
        })
}
fn digest(value: &str) -> bool {
    value.strip_prefix("sha256:").is_some_and(|v| {
        v.len() == 64
            && v.bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    })
}
fn object_keys(value: &Value, allowed: &[&str]) -> Result<(), Error> {
    let object = value.as_object().ok_or_else(refuse)?;
    if object.keys().any(|k| !allowed.contains(&k.as_str())) {
        return Err(refuse());
    }
    Ok(())
}
fn rule(value: &Value, category: &str) -> Result<(), Error> {
    let mut allowed = vec![
        "source",
        "regex",
        "has",
        "missing",
        "locale",
        "basePath",
        "caseSensitive",
    ];
    match category {
        "header" => allowed.push("headers"),
        "redirect" => allowed.extend(["destination", "statusCode", "internal", "priority"]),
        _ => allowed.extend(["destination", "check"]),
    }
    object_keys(value, &allowed)?;
    if !value["source"].as_str().is_some_and(|v| v.starts_with('/'))
        || value["regex"].as_str().is_some_and(str::is_empty)
        || category == "redirect" && value.get("statusCode").is_none()
        || category != "header" && value["destination"].as_str().is_some_and(str::is_empty)
    {
        return Err(refuse());
    }
    for field in ["source", "regex"] {
        if !value
            .get(field)
            .and_then(Value::as_str)
            .is_some_and(bounded)
        {
            return Err(refuse());
        }
    }
    if category != "header"
        && !value
            .get("destination")
            .and_then(Value::as_str)
            .is_some_and(bounded)
    {
        return Err(refuse());
    }
    for field in [
        "internal",
        "priority",
        "permanent",
        "locale",
        "basePath",
        "check",
        "caseSensitive",
    ] {
        if value.get(field).is_some_and(|v| !v.is_boolean()) {
            return Err(refuse());
        }
    }
    if let Some(status) = value.get("statusCode")
        && ![301.0, 302.0, 303.0, 307.0, 308.0].contains(&status.as_f64().ok_or_else(refuse)?)
    {
        return Err(refuse());
    }
    for field in ["has", "missing"] {
        if let Some(conditions) = value.get(field) {
            let conditions = conditions
                .as_array()
                .filter(|v| v.len() <= 64)
                .ok_or_else(refuse)?;
            for condition in conditions {
                object_keys(condition, &["type", "key", "value"])?;
                let kind = condition["type"].as_str().ok_or_else(refuse)?;
                if kind == "host"
                    && (condition.get("key").is_some()
                        || !condition
                            .get("value")
                            .and_then(Value::as_str)
                            .is_some_and(bounded))
                {
                    return Err(refuse());
                }
                if !["header", "cookie", "query", "host"].contains(&kind)
                    || kind != "host"
                        && !condition
                            .get("key")
                            .and_then(Value::as_str)
                            .is_some_and(bounded)
                    || condition
                        .get("key")
                        .is_some_and(|v| !v.as_str().is_some_and(bounded))
                    || condition
                        .get("value")
                        .is_some_and(|v| !v.as_str().is_some_and(bounded))
                {
                    return Err(refuse());
                }
            }
        }
    }
    if category == "header" {
        let headers = value["headers"]
            .as_array()
            .filter(|v| v.len() <= 128)
            .ok_or_else(refuse)?;
        for header in headers {
            object_keys(header, &["key", "value"])?;
            if !header["key"].as_str().is_some_and(bounded)
                || !header["value"].as_str().is_some_and(bounded)
            {
                return Err(refuse());
            }
        }
    } else if value.get("headers").is_some() {
        return Err(refuse());
    }
    Ok(())
}

pub(crate) fn observe(
    namespace: &str,
    inputs: &BTreeMap<&str, &str>,
    selection: &NextBuildConfig,
) -> Result<(Vec<Value>, Value), Error> {
    if !selection.nonsecret_inputs {
        return Err(Error::refused(
            "NATIVE_SECRET_INPUT",
            "Explicit nonsecret input declaration required",
        ));
    }
    let paths = [
        &selection.routes_manifest,
        &selection.app_paths_manifest,
        &selection.configuration_projection,
    ];
    if paths.iter().collect::<BTreeSet<_>>().len() != 3
        || inputs.len() != 3
        || paths
            .iter()
            .any(|p| !crate::relative_path(p) || !inputs.contains_key(p.as_str()))
        || inputs.values().map(|v| v.len()).sum::<usize>() > 8 * 1024 * 1024
    {
        return Err(refuse());
    }
    let projection: Projection =
        parse(inputs[selection.configuration_projection.as_str()].as_bytes())?;
    let manifest: Manifest = parse(inputs[selection.routes_manifest.as_str()].as_bytes())?;
    let apps: BTreeMap<String, String> =
        parse(inputs[selection.app_paths_manifest.as_str()].as_bytes())?;
    let config = &projection.configuration;
    if projection.profile != "patamaps-next-build-config-1"
        || !version(&projection.framework_version)
        || projection.framework_version.len() > 64
        || !digest(&projection.build_receipt_digest)
        || projection.routes_digest
            != byte_digest(inputs[selection.routes_manifest.as_str()].as_bytes())
        || projection.app_paths_digest
            != byte_digest(inputs[selection.app_paths_manifest.as_str()].as_bytes())
        || manifest.version.get() != 3
        || manifest.app_type != "app"
        || config.base_path != manifest.base_path
        || !config.base_path.is_empty() && !route_path(&config.base_path)
        || !["standalone", "export", "server"].contains(&config.output.as_str())
        || config.environment.len() > 64
        || config.secret_references.len() > 64
        || config
            .environment
            .iter()
            .any(|(k, v)| !public_environment_name(k) || !bounded(v))
        || config
            .secret_references
            .iter()
            .any(|(k, v)| !env_name(k) || !env_name(v) || config.environment.contains_key(k))
        || config.transpile_packages.len() > 128
        || config
            .transpile_packages
            .iter()
            .any(|v| v.is_empty() || !bounded(v))
        || config.server_actions.as_ref().is_some_and(|a| {
            a.allowed_origins.len() > 64
                || a.allowed_origins.iter().any(|v| !bounded(v))
                || a.body_size_limit
                    .as_ref()
                    .is_some_and(|v| v.is_empty() || !bounded(v))
        })
        || apps.len() > 4096
        || !manifest.data_routes.is_empty()
        || !manifest.rsc.is_object()
        || !manifest.rewrite_headers.is_object()
    {
        return Err(refuse());
    }
    let mut entities = Vec::new();
    let mut emit = |kind: &str,
                    source: &str,
                    identity: Value,
                    attributes: Value|
     -> Result<(), Error> {
        if entities.len() >= 10000 {
            return Err(refuse());
        }
        entities.push(json!({"id":super::native_discovery::physical_id(namespace,kind,&identity)?,
            "kind":kind,"locators":[{"uri":format!("workspace:{source}")}],"attributes":attributes}));
        Ok(())
    };
    let mut pages = BTreeSet::new();
    for (category, routes) in [
        ("static", &manifest.static_routes),
        ("dynamic", &manifest.dynamic_routes),
    ] {
        if routes.len() > 4096 {
            return Err(refuse());
        }
        for (index, route) in routes.iter().enumerate() {
            if !route_path(&route.page)
                || !pages.insert(&route.page)
                || !bounded(&route.regex)
                || !bounded(&route.named_regex)
                || route.route_keys.len() > 128
                || route
                    .route_keys
                    .iter()
                    .any(|(k, v)| !bounded(k) || !bounded(v))
            {
                return Err(refuse());
            }
            emit(
                "next-build-route",
                &selection.routes_manifest,
                json!([selection.routes_manifest, category, route.page]),
                json!({"category":category,"index":index,"page":route.page,"regex":route.regex,
                    "namedRegex":route.named_regex,"routeKeys":route.route_keys,"regexExecuted":false,"httpMethods":"not-observed"}),
            )?;
        }
    }
    for (category, rules) in [
        ("redirect", &manifest.redirects),
        ("header", &manifest.headers),
        ("beforeFiles", &manifest.rewrites.before_files),
        ("afterFiles", &manifest.rewrites.after_files),
        ("fallback", &manifest.rewrites.fallback),
    ] {
        if rules.len() > 4096 {
            return Err(refuse());
        }
        for (index, value) in rules.iter().enumerate() {
            rule(value, category)?;
            emit(
                "next-build-rule",
                &selection.routes_manifest,
                json!([selection.routes_manifest, category, index]),
                json!({"category":category,"index":index,"rule":value,"matchingAndExecution":"not-performed"}),
            )?;
        }
    }
    for (app, path) in &apps {
        if !route_path(app) || !route_path(path) {
            return Err(refuse());
        }
        emit(
            "next-build-module",
            &selection.app_paths_manifest,
            json!([selection.app_paths_manifest, app]),
            json!({"appPath":app,"routePath":path,"businessCorrespondence":"not-inferred","httpMethods":"not-observed"}),
        )?;
    }
    emit(
        "next-build-configuration",
        &selection.configuration_projection,
        json!(selection.configuration_projection),
        json!({"frameworkVersionDeclared":projection.framework_version,"buildReceiptDigestDeclared":projection.build_receipt_digest,
            "basePath":config.base_path,"output":config.output,"trailingSlash":config.trailing_slash,
            "caseSensitive":manifest.case_sensitive,"pages404":manifest.pages404,"environment":config.environment,
            "secretReferences":config.secret_references,"transpilePackages":config.transpile_packages,
            "serverActions":config.server_actions.as_ref().map(|a| json!({"bodySizeLimit":a.body_size_limit,"allowedOrigins":a.allowed_origins})),
            "configurationOrigin":"independent-owner-projection","secretResolution":"not-performed"}),
    )?;
    emit(
        "next-build-protocol",
        &selection.routes_manifest,
        json!([selection.routes_manifest, "protocol"]),
        json!({"rsc":manifest.rsc,"rewriteHeaders":manifest.rewrite_headers,"interpretation":"opaque-captured-metadata"}),
    )?;
    Ok((
        entities,
        json!({"profile":"patamaps-next-build-observations-1","manifestVersion":3,
        "frameworkVersionDeclared":projection.framework_version,"buildReceiptDigestDeclared":projection.build_receipt_digest,
        "compilationEstablished":false,"runtimeEstablished":false,"regexExecuted":false,
        "configurationOrigin":"independent-owner-projection","semanticMeaning":"owner-authored",
        "dataRoutes":"refused","methodsAndServerActionHandlers":"not-observed"}),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> (BTreeMap<String, String>, NextBuildConfig) {
        let routes = json!({"version":3,"pages404":true,"appType":"app","caseSensitive":false,"basePath":"/docs",
            "redirects":[{"source":"/old","destination":"/new","statusCode":308,"regex":"^/old$"}],
            "headers":[{"source":"/all","regex":"^/all$","headers":[{"key":"x-owner","value":"declared"}]}],
            "rewrites":{"beforeFiles":[{"source":"/first","destination":"/target","regex":"^/first$",
                "has":[{"type":"header","key":"x-mode","value":"one"}]}],
                "afterFiles":[{"source":"/proxy","destination":"http://127.0.0.1:1234/upstream","regex":"^/proxy$","missing":[{"type":"cookie","key":"session"}]}],
                "fallback":[]},
            "staticRoutes":[{"page":"/","regex":"^/docs(?:/)?$","routeKeys":{},"namedRegex":"^/docs(?:/)?$"}],
            "dynamicRoutes":[{"page":"/shop/[id]","regex":"^/docs/shop/([^/]+?)$","routeKeys":{"nxtPid":"nxtPid"},"namedRegex":"^/docs/shop/(?<nxtPid>[^/]+?)$"}],
            "dataRoutes":[],"rsc":{"header":"rsc"},"rewriteHeaders":{"pathHeader":"x-nextjs-rewritten-path"}});
        let apps = json!({"/(group)/page":"/","/shop/[id]/page":"/shop/[id]","/api/items/route":"/api/items"});
        let mut inputs = BTreeMap::from([
            ("routes.json".into(), routes.to_string()),
            ("apps.json".into(), apps.to_string()),
        ]);
        let projection = json!({"profile":"patamaps-next-build-config-1","frameworkVersion":"16.1.6",
            "buildReceiptDigest":format!("sha256:{}", "a".repeat(64)),
            "routesDigest":byte_digest(inputs["routes.json"].as_bytes()),"appPathsDigest":byte_digest(inputs["apps.json"].as_bytes()),
            "configuration":{"basePath":"/docs","output":"standalone","trailingSlash":false,
                "environment":{"NEXT_PUBLIC_API_URL":"http://127.0.0.1:1234"},
                "secretReferences":{"AUTH_TOKEN":"OWNER_AUTH_TOKEN"},"transpilePackages":["@owner/shared"],
                "serverActions":{"bodySizeLimit":"1mb","allowedOrigins":["localhost"]}}});
        inputs.insert("config.json".into(), projection.to_string());
        (
            inputs,
            NextBuildConfig {
                nonsecret_inputs: true,
                routes_manifest: "routes.json".into(),
                app_paths_manifest: "apps.json".into(),
                configuration_projection: "config.json".into(),
            },
        )
    }
    fn run(
        inputs: &BTreeMap<String, String>,
        config: &NextBuildConfig,
    ) -> Result<(Vec<Value>, Value), Error> {
        observe(
            "urn:test:next-build",
            &inputs
                .iter()
                .map(|(k, v)| (k.as_str(), v.as_str()))
                .collect(),
            config,
        )
    }
    fn mutate(inputs: &mut BTreeMap<String, String>, name: &str, change: impl FnOnce(&mut Value)) {
        let mut value: Value = serde_json::from_str(&inputs[name]).unwrap();
        change(&mut value);
        inputs.insert(name.into(), value.to_string());
    }
    fn rebind(inputs: &mut BTreeMap<String, String>) {
        let routes = byte_digest(inputs["routes.json"].as_bytes());
        let apps = byte_digest(inputs["apps.json"].as_bytes());
        mutate(inputs, "config.json", |v| {
            v["routesDigest"] = json!(routes);
            v["appPathsDigest"] = json!(apps);
        });
    }
    #[test]
    fn captures_compiled_routes_groups_conditions_and_configuration_without_execution() {
        let (inputs, config) = fixture();
        let (entities, metadata) = run(&inputs, &config).unwrap();
        assert_eq!(entities.len(), 11);
        assert_eq!(metadata["runtimeEstablished"], false);
        assert_eq!(metadata["compilationEstablished"], false);
        assert_eq!(metadata["regexExecuted"], false);
        let alias = entities
            .iter()
            .find(|e| e["attributes"]["appPath"] == "/(group)/page")
            .unwrap();
        assert_eq!(alias["attributes"]["routePath"], "/");
        assert_eq!(
            alias["attributes"]["businessCorrespondence"],
            "not-inferred"
        );
        let rewrite = entities
            .iter()
            .find(|e| e["attributes"]["category"] == "beforeFiles")
            .unwrap();
        assert_eq!(rewrite["attributes"]["rule"]["has"][0]["key"], "x-mode");
        let config = entities
            .iter()
            .find(|e| e["kind"] == "next-build-configuration")
            .unwrap();
        assert_eq!(
            config["attributes"]["secretReferences"]["AUTH_TOKEN"],
            "OWNER_AUTH_TOKEN"
        );
        assert_eq!(run(&inputs, &fixture().1).unwrap().0, entities);
    }
    #[test]
    fn cross_document_binding_inventory_and_nonsecret_declaration_are_required() {
        let (mut inputs, mut config) = fixture();
        config.nonsecret_inputs = false;
        assert!(run(&inputs, &config).is_err());
        config.nonsecret_inputs = true;
        inputs.insert("extra.json".into(), "{}".into());
        assert!(run(&inputs, &config).is_err());
        inputs.remove("extra.json");
        mutate(&mut inputs, "routes.json", |v| {
            v["caseSensitive"] = json!(true)
        });
        assert!(run(&inputs, &config).is_err());
        rebind(&mut inputs);
        assert!(run(&inputs, &config).is_ok());
        config.app_paths_manifest = config.routes_manifest.clone();
        assert!(run(&inputs, &config).is_err());
    }
    #[test]
    fn ordinary_public_environment_names_remain_allowed() {
        let (mut inputs, config) = fixture();
        mutate(&mut inputs, "config.json", |v| {
            v["configuration"]["environment"]["NEXT_PUBLIC_AUTH_URL"] =
                json!("https://auth.example.invalid");
            v["configuration"]["environment"]["NEXT_PUBLIC_SIGNING_ENABLED"] = json!("false");
        });
        assert!(run(&inputs, &config).is_ok());
    }
    #[test]
    fn secret_looking_public_environment_names_are_refused() {
        for name in [
            "NEXT_PUBLIC_SENTRY_AUTH_TOKEN",
            "NEXT_PUBLIC_CLIENT_SECRET",
            "NEXT_PUBLIC_DATABASE_PASSWORD",
            "NEXT_PUBLIC_JWT_PRIVATE_KEY",
            "NEXT_PUBLIC_SIGNING_KEY",
        ] {
            let (mut inputs, config) = fixture();
            mutate(&mut inputs, "config.json", |v| {
                v["configuration"]["environment"][name] = json!("must-not-be-retained")
            });
            let error = run(&inputs, &config).expect_err(name);
            assert!(
                !error.to_string().contains("must-not-be-retained"),
                "{name}"
            );
        }
    }
    #[test]
    fn frozen_invalid_manifest_and_projection_cases_refuse_after_rebinding() {
        type Mutation = (&'static str, &'static str, fn(&mut Value));
        let mut changes: Vec<Mutation> = vec![
            ("version", "routes.json", |v| v["version"] = json!(4)),
            ("pages-router", "routes.json", |v| {
                v["appType"] = json!("pages")
            }),
            ("unknown-field", "routes.json", |v| {
                v["futureRoutingMode"] = json!(true)
            }),
            ("data-routes", "routes.json", |v| {
                v["dataRoutes"] = json!([{}])
            }),
            ("duplicate-route", "routes.json", |v| {
                v["dynamicRoutes"][0]["page"] = json!("/")
            }),
            ("condition-kind", "routes.json", |v| {
                v["rewrites"]["beforeFiles"][0]["has"][0]["type"] = json!("body")
            }),
            ("rule-unknown", "routes.json", |v| {
                v["redirects"][0]["unreviewed"] = json!(true)
            }),
            ("bad-path", "apps.json", |v| {
                v["/api/items/route"] = json!("/../escape")
            }),
            ("secret-value", "config.json", |v| {
                v["configuration"]["environment"]["AUTH_TOKEN"] = json!("must-refuse")
            }),
            ("raw-key-field", "config.json", |v| {
                v["configuration"]["serverActions"]["encryptionKey"] = json!("must-refuse")
            }),
            ("base-path", "config.json", |v| {
                v["configuration"]["basePath"] = json!("/other")
            }),
            ("framework-version", "config.json", |v| {
                v["frameworkVersion"] = json!("17.0.0")
            }),
        ];
        changes.extend([
            (
                "host-without-value",
                "routes.json",
                (|v: &mut Value| v["rewrites"]["beforeFiles"][0]["has"][0] = json!({"type":"host"}))
                    as fn(&mut Value),
            ),
            (
                "missing-status",
                "routes.json",
                (|v: &mut Value| {
                    v["redirects"][0]
                        .as_object_mut()
                        .unwrap()
                        .remove("statusCode");
                }) as fn(&mut Value),
            ),
            (
                "header-destination",
                "routes.json",
                (|v: &mut Value| v["headers"][0]["destination"] = json!("/wrong"))
                    as fn(&mut Value),
            ),
            (
                "version-format",
                "config.json",
                (|v: &mut Value| v["frameworkVersion"] = json!("16.invalid.6")) as fn(&mut Value),
            ),
        ]);
        for (label, name, change) in changes {
            let (mut inputs, config) = fixture();
            mutate(&mut inputs, name, change);
            rebind(&mut inputs);
            assert!(run(&inputs, &config).is_err(), "{label} was accepted");
        }
    }
}
