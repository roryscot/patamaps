export default async function Item({params}:{params:Promise<{id:string}>}) {
  const {id} = await params;
  return <main><h1>Item {id}</h1><a href="/">Catalog</a></main>;
}
