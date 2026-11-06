import test from 'node:test';import assert from 'node:assert/strict';
import{closedInspectionStopped as rawClosedInspectionStopped,normalInspectionSealed,createRegisteredGuardInvocation,consumeRegisteredGuardInvocation}from'./native_registered_guard_candidate.mjs';
const binding={kind:'registered',manifestSha256:'pinned',qualifiedHost:{build:'qualified'}};
const good=()=>({registeredStagedSource:true,binding:structuredClone(binding),ownership:{ownershipKnown:true,allRegisteredStopped:true,channelClosed:true,protocolFailure:null,probeError:null},dataStreamsClosed:true,exit:{code:0,signal:null}});
const sealed=()=>({version:1,channelClosed:true,failure:null,controllerOutcome:{code:0,signal:null},calls:[{registrationKnown:true,innerCount:3,nextSequence:6,finished:true,controlComplete:true,terminalFlags:{stdoutClosed:true,stderrClosed:true,bindingsUnchanged:true}}]});
const closedInspectionStopped=(result,initial,status=sealed())=>rawClosedInspectionStopped(result,initial,status);
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

test('zero exit without observed normal status retains uncertainty',()=>assert.equal(rawClosedInspectionStopped(good(),binding),false));
test('failed operation may release known stopped ownership without success seal',()=>{const r=good();r.exit={code:75,signal:null};assert.equal(rawClosedInspectionStopped(r,binding,{calls:[]}),true);});
test('signaled controller may release known stopped ownership without success seal',()=>{const r=good();r.exit={code:null,signal:'SIGKILL'};assert.equal(rawClosedInspectionStopped(r,binding,{calls:[]}),true);});
test('unknown controller outcome retains uncertainty',()=>{const r=good();delete r.exit;assert.equal(closedInspectionStopped(r,binding),false);});
for(const field of ['finished','controlComplete','registrationKnown']){
 test('normal-success missing '+field+' retains resources',()=>{const status=sealed();status.calls[0][field]=false;assert.equal(normalInspectionSealed(status),false);assert.equal(closedInspectionStopped(good(),binding,status),false);});
}
for(const[field,value]of [['innerCount',2],['nextSequence',5]]){
 test('normal-success incomplete '+field+' retains resources',()=>{const status=sealed();status.calls[0][field]=value;assert.equal(closedInspectionStopped(good(),binding,status),false);});
}
for(const field of ['stdoutClosed','stderrClosed','bindingsUnchanged']){
 test('normal-success missing terminal '+field+' retains resources',()=>{const status=sealed();status.calls[0].terminalFlags[field]=false;assert.equal(closedInspectionStopped(good(),binding,status),false);});
}
test('observed controller result must agree with normal success',()=>{const status=sealed();status.controllerOutcome.code=75;assert.equal(closedInspectionStopped(good(),binding,status),false);});
test('normal success with no observed call retains uncertainty',()=>{const status=sealed();status.calls=[];assert.equal(closedInspectionStopped(good(),binding,status),false);});
test('paired watch verification requires exactly two sealed calls',()=>{
 const status=sealed();
 assert.equal(rawClosedInspectionStopped(good(),binding,status,2),false);
 status.calls.push(structuredClone(status.calls[0]));
 assert.equal(rawClosedInspectionStopped(good(),binding,status,2),true);
 assert.equal(rawClosedInspectionStopped(good(),binding,status),false);
 status.calls[1].controlComplete=false;
 assert.equal(rawClosedInspectionStopped(good(),binding,status,2),false);
 status.calls[1].controlComplete=true;
 status.calls.push(structuredClone(status.calls[0]));
 assert.equal(rawClosedInspectionStopped(good(),binding,status,2),false);
});
