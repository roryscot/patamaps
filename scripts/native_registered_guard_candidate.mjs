// Proposed staged integration only. No installed guard or trust activation.
import {
 verifyInspectionRegistration,startRegisteredInspection,registeredInspectionStatus,
 stopRegisteredInspection,finishRegisteredInspection,
} from './native_inspection_registration.mjs';
const capabilities=new WeakMap();
const need=(condition,message)=>{if(!condition)throw Error(message);};
export function closedInspectionStopped(result,initialBinding){
 return result?.registeredStagedSource===true&&
  typeof initialBinding?.manifestSha256==='string'&&
  initialBinding.qualifiedHost!==null&&typeof initialBinding.qualifiedHost==='object'&&
  result.binding?.manifestSha256===initialBinding.manifestSha256&&
  result.binding?.kind===initialBinding.kind&&
  JSON.stringify(result.binding?.qualifiedHost)===JSON.stringify(initialBinding.qualifiedHost)&&
  result.ownership?.ownershipKnown===true&&
  result.ownership?.allRegisteredStopped===true&&
  result.ownership?.channelClosed===true&&
  result.ownership?.protocolFailure===null&&
  result.ownership?.probeError===null&&result.dataStreamsClosed===true;
}
export function createRegisteredGuardInvocation(registration,options){
 // The existing registrar accepts only hardcoded source/archive/native identities.
 // A copied handle or caller-provided digest cannot reach this point.
 const binding=verifyInspectionRegistration(registration);
 need(options&&Object.keys(options).sort().join(',')==='inputs,operation,runRoot','closed-guard-inspection-options');
 need(['engine','input-key','unchanged-build'].includes(options.operation),'closed-guard-inspection-operation');
 const cloned=structuredClone(options);
 need(JSON.stringify(cloned)===JSON.stringify(options),'closed-guard-inspection-values');
 const handle=Object.freeze({kind:'patamaps-staged-guard-inspection-v1'});
 capabilities.set(handle,{registration,options:cloned,binding});
 return handle;
}
export function consumeRegisteredGuardInvocation(handle){
 const value=capabilities.get(handle);
 need(value,'unregistered-or-reused-guard-inspection');
 capabilities.delete(handle);
 verifyInspectionRegistration(value.registration);
 let inspection=null,completion=null,terminal=null,stopPromise=null,observer=null;
 let attempted=false,observerFailure=null;
 const publish=callback=>{
  if(!inspection)return;
  const snapshot=registeredInspectionStatus(inspection);
  try{callback?.(snapshot);}catch(error){observerFailure=String(error.message).slice(0,240);void api.stop().catch(()=>{});}
 };
 const api={
  async start(callback){
   need(!attempted,'guard-inspection-already-started');attempted=true;
   inspection=await startRegisteredInspection(value.registration,value.options);
   let last='';
   observer=setInterval(()=>{
    const snapshot=registeredInspectionStatus(inspection),encoded=JSON.stringify(snapshot);
    if(encoded!==last){last=encoded;publish(callback);}
   },100);
   observer.unref();
   const child=inspection.child;
   const exited=child.exitCode!==null||child.signalCode!==null?Promise.resolve():
    new Promise(resolve=>child.once('exit',resolve));
   completion=(async()=>{
    await exited;
    let timer;
    try{
     const result=await Promise.race([
      finishRegisteredInspection(inspection),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('registered-final-proof-deadline')),30000);timer.unref();}),
     ]);
     terminal={safeToRelease:observerFailure===null&&closedInspectionStopped(result,value.binding),observerFailure,
      controllerExitCode:result.exit?.code??1,controllerSignal:result.exit?.signal??null,
      outputError:result.outputError,ownership:result.ownership,
      binding:result.binding,dataStreamsClosed:result.dataStreamsClosed};
     return {code:result.outputError?1:(result.exit?.code??1),childSignal:result.exit?.signal??null,
      stdout:result.stdout,stderr:result.stderr};
    }catch(error){
     terminal={safeToRelease:false,failure:String(error.message).slice(0,240)};
     return {code:1,childSignal:child.signalCode??null,stdout:Buffer.alloc(0),stderr:Buffer.alloc(0)};
    }finally{
     clearTimeout(timer);clearInterval(observer);publish(callback);
    }
   })();
   publish(callback);
   return child;
  },
  async stop(){
   if(!inspection)return {confirmedStopped:false};
   stopPromise??=stopRegisteredInspection(inspection);
   return stopPromise;
  },
  async result(){
   need(completion,'guard-inspection-not-started');return completion;
  },
  async closed(){
   need(completion,'guard-inspection-not-started');await completion;
   return observerFailure===null&&terminal?.safeToRelease===true;
  },
  status(){return structuredClone({...terminal,safeToRelease:observerFailure===null&&terminal?.safeToRelease===true,launchAttempted:attempted,observerFailure});},
 };
 return Object.freeze(api);
}
