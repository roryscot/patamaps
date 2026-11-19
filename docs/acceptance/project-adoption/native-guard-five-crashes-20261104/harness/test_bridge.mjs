import test from 'node:test';import assert from 'node:assert/strict';
import{closedInspectionStopped,createRegisteredGuardInvocation,consumeRegisteredGuardInvocation}from'/Volumes/dev_src_case_sensitive/projects/patamaps/.tools/native-guard-candidate-parent-watch-20261104/engine/native_registered_guard_candidate.mjs';
const binding={kind:'registered',manifestSha256:'pinned',qualifiedHost:{build:'qualified'}};
const good=()=>({registeredStagedSource:true,binding:structuredClone(binding),ownership:{ownershipKnown:true,allRegisteredStopped:true,channelClosed:true,protocolFailure:null,probeError:null},dataStreamsClosed:true});
test('complete concrete closed evidence permits staged stop only',()=>assert.equal(closedInspectionStopped(good(),binding),true));
for(const field of ['ownershipKnown','allRegisteredStopped','channelClosed']){
 test('incomplete '+field+' retains uncertainty',()=>{const r=good();r.ownership[field]=false;assert.equal(closedInspectionStopped(r,binding),false);});
}
for(const field of ['protocolFailure','probeError']){
 test(field+' retains uncertainty',()=>{const r=good();r.ownership[field]='unknown';assert.equal(closedInspectionStopped(r,binding),false);});
}
test('data-stream closure is independently required',()=>{const r=good();r.dataStreamsClosed=false;assert.equal(closedInspectionStopped(r,binding),false);});
test('changed manifest refuses',()=>{const r=good();r.binding.manifestSha256='changed';assert.equal(closedInspectionStopped(r,binding),false);});
test('changed qualified host refuses',()=>{const r=good();r.binding.qualifiedHost.build='changed';assert.equal(closedInspectionStopped(r,binding),false);});
test('zero exit cannot replace registration',()=>assert.equal(closedInspectionStopped({exit:{code:0}},binding),false));
test('caller automatic-release flag cannot replace concrete proof',()=>assert.equal(closedInspectionStopped({automaticReservationReleaseQualified:true},binding),false));
test('missing initial registration cannot compare equal',()=>assert.equal(closedInspectionStopped(good(),{}),false));
test('forged invocation cannot be consumed',()=>assert.throws(()=>consumeRegisteredGuardInvocation({kind:'patamaps-staged-guard-inspection-v1'}),/unregistered-or-reused/));
test('forged registration cannot create invocation',()=>assert.throws(()=>createRegisteredGuardInvocation({kind:'patamaps-staged-native-registration-v1'},{operation:'engine',runRoot:'/owned',inputs:{}}),/unregistered-inspection-capability/));
