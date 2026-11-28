
#[cfg(test)] mod tests {
 fn graph(bytes: &[u8]) {
  let old: alpha::GraphDocument = alpha::parse(bytes).unwrap();
  let new: current::GraphDocument = current::parse(bytes).unwrap();
  let a = alpha::canonical_bytes(&old).unwrap(); let b = current::canonical_bytes(&new).unwrap();
  assert_eq!(a,b); assert!(alpha::parse::<alpha::GraphDocument>(&b).is_ok()); assert!(current::parse::<current::GraphDocument>(&a).is_ok());
 }
 #[test] fn representative_graphs_and_pack_round_trip() {
  for input in [include_bytes!("/Volumes/dev_src_case_sensitive/projects/patamaps/fixtures/routing/graph.json").as_slice(),include_bytes!("/Volumes/dev_src_case_sensitive/projects/patamaps/fixtures/topology/graph.json").as_slice(),include_bytes!("/Volumes/dev_src_case_sensitive/projects/patamaps/fixtures/laws/graph.json").as_slice()] { graph(input); }
  let input=include_bytes!("/Volumes/dev_src_case_sensitive/projects/patamaps/fixtures/laws/pack.json");
  let a:alpha::RelationPack=alpha::parse(input).unwrap(); let b:current::RelationPack=current::parse(input).unwrap();
  let x=alpha::canonical_bytes(&a).unwrap();let y=current::canonical_bytes(&b).unwrap();assert_eq!(x,y);
  assert!(alpha::parse::<alpha::RelationPack>(&y).is_ok());assert!(current::parse::<current::RelationPack>(&x).is_ok());
 }
 #[test] fn strict_graph_rejections_match() {
  for input in [br#"{"schemaVersion":"0.1.0","documentType":"graph","id":"urn:a","id":"urn:b","namespace":"test","entities":[],"mappings":[],"authorities":[]}"#.as_slice(),br#"{"schemaVersion":"0.1.0","documentType":"graph","id":"urn:a","namespace":"test","label":null,"entities":[],"mappings":[],"authorities":[]}"#.as_slice(),br#"{"schemaVersion":"0.1.0","documentType":"graph","id":"urn:a","namespace":"test","unknown":true,"entities":[],"mappings":[],"authorities":[]}"#.as_slice()] {
   assert!(alpha::parse::<alpha::GraphDocument>(input).is_err());assert!(current::parse::<current::GraphDocument>(input).is_err());
  }
 }
}
