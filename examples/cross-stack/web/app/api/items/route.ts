export async function POST(request: Request) {
  let value: unknown;
  try { value = await request.json(); } catch { return Response.json({error:"invalid-json"}, {status:400}); }
  const base = process.env.CATALOG_SERVICE_URL ?? "http://127.0.0.1:43187";
  const response = await fetch(base + "/items", {method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(value),cache:"no-store"});
  return new Response(await response.text(), {status:response.status,headers:{"content-type":"application/json"}});
}
