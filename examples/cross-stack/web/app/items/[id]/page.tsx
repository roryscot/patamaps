export default async function Item({params}:{params:Promise<{id:string}>}) {
  const {id} = await params;
  let displayId = id;
  try { displayId = decodeURIComponent(id); } catch { /* A literal percent stays text. */ }
  return <main><h1>Item {displayId}</h1><a href="/">Catalog</a></main>;
}
