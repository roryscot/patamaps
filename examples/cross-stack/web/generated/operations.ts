// Generated from sha256:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3; regenerate after correspondence changes.
export const BINDINGS = JSON.parse("{\"urn:example:operation:create-item\":{\"endpoint\":{\"attributes\":{\"http\":{\"method\":\"POST\",\"path\":\"/items\",\"successStatus\":201}},\"id\":\"urn:example:operation:create-item:endpoint\",\"kind\":\"routing:endpoint\"},\"handler\":{\"attributes\":{\"http\":{\"errorType\":\"OperationError\",\"errors\":[{\"code\":\"invalid-name\",\"status\":400,\"variant\":\"InvalidName\"},{\"code\":\"backend-failure\",\"status\":500,\"variant\":\"BackendFailure\"}],\"modulePath\":\"handlers/create_item.rs\",\"profile\":\"patamaps-http-object-strings-1\",\"requestType\":\"CreateItemRequest\",\"responseSchema\":{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\",\"additionalProperties\":false,\"properties\":{\"id\":{\"type\":\"string\"},\"name\":{\"type\":\"string\"}},\"required\":[\"id\",\"name\"],\"type\":\"object\"},\"responseType\":\"CreateItemResponse\"}},\"id\":\"urn:example:operation:create-item:handler\",\"kind\":\"routing:handler\",\"locators\":[{\"digest\":\"sha256:1e04089800d93b65af6823c1be25653244b70252723e6f9df4005e80a2eea962\",\"uri\":\"rust:crate::catalog::create_item\"}]},\"input\":{\"attributes\":{\"jsonSchema\":{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\",\"additionalProperties\":false,\"properties\":{\"name\":{\"maxLength\":80,\"minLength\":1,\"type\":\"string\"}},\"required\":[\"name\"],\"type\":\"object\"}},\"id\":\"urn:example:operation:create-item:input\",\"kind\":\"routing:schema\",\"locators\":[{\"digest\":\"sha256:e814007c18146f82674e36f5dc6fb1affe8e871f828c8ddff117f244e2ddfe95\",\"uri\":\"json-schema:contracts/create-item.request.schema.json\"}]}}}") as { readonly ["urn:example:operation:create-item"]: { readonly ["endpoint"]: { readonly ["attributes"]: { readonly ["http"]: { readonly ["method"]: "POST"; readonly ["path"]: "/items"; readonly ["successStatus"]: number } }; readonly ["id"]: "urn:example:operation:create-item:endpoint"; readonly ["kind"]: "routing:endpoint" }; readonly ["handler"]: { readonly ["attributes"]: { readonly ["http"]: { readonly ["errorType"]: "OperationError"; readonly ["errors"]: readonly [{ readonly ["code"]: "invalid-name"; readonly ["status"]: number; readonly ["variant"]: "InvalidName" }, { readonly ["code"]: "backend-failure"; readonly ["status"]: number; readonly ["variant"]: "BackendFailure" }]; readonly ["modulePath"]: "handlers/create_item.rs"; readonly ["profile"]: "patamaps-http-object-strings-1"; readonly ["requestType"]: "CreateItemRequest"; readonly ["responseSchema"]: { readonly ["$schema"]: "https://json-schema.org/draft/2020-12/schema"; readonly ["additionalProperties"]: false; readonly ["properties"]: { readonly ["id"]: { readonly ["type"]: "string" }; readonly ["name"]: { readonly ["type"]: "string" } }; readonly ["required"]: readonly ["id", "name"]; readonly ["type"]: "object" }; readonly ["responseType"]: "CreateItemResponse" } }; readonly ["id"]: "urn:example:operation:create-item:handler"; readonly ["kind"]: "routing:handler"; readonly ["locators"]: readonly [{ readonly ["digest"]: "sha256:1e04089800d93b65af6823c1be25653244b70252723e6f9df4005e80a2eea962"; readonly ["uri"]: "rust:crate::catalog::create_item" }] }; readonly ["input"]: { readonly ["attributes"]: { readonly ["jsonSchema"]: { readonly ["$schema"]: "https://json-schema.org/draft/2020-12/schema"; readonly ["additionalProperties"]: false; readonly ["properties"]: { readonly ["name"]: { readonly ["maxLength"]: number; readonly ["minLength"]: number; readonly ["type"]: "string" } }; readonly ["required"]: readonly ["name"]; readonly ["type"]: "object" } }; readonly ["id"]: "urn:example:operation:create-item:input"; readonly ["kind"]: "routing:schema"; readonly ["locators"]: readonly [{ readonly ["digest"]: "sha256:e814007c18146f82674e36f5dc6fb1affe8e871f828c8ddff117f244e2ddfe95"; readonly ["uri"]: "json-schema:contracts/create-item.request.schema.json" }] } } };
export type SemanticId = keyof typeof BINDINGS;
// HTTP profile patamaps-http-object-strings-1; projection sha256:b8164dd6cc718a37f1553e717e97d44bd1f1d3545d42103eec229fbec99612d3.
export interface Requests {
"urn:example:operation:create-item": { "name": string; };
}
export interface Responses {
"urn:example:operation:create-item": { "id": string; "name": string; };
}
export const OPERATIONS = [
{ id: "urn:example:operation:create-item", frontend: { method: "POST", path: "/api/items" }, backend: { method: "POST", path: "/items" }, successStatus: 201, errors: [{"code":"invalid-name","status":400},{"code":"backend-failure","status":500},{"code":"invalid-request","status":400},{"code":"input-limit","status":413},{"code":"invalid-response","status":500}] },
] as const;
function unicodeScalars(value: string): boolean {
for (const point of value) { const n = point.codePointAt(0)!; if (n >= 0xd800 && n <= 0xdfff) return false; }
return true;
}
function request_0(value: unknown): boolean { if (typeof value !== 'object' || value === null || Array.isArray(value) || Object.keys(value).length !== 1) return false;
const object = value as Record<string, unknown>;
if (!Object.prototype.hasOwnProperty.call(object, "name")) return false;
const text0 = object["name"];
if (typeof text0 !== 'string' || !unicodeScalars(text0)) return false;
const length0 = Array.from(text0).length;
if (length0 < 1 || length0 > 80) return false;
return true;
 }
