// Authored fixture checks, independent of discovery output and graph hashes.
const assert = require('node:assert/strict');
const {callOperation, validRequest, validResponse, OPERATIONS} = require(process.argv[2]);
const frontend = process.argv[3];
const backend = process.argv[4];
(async () => {
  const id = 'urn:example:operation:create-item';
  assert.deepEqual(OPERATIONS.map(v => v.id), [id]);
  assert.deepEqual(await callOperation(id, {name: 'Widget'}, {base: frontend}),
    {status: 201, body: {id: 'item:widget', name: 'Widget'}});
  assert.deepEqual(await callOperation(id, {name: 'fail'}, {base: frontend}),
    {status: 500, body: {error: 'backend-failure'}});
  const unicode = '😀'.repeat(80);
  assert.deepEqual(await callOperation(id, {name: unicode}, {base: backend, endpoint: 'backend'}),
    {status: 201, body: {id: 'item:' + unicode, name: unicode}});
  assert.equal(validRequest(id, {name: '😀'.repeat(81)}), false);
  assert.equal(validRequest(id, {name: '\ud800'}), false);
  assert.equal(validRequest(id, {name: 'ok', extra: true}), false);
  assert.equal(validResponse(id, {id: 'item:ok'}), false);
  await assert.rejects(callOperation(id, {name: 'ok'}, {transport: async () =>
    new Response(JSON.stringify({id: 'item:ok'}), {status: 201})}), /HTTP_RESPONSE_CONTRACT/);
  await assert.rejects(callOperation(id, {name: 'ok'}, {transport: async () =>
    new Response(JSON.stringify({error: 'unowned-error'}), {status: 500})}), /HTTP_ERROR_CONTRACT/);
  console.log(JSON.stringify({status: 'passed', realNextRustRoundTrip: true,
    unicodeCodePointBoundary: true, malformedResponseRefused: true}));
})().catch(error => { console.error(error); process.exitCode = 1; });
