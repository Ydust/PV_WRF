'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const job=path.resolve(__dirname,'..'),root=path.dirname(job),full=path.join(root,'multiscale_full_resolution_20261024'),src=path.join(full,'source_data'),out=path.join(job,'outputs');
const {readNpz}=require(path.join(full,'code/benchmark_core_native.cjs'));
const {coarseStats,checkAccount}=require(path.join(full,'code/build_warm_accounts.cjs'));
const read=f=>JSON.parse(fs.readFileSync(f,'utf8')),sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
function contexts(){
 const w={};vm.runInNewContext(fs.readFileSync(path.join(full,'outputs/parent_inputs.js'),'utf8'),{window:w});const packed=w.NATIVE_FULL_INPUTS.parent_inputs;delete packed.arrays;
 const cat=read(path.join(src,'full_catalog.json')),parent={...packed,...readNpz(path.join(src,'parent_inputs.npz')),countries:cat.countries,regions:cat.regions,regions12:cat.regions12,countryTo12:cat.countryTo12};
 const common=read(path.join(src,'common_parameter_registry.json')),registry={resolved:read(path.join(src,'resolved_parameters_by_pair.json')),storageAliases:common.storageAliases,reference_account_id:'STORAGE_REF_LFP_20261023'},iam=read(path.join(src,'iam_inputs.json'));
 const native={parent,stats:{N:parent.N,resolution:'native1km',rho:readNpz(path.join(src,'native_rho.npz')),opening:readNpz(path.join(src,'native_opening.npz')),loadYield:async()=>readNpz(path.join(src,'native_yield.npz')),loadJointUTIL0:async()=>readNpz(path.join(src,'native_util0_joint.npz'))}};
 return {native,coarse:coarseStats(parent),registry,iam,cat};
}
function checkEnergy(p){
 const near=(a,b)=>assert(Math.abs(a-b)<=1e-6+1e-8*Math.max(Math.abs(a),Math.abs(b)),a+' != '+b);
 for(let c=0;c<231;c++)for(let t=0;t<76;t++){
  const e=Object.fromEntries(Object.entries(p.energyCountry).map(([k,v])=>[k,v===null?null:v[c][t]]));
  for(const [k,v]of Object.entries(e))if(v!==null)assert(Number.isFinite(v)&&v>=0,k+':invalid');
  near(e.generation,e.useful+e.loss+e.pvAux+e.curtailment);near(e.charge,e.discharge+e.loss);
 }
 for(const [k,a]of Object.entries(p.energyCountry))if(a!==null)for(let t=0;t<76;t++)near(a.reduce((s,row)=>s+row[t],0),p.energyGlobal[k][t]);
}
async function main(){
 fs.mkdirSync(out,{recursive:true});fs.mkdirSync(path.join(out,'warm_accounts'),{recursive:true});fs.mkdirSync(path.join(job,'source_data'),{recursive:true});
 const all=contexts(),{createCore}=require(path.join(out,'full_resolution_core.js')),files={},accounts=[],began=Date.now();
 const smoke=process.argv.includes('--smoke'),resolutions=smoke?['legacy1deg']:['native1km','legacy1deg'],storages=smoke?['REF']:['REF','FC0','FC100'];
 const sources=[path.join(out,'full_resolution_core.js'),path.join(src,'parent_inputs.npz'),path.join(src,'native_rho.npz'),path.join(src,'native_opening.npz'),path.join(src,'resolved_parameters_by_pair.json'),path.join(src,'iam_inputs.json')],sourceHashes=Object.fromEntries(sources.map(f=>[f,sha(f)]));
 const hardwareByStorage=new Map();
 for(const resolution of resolutions){
  const context=resolution==='native1km'?all.native:all.coarse,core=createCore({...context,registry:all.registry,iam:all.iam,climates:{roofRatios:all.cat.roofRatios,weatherRatios:{}}});
  for(const storage of storages)for(const exportConstraint of ['UNLIMITED','CAP50','CAP25','CAP0']){
   let referenceQuantity=null;
   for(const iam of smoke?['REMIND']:['REMIND','GCAM','MESSAGE'])for(const background of smoke?['CP']:['CP','NDC','NZ2050','B2C','DT','FW','LD']){
    const selection={resolution,storage,exportConstraint,iam,background,roof:'FIXED',climate:'CLEAN_CONTROL',model:null,life:'REF'},start=Date.now();
    const p=await core.compute(selection);checkAccount(p);checkEnergy(p);
    const physics=await core.buildPhysical(selection),quantityHash=crypto.createHash('sha256');for(const a of Object.values(physics.quantity))quantityHash.update(Buffer.from(a.buffer,a.byteOffset,a.byteLength));
    const qhash=quantityHash.digest('hex');if(referenceQuantity!==null)assert.equal(qhash,referenceQuantity);referenceQuantity=qhash;
    const hardwareKey=resolution+'::'+storage;if(hardwareByStorage.has(hardwareKey))assert.equal(qhash,hardwareByStorage.get(hardwareKey),'Export constraint changed matched hardware');else hardwareByStorage.set(hardwareKey,qhash);
    if(exportConstraint==='UNLIMITED'&&storage==='REF'){
     const oldKey=p.key.split('::EX_')[0],w={};vm.runInNewContext(fs.readFileSync(path.join(full,'outputs/warm_accounts',oldKey.replace(/[^A-Za-z0-9_]/g,'_')+'.js'),'utf8'),{window:w});const old=w.NATIVE_FULL_WARM_ACCOUNTS[oldKey];
     for(const field of ['global','countries','annualCountry','annualGlobal','regions'])assert.equal(JSON.stringify(p[field]),JSON.stringify(old[field]),'Unlimited reference changed '+field);
     assert.equal(JSON.stringify(p.bubble.regions),JSON.stringify(old.bubble.regions));assert.equal(JSON.stringify(p.bubble.global),JSON.stringify(old.bubble.global));
    }
    const id=p.key.replace(/[^A-Za-z0-9_]/g,'_'),file='warm_accounts/'+id+'.js';
    p.provenance={...p.provenance,export_assumption_registry:'export_assumptions.json',matched_hardware:true,warm_cache:true,sourceHashes};
    const script='window.EXPORT_CONSTRAINT_WARM_ACCOUNTS=window.EXPORT_CONSTRAINT_WARM_ACCOUNTS||{};window.EXPORT_CONSTRAINT_WARM_ACCOUNTS['+JSON.stringify(p.key)+']='+JSON.stringify(p)+';\n';fs.writeFileSync(path.join(out,file),script);files[p.key]=file;
    accounts.push({key:p.key,file,bytes:Buffer.byteLength(script),sha256:sha(path.join(out,file)),selection,C2100_Gt:p.global.C.at(-1),negative:p.global.negative.at(-1),generation_TWh:p.energyGlobal.generation.reduce((a,b)=>a+b,0)/1e9,curtailment_TWh:p.energyGlobal.curtailment.reduce((a,b)=>a+b,0)/1e9,quantityHash:qhash});
    console.log(JSON.stringify({done:accounts.length,selection,C:p.global.C.at(-1),curtailment_TWh:accounts.at(-1).curtailment_TWh,ms:Date.now()-start,elapsed_ms:Date.now()-began}));
   }
  }
 }
 const catalog={schema:'pv-wrf-export-constraint-warm-cache/1.0',files,accounts,sourceHashes,date_local:'2026-10-26',scope:'Fixed2020roof/staticcleanclimate/REF lifetime, REF/FC0/FC100 storage; all4 export ×2resolution×3IAM×7background',wall_ms:Date.now()-began,status:'PASS'};
 fs.writeFileSync(path.join(out,smoke?'smoke_checks.json':'warm_catalog.js'),smoke?JSON.stringify(catalog,null,2):'window.EXPORT_CONSTRAINT_WARM_CATALOG='+JSON.stringify(catalog)+';\n');
 if(!smoke)fs.writeFileSync(path.join(job,'source_data/warm_account_checks.json'),JSON.stringify(catalog,null,2));
}
if(require.main===module)main().catch(e=>{console.error(e.stack);process.exitCode=1;});
module.exports={contexts,checkEnergy};