function response_0(value: unknown): boolean { if (typeof value !== 'object' || value === null || Array.isArray(value) || Object.keys(value).length !== 2) return false;
const object = value as Record<string, unknown>;
if (!Object.prototype.hasOwnProperty.call(object, "id")) return false;
const text0 = object["id"];
if (typeof text0 !== 'string' || !unicodeScalars(text0)) return false;
const length0 = Array.from(text0).length;
if (length0 < 0 || length0 > 4294967295) return false;
if (!Object.prototype.hasOwnProperty.call(object, "name")) return false;
const text1 = object["name"];
if (typeof text1 !== 'string' || !unicodeScalars(text1)) return false;
const length1 = Array.from(text1).length;
if (length1 < 0 || length1 > 4294967295) return false;
return true;
 }
export function validRequest(id: SemanticId, value: unknown): boolean {
switch (id) {
case "urn:example:operation:create-item": return request_0(value);
default: return false;
}
}
export function validResponse(id: SemanticId, value: unknown): boolean {
switch (id) {
case "urn:example:operation:create-item": return response_0(value);
default: return false;
}
}
export async function callOperation<I extends SemanticId>(id: I, input: Requests[I], options: {base?: string; endpoint?: 'frontend' | 'backend'; transport?: typeof fetch} = {}): Promise<{status: number; body: Responses[I] | {error: string}}> {
const operation = OPERATIONS.find(op => op.id === id);
if (!operation || !validRequest(id, input)) throw new Error('HTTP_INVALID_REQUEST');
const endpoint = operation[options.endpoint ?? 'frontend'];
const response = await (options.transport ?? fetch)((options.base ?? '') + endpoint.path, {method:endpoint.method, headers:{'content-type':'application/json'}, body:JSON.stringify(input), cache:'no-store'});
let body: unknown;
try { body = await response.json(); } catch { throw new Error('HTTP_INVALID_JSON'); }
if (response.status === operation.successStatus) {
if (!validResponse(id, body)) throw new Error('HTTP_RESPONSE_CONTRACT');
return {status:response.status, body:body as Responses[I]};
}
if (typeof body !== 'object' || body === null || Array.isArray(body) || Object.keys(body).length !== 1 || !('error' in body) || typeof body.error !== 'string' || !operation.errors.some(e => e.status === response.status && e.code === body.error)) throw new Error('HTTP_ERROR_CONTRACT');
return {status:response.status, body:body as {error:string}};
}

