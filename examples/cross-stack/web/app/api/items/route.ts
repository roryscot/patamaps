import { callOperation, validRequest, type Requests } from "../../../generated/operations";
const id = "urn:example:operation:create-item";
export async function POST(request: Request) {
  let value: unknown;
  try { value = await request.json(); } catch { return Response.json({error:"invalid-json"}, {status:400}); }
  if (!validRequest(id, value)) return Response.json({error:"invalid-request"}, {status:400});
  try {
    const result = await callOperation(id, value as Requests[typeof id], {base:process.env.CATALOG_SERVICE_URL ?? "http://127.0.0.1:43187", endpoint:"backend"});
    return Response.json(result.body, {status:result.status});
  } catch {
    return Response.json({error:"backend-contract"}, {status:502});
  }
}
