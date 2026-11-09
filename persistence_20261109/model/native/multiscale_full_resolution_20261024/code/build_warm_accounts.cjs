/* Actual core-computed fixed-roof/static-climate REF accounts:42 real cases.
 * This is a bounded startup cache, not a relabelled or complete selector grid.
 */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
const {readNpz}=require('./benchmark_core_native.cjs');
const ROOT=path.resolve(__dirname,'..'),CROOT=path.dirname(ROOT),SRC=path.join(ROOT,'source_data'),OUT=path.join(ROOT,'outputs'),DEST=path.join(OUT,'warm_accounts');fs.mkdirSync(DEST,{recursive:true});
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const manifest=read(path.join(SRC,'native_cdf_manifest.json'));
function coarseStats(parent){
 const N=parent.N,offsets=Float64Array.from({length:N+1},(_,i)=>i),Y=Float64Array.from({length:N},(_,i)=>parent.Yold[i]/parent.Fold[i]);
 const area=new Float64Array(parent.area),sumAY=Float64Array.from(Y,(y,i)=>y*area[i]),rho=new Float64Array(parent.rho),w1=Float64Array.from(rho,(r,i)=>r*sumAY[i]);
 const parentOffsets=new Float64Array(N+1),op=[],due=[],oy=[],oa=[];
 for(let i=0;i<N;i++){parentOffsets[i]=op.length;if(parent.u0[i]>0){op.push(i);due.push(parent.batDue[i]);oy.push(Y[i]);oa.push(area[i]);}}parentOffsets[N]=op.length;
 const opening={parentOffsets,parent:Float64Array.from(op),due:Float64Array.from(due),offsets:Float64Array.from({length:op.length+1},(_,i)=>i),x:Float64Array.from(oy),area:Float64Array.from(oa),prefixA:Float64Array.from(oa),prefixAY:Float64Array.from(oy,(y,i)=>y*oa[i])};
 const joint={...opening,rho:Float64Array.from(op,i=>rho[i])};
 const yieldCDF={offsets,x:Y,area,prefixA:area,prefixAY:sumAY};
 return {parent:{...parent,allocatedArea:area,sumAY,minY:Y,maxY:Y,minRho:rho,maxRho:rho},stats:{N,resolution:'legacy1deg',rho:{offsets,x:rho,w:sumAY,w1,prefixW:sumAY,prefixW1:w1},yield:yieldCDF,opening,jointUTIL0:joint}};
}
function checkAccount(p){const near=(a,b)=>assert(Math.abs(a-b)<1e-10+1e-11*Math.max(Math.abs(a),Math.abs(b)),a+' != '+b);const n=p.countries.C.length;
 for(let t=0;t<76;t++){let C=0,A=0,H=0,negative=0;
  for(let c=0;c<n;c++){const f=p.annualCountry;near(f.H[c][t],f.newManufacturing[c][t]+f.replacementManufacturing[c][t]+f.treatment[c][t]+f.gridAux[c][t]);near(f.net[c][t],f.H[c][t]-f.A[c][t]);near(p.countries.C[c][t],(t?p.countries.C[c][t-1]:0)+f.net[c][t]);C+=p.countries.C[c][t];A+=p.countries.A[c][t];H+=p.countries.H[c][t];negative+=p.countries.C[c][t]<0?1:0;}
  near(C,p.global.C[t]);near(A,p.global.A[t]);near(H,p.global.H[t]);assert.equal(negative,p.global.negative[t]);}
 for(const field of ['A','H','C'])near(p.bubble.regions.reduce((s,r)=>s+r[field],0),p.global[field].at(-1));
 assert.equal(p.bubble.regions.reduce((s,r)=>s+r.n,0),231);assert.equal(Object.values(p.trajectorySummary.counts).reduce((a,b)=>a+b,0)+p.trajectorySummary.allZero,231);
}
async function main(){const began=Date.now(),w={};vm.runInNewContext(fs.readFileSync(path.join(OUT,'parent_inputs.js'),'utf8'),{window:w});const packed=w.NATIVE_FULL_INPUTS.parent_inputs,oldw={};vm.runInNewContext(fs.readFileSync(path.join(CROOT,'mainpage_roof_climate_integration_20261021/outputs/base_inputs.js'),'utf8'),{window:oldw});const old=oldw.INTEGRATED_BASE_INPUTS;
 const parent={...packed,...readNpz(path.join(SRC,'parent_inputs.npz')),countries:old.countries,regions:old.regions,regions12:old.regions12,countryTo12:old.countryTo12};delete parent.arrays;
 const native={parent,stats:{N:parent.N,resolution:'native1km',rho:readNpz(path.join(SRC,'native_rho.npz')),opening:readNpz(path.join(SRC,'native_opening.npz')),loadYield:async()=>readNpz(path.join(SRC,'native_yield.npz')),loadJointUTIL0:async()=>readNpz(path.join(SRC,'native_util0_joint.npz'))}};
 const common=read(path.join(SRC,'common_parameter_registry.json')),registry={resolved:read(path.join(SRC,'resolved_parameters_by_pair.json')),storageAliases:common.storageAliases,reference_account_id:'STORAGE_REF_LFP_20261023'},iam=read(path.join(SRC,'iam_inputs.json')),cat=read(path.join(SRC,'full_catalog.json'));
 const coreFile=path.join(OUT,'full_resolution_core.js'),sources=[coreFile,__filename,path.join(SRC,'parent_inputs.npz'),path.join(SRC,'native_rho.npz'),path.join(SRC,'native_opening.npz'),path.join(SRC,'common_parameter_registry.json'),path.join(SRC,'resolved_parameters_by_pair.json'),path.join(SRC,'iam_inputs.json')];
 const sourceHashes=Object.fromEntries(sources.map(file=>[file,sha(file)]));
 const {createCore}=require(coreFile),files={},accounts=[];
 for(const resolution of ['native1km','legacy1deg']){
  const context=resolution==='native1km'?native:coarseStats(parent),core=createCore({...context,registry,iam,climates:{roofRatios:cat.roofRatios,weatherRatios:{}}});
  for(const model of iam.models)for(const background of ['CP','NDC','NZ2050','B2C','DT','FW','LD']){
   const s={resolution,iam:model.id,background,storage:'REF',life:'REF',roof:'FIXED',climate:'CLEAN_CONTROL',model:null};
   const account=await core.compute(s);checkAccount(account);
   account.provenance={...account.provenance,warm_cache:true,warm_scope:'Fixed2020roof/staticcleanclimate/REFdevices; actual model-specific annual carbon evaluation',sourceHashes};
   const id=account.key.replace(/[^A-Za-z0-9_]/g,'_'),file='warm_accounts/'+id+'.js',destination=path.join(OUT,file);
   const script='window.NATIVE_FULL_WARM_ACCOUNTS=window.NATIVE_FULL_WARM_ACCOUNTS||{};window.NATIVE_FULL_WARM_ACCOUNTS['+JSON.stringify(account.key)+']='+JSON.stringify(account)+';\n';fs.writeFileSync(destination,script);
   files[account.key]=file;accounts.push({key:account.key,file,sha256:sha(destination),bytes:Buffer.byteLength(script),selection:account.selection,C2100_Gt:account.global.C.at(-1),negative:account.global.negative.at(-1)});
   console.log(JSON.stringify({computed:accounts.length,resolution,iam:model.id,background,C2100_Gt:account.global.C.at(-1),elapsed_ms:Date.now()-began}));
  }
 }
 assert.equal(accounts.length,42);const ref=accounts.find(a=>a.selection.resolution==='native1km'&&a.selection.iam==='REMIND'&&a.selection.background==='CP');assert(Math.abs(ref.C2100_Gt+32.928802182824896)<1e-8);assert.equal(ref.negative,158);
 for(const [file,digest]of Object.entries(sourceHashes))assert.equal(sha(file),digest,'Warm source changed during generation');
 const catalog={schema:'pv-wrf-exact-42-account-warm-cache/1.0',status:'PASS',files,accounts,core_sha256:sourceHashes[coreFile],sourceHashes,scope:'42 actual core-computed REF/REF/FIXED/CLEAN_CONTROL accounts, both resolutions, all3IAM×7backgrounds; all other selectors remain exact on demand',date_local:'2026-10-24',no_source_relabelling:true,all_annual_and_cumulative_closure_passed:true,wall_ms:Date.now()-began};
 fs.writeFileSync(path.join(OUT,'warm_catalog.js'),'window.FULL_RESOLUTION_WARM_CATALOG='+JSON.stringify(catalog)+';\n');fs.writeFileSync(path.join(SRC,'warm_account_checks.json'),JSON.stringify(catalog,null,2));console.log(JSON.stringify({status:'PASS',accounts:42,core_sha256:catalog.core_sha256,wall_ms:catalog.wall_ms}));
}
if(require.main===module)main().catch(e=>{fs.writeFileSync(path.join(SRC,'warm_account_checks.json'),JSON.stringify({status:'FAIL',error:e.message,stack:e.stack},null,2));console.error(e.stack);process.exitCode=1;});
module.exports={coarseStats,checkAccount};
