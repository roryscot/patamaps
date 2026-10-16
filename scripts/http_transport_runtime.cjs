const http=require('node:http');
const assert=require('node:assert/strict');
const api=require(process.argv[2]);
const backend=process.argv[3], prefix='urn:transport:operation:';
const rows=[],traces=[];
let wrongProxy=false;
const jsonHeaders={'content-type':'application/json'};
async function failure(label,code,fn){
 try{await fn();throw new Error(label+': unexpectedly succeeded');}
 catch(error){assert.equal(error.message,code,label);rows.push({label,result:'refused',code});}
}
(async()=>{
 const proxy=http.createServer(async(req,res)=>{
  try {
   const chunks=[];for await(const chunk of req)chunks.push(chunk);
   const raw=Buffer.concat(chunks).toString('utf8');
   const url=new URL(req.url,'http://loopback.invalid');
   let path;
   if(url.pathname==='/api/evaluate'){
    const body=JSON.parse(raw);
    path=wrongProxy?'/evaluate':Object.hasOwn(body,'expected_report')?'/replay':'/evaluate';
   } else if(url.pathname==='/api/scalars'){path='/scalars';
   } else if(url.pathname.startsWith('/api/items/')){
    const id=decodeURIComponent(url.pathname.slice('/api/items/'.length));
    path='/items/'+encodeURIComponent(id)+url.search;
   } else if(url.pathname==='/api/health'){path='/health';}
   else {res.writeHead(404,jsonHeaders);res.end('{}');return;}
   traces.push({method:req.method,frontend:url.pathname,backend:path});
   const headers={};
   if(req.headers['content-type'])headers['content-type']=req.headers['content-type'];
   if(req.headers['x-proof'])headers['x-proof']=req.headers['x-proof'];
   const response=await fetch(backend+path,{method:req.method,headers,body:raw||undefined});
   res.writeHead(response.status,{'content-type':response.headers.get('content-type')??'application/json'});
   if(req.method==='HEAD'){res.end();return;}
   res.end(Buffer.from(await response.arrayBuffer()));
  }catch(error){res.writeHead(502,jsonHeaders);res.end(JSON.stringify({error:'proxy-failure',issues:[]}));}
 });
 await new Promise(resolve=>proxy.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+proxy.address().port;
 try {
  for(const endpoint of ['backend','frontend']){
   const origin=endpoint==='backend'?backend:base;
   for(const [operation,input,kind,value] of [
    ['evaluate',{message:'hello'},'evaluate','hello'],
    ['replay',{expected_report:'record'},'replay','record']
   ]){
    const result=await api.callOperation(prefix+operation,input,{base:origin,endpoint});
    assert.equal(result.status,200);
    assert.equal(result.body.state,'owned-state');
    assert.equal(result.body.kind,kind);assert.equal(result.body.value,value);
    rows.push({label:endpoint+'-'+operation,status:result.status,kind:result.body.kind});
   }
   const large=await api.callOperation(prefix+'evaluate',{message:'z'.repeat(16000)},{base:origin,endpoint});
   assert.equal(large.status,200);assert.equal(large.body.value.length,16000);
   rows.push({label:endpoint+'-above-fixture-limit',status:large.status,bytes:16000});
   const failed=await api.callOperation(prefix+'evaluate',{message:'hello',fail:true},{base:origin,endpoint});
   assert.equal(failed.status,400);assert.equal(failed.body.error,'domain-refusal');assert.equal(failed.body.issues[0].path,'$');
   rows.push({label:endpoint+'-structured-error',status:400,issues:failed.body.issues.length});
   for(const method of ['get','put','patch']){
    const id='a/b ☃%';
    const result=await api.callOperation(prefix+method+'-item',null,{base:origin,endpoint,path:{id},query:{limit:3,verbose:false},headers:{'x-proof':'allow'}});
    assert.equal(result.status,200);assert.equal(result.body.value,id);
    assert.equal(result.body.limit,3);assert.equal(result.body.verbose,false);
    assert.equal(result.body.state,'owned-state');
    if(endpoint==='frontend')assert.equal(traces.at(-1).method,method.toUpperCase());
    rows.push({label:endpoint+'-'+method+'-parameters',status:200,id,limit:3,verbose:false});
   }
   const removed=await api.callOperation(prefix+'delete-item',null,{base:origin,endpoint,path:{id:'x'}});
   assert.equal(removed.status,204);assert.equal(removed.body,null);
   if(endpoint==='frontend')assert.equal(traces.at(-1).method,'DELETE');
   rows.push({label:endpoint+'-delete-no-content',status:204});
   for(const method of ['get','head','options']){
    const result=await api.callOperation(prefix+method+'-health',null,{base:origin,endpoint});
    assert.equal(result.status,200);
    if(method==='head')assert.equal(result.body,null);else assert.equal(result.body.ok,true);
    if(endpoint==='frontend')assert.equal(traces.at(-1).method,method.toUpperCase());
    rows.push({label:endpoint+'-'+method+'-health',status:200});
   }
  }
  // Frozen scalar cases exercise generated validators and real Rust Serde transport.
  const scalar={uuid:'00112233-4455-6677-8899-AABBCCDDEEFF',quantity:'18446744073709551616000000000000000000000',count:Number.MAX_SAFE_INTEGER,delta:-Number.MAX_SAFE_INTEGER};
  for(const endpoint of ['backend','frontend']){
   for(const [label,body] of [['safe-bounds',scalar],['zero',{...scalar,count:0,delta:0,quantity:'0'}]]){
    const result=await api.callOperation(prefix+'scalars',body,{base:endpoint==='backend'?backend:base,endpoint});
    assert.equal(result.status,200);assert.deepEqual(result.body,body);
    rows.push({label:endpoint+'-scalars-'+label,status:200,quantityPreserved:result.body.quantity===body.quantity});
   }
  }
  const scalarBad=[
   ['unsafe-count',{count:Number.MAX_SAFE_INTEGER+1}],['negative-count',{count:-1}],
   ['fractional-count',{count:1.5}],['unsafe-delta',{delta:-Number.MAX_SAFE_INTEGER-1}],
   ['uuid-short',{uuid:'00112233'}],['uuid-nonhex',{uuid:'g0112233-4455-6677-8899-aabbccddeeff'}],
   ['uuid-no-hyphens',{uuid:'00112233445566778899aabbccddeeff'}],['uuid-newline',{uuid:scalar.uuid+'\n'}],
   ['quantity-empty',{quantity:''}],['quantity-leading-zero',{quantity:'01'}],
   ['quantity-sign',{quantity:'+1'}],['quantity-negative',{quantity:'-1'}],
   ['quantity-fraction',{quantity:'1.0'}],['quantity-exponent',{quantity:'1e3'}],
   ['quantity-newline',{quantity:'1\n'}],['quantity-unicode-digits',{quantity:'١'}],
  ];
  for(const [label,patch] of scalarBad){
   let reached=false;
   await failure('scalar-input-'+label,'HTTP_INVALID_REQUEST',()=>api.callOperation(prefix+'scalars',{...scalar,...patch},{base:backend,transport:async()=>{reached=true;throw new Error('unexpected fetch');}}));
   assert.equal(reached,false);
   await failure('scalar-response-'+label,'HTTP_RESPONSE_CONTRACT',()=>api.callOperation(prefix+'scalars',scalar,{base:backend,transport:async()=>new Response(JSON.stringify({...scalar,...patch}),{status:200,headers:jsonHeaders})}));
  }
  const serdeNegative=await fetch(backend+'/scalars',{method:'POST',headers:jsonHeaders,body:JSON.stringify({...scalar,count:-1})});
  assert.equal(serdeNegative.status,422);
  rows.push({label:'scalar-rust-negative-u64',status:422});
  const denied=await api.callOperation(prefix+'get-item',null,{base:backend,endpoint:'backend',path:{id:'x'},headers:{'x-proof':'deny'}});
  assert.equal(denied.status,400);assert.equal(denied.body.error,'header-refusal');
  rows.push({label:'header-domain-refusal',status:400});
  const over=await fetch(backend+'/evaluate',{method:'POST',headers:jsonHeaders,body:JSON.stringify({message:'z'.repeat(66000)})});
  assert.equal(over.status,413);const overBody=await over.json();assert.ok(Array.isArray(overBody.issues));
  rows.push({label:'actual-axum-body-limit',status:413});
  wrongProxy=true;
  const wrong=await api.callOperation(prefix+'replay',{expected_report:'record'},{base,endpoint:'frontend'});
  assert.equal(wrong.status,422);assert.equal(traces.at(-1).backend,'/evaluate');
  rows.push({label:'wrong-proxy-branch',status:422,actualBackend:'/evaluate'});
  wrongProxy=false;
  const recovered=await api.callOperation(prefix+'replay',{expected_report:'record'},{base,endpoint:'frontend'});
  assert.equal(recovered.status,200);assert.equal(recovered.body.kind,'replay');
  rows.push({label:'proxy-branch-restored',status:200});
  let fetched=false;
  const forbidden=async()=>{fetched=true;throw new Error('Unexpected transport call');};
  await failure('missing-path','HTTP_INVALID_REQUEST',()=>api.callOperation(prefix+'get-item',null,{base:backend,endpoint:'backend',headers:{'x-proof':'allow'},transport:forbidden}));
  await failure('fractional-query','HTTP_INVALID_REQUEST',()=>api.callOperation(prefix+'get-item',null,{base:backend,path:{id:'x'},query:{limit:1.5},headers:{'x-proof':'allow'},transport:forbidden}));
  await failure('extra-query','HTTP_INVALID_REQUEST',()=>api.callOperation(prefix+'get-item',null,{base:backend,path:{id:'x'},query:{extra:'x'},headers:{'x-proof':'allow'},transport:forbidden}));
  await failure('path-dot-segment','HTTP_INVALID_PATH',()=>api.callOperation(prefix+'get-item',null,{base:backend,path:{id:'..'},headers:{'x-proof':'allow'},transport:forbidden}));
  await failure('header-injection','HTTP_INVALID_HEADERS',()=>api.callOperation(prefix+'get-item',null,{base:backend,path:{id:'x'},headers:{'x-proof':'allow\r\nx-extra: bad'},transport:forbidden}));
  await failure('utf8-byte-limit','HTTP_INPUT_LIMIT',()=>api.callOperation(prefix+'evaluate',{message:'😀'.repeat(17000)},{base:backend,transport:forbidden}));
  await failure('ascii-byte-limit','HTTP_INPUT_LIMIT',()=>api.callOperation(prefix+'evaluate',{message:'z'.repeat(66000)},{base:backend,transport:forbidden}));
  assert.equal(fetched,false,'Refused input reached transport');
  await failure('content-type','HTTP_CONTENT_TYPE',()=>api.callOperation(prefix+'get-health',null,{base:backend,transport:async()=>new Response('{}',{status:200,headers:{'content-type':'text/plain'}})}));
  await failure('response-shape','HTTP_RESPONSE_CONTRACT',()=>api.callOperation(prefix+'get-health',null,{base:backend,transport:async()=>new Response('{"ok":"x"}',{status:200,headers:jsonHeaders})}));
  await failure('error-shape','HTTP_ERROR_CONTRACT',()=>api.callOperation(prefix+'evaluate',{message:'x'},{base:backend,transport:async()=>new Response('{"error":"x"}',{status:400,headers:jsonHeaders})}));
  await failure('invalid-utf8','HTTP_INVALID_JSON',()=>api.callOperation(prefix+'get-health',null,{base:backend,transport:async()=>new Response(new Uint8Array([255]),{status:200,headers:jsonHeaders})}));
  let cancelled=false;
  await failure('bounded-response-stream','HTTP_RESPONSE_LIMIT',()=>api.callOperation(prefix+'get-health',null,{base:backend,transport:async()=>new Response(new ReadableStream({start(controller){controller.enqueue(new Uint8Array(17));},cancel(){cancelled=true;}}),{status:200,headers:jsonHeaders})}));
  assert.equal(cancelled,true,'Oversized response was not cancelled');
  const controller=new AbortController();controller.abort();
  try{await api.callOperation(prefix+'get-health',null,{base:backend,endpoint:'backend',signal:controller.signal});throw new Error('abort was ignored');}
  catch(error){assert.equal(error.name,'AbortError');rows.push({label:'abort-signal',result:'cancelled',code:'AbortError'});}
  console.log(JSON.stringify(rows));
 } finally {proxy.closeAllConnections();await new Promise(resolve=>proxy.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
