use axum::{
    Json, Router,
    extract::{DefaultBodyLimit, Path, Query, State, rejection::JsonRejection},
    http::{HeaderMap, StatusCode},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
#[derive(Clone)]
struct Context {
    tag: &'static str,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Evaluate {
    message: String,
    fail: Option<bool>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Replay {
    expected_report: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Filter {
    limit: Option<u32>,
    verbose: Option<bool>,
}
#[derive(Serialize)]
struct Reply {
    state: String,
    kind: String,
    value: String,
    limit: Option<u32>,
    verbose: Option<bool>,
}
#[derive(Serialize)]
struct Problem {
    error: String,
    issues: Vec<Issue>,
}
#[derive(Serialize)]
struct Issue {
    path: String,
    message: String,
}
type Failure = (StatusCode, Json<Problem>);
type Result<T> = ::std::result::Result<T, Failure>;
type F = Evaluate;
type Fut = Reply;
fn problem(status: StatusCode, message: &str) -> Failure {
    (
        status,
        Json(Problem {
            error: message.into(),
            issues: vec![Issue {
                path: "$".into(),
                message: message.into(),
            }],
        }),
    )
}
async fn evaluate(
    State(context): State<Context>,
    body: ::std::result::Result<Json<Evaluate>, JsonRejection>,
) -> Result<Json<Reply>> {
    let Json(body) = body.map_err(|e| problem(e.status(), &e.body_text()))?;
    if body.fail.unwrap_or(false) {
        return Err(problem(StatusCode::BAD_REQUEST, "domain-refusal"));
    }
    Ok(Json(Reply {
        state: context.tag.into(),
        kind: "evaluate".into(),
        value: body.message,
        limit: None,
        verbose: None,
    }))
}
async fn replay(
    State(context): State<Context>,
    body: ::std::result::Result<Json<Replay>, JsonRejection>,
) -> Result<Json<Reply>> {
    let Json(body) = body.map_err(|e| problem(e.status(), &e.body_text()))?;
    Ok(Json(Reply {
        state: context.tag.into(),
        kind: "replay".into(),
        value: body.expected_report,
        limit: None,
        verbose: None,
    }))
}
async fn fetch_item(
    State(context): State<Context>,
    Path(id): Path<String>,
    Query(filter): Query<Filter>,
    headers: HeaderMap,
) -> Result<Json<Reply>> {
    if headers.get("x-proof").and_then(|v| v.to_str().ok()) != Some("allow") {
        return Err(problem(StatusCode::BAD_REQUEST, "header-refusal"));
    }
    Ok(Json(Reply {
        state: context.tag.into(),
        kind: "get".into(),
        value: id,
        limit: filter.limit,
        verbose: filter.verbose,
    }))
}
async fn remove_item(State(context): State<Context>, Path(_id): Path<String>) -> StatusCode {
    if context.tag == "owned-state" {
        StatusCode::NO_CONTENT
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    }
}
async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"ok":true}))
}
pub fn router() -> Router {
    Router::new()
        .route("/evaluate", post(evaluate))
        .route("/replay", post(replay))
        .route(
            "/items/{id}",
            get(fetch_item)
                .put(fetch_item)
                .patch(fetch_item)
                .delete(remove_item),
        )
        .route("/health", get(health).head(health).options(health))
        .layer(DefaultBodyLimit::max(65536))
        .with_state(Context { tag: "owned-state" })
}
include!(env!("PATAMAPS_AXUM_WITNESS"));
