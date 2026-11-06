import fs from'node:fs';
import {probe}from"/Volumes/dev_src_case_sensitive/projects/patamaps/scripts/selected_next_http_probe.mjs";
import {preflight,inspect}from"./auth-inspector.mjs";
const c=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
preflight(c);
await probe(c.http,x=>inspect(c,x));
preflight(c);
