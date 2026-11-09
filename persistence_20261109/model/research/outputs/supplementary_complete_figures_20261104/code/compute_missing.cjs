'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto'),assert=require('assert');
const J=path.resolve(__dirname,'..'),R=path.resolve(__dirname,'../..').split(path.sep).join('/'),V=path.resolve(__dirname,'../../../native').split(path.sep).join('/');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\ufeff/,'')),unzip=p=>JSON.parse(zlib.gunzipSync(fs.readFileSync(p))),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const P=R+'/outputs/opening_balance_reference_cohorts_20261102',f=read(P+'/source_data/frozen_inputs.json'),cohorts=read(P+'/source_data/fixed_reference_cohorts.json');
const {classify}=require(P+'/code/classify.cjs');
const BGS=['CP','NDC','B2C','NZ2050','LD'],T=76;
function gainVector(p,codes){
 const gpv=p.pv_system_gain??1,ginv=p.inverter_gain??1,out=new Float64Array(codes.length*T);out.fill(1);if(gpv===1&&ginv===1)return out;
 for(let c=0;c<codes.length;c++){
  const components=f.components.filter(x=>x.code===codes[c]&&['PV_MODULE_AND_LINKED_BOS','INVERTER'].includes(x.device));
  const pv=components.filter(x=>x.device==='PV_MODULE_AND_LINKED_BOS'),invs=new Map(components.filter(x=>x.device==='INVERTER').map(x=>[x.cohort_id.replace(':INVERTER:',':PV_MODULE_AND_LINKED_BOS:'),x]));
  const total=pv.reduce((s,x)=>s+x.quantity,0);if(!total)continue;
  for(let t=0;t<T;t++){const y=2025+t;let sum=0;
   for(const x of pv){const i=invs.get(x.cohort_id);assert(i,'PV/inverter historical cohort join');const cuts=[y,y+1,...[x.next_due_time,i.next_due_time].filter(z=>z>y&&z<y+1)].sort((a,b)=>a-b);let value=0;
    for(let k=1;k<cuts.length;k++){let mid=(cuts[k]+cuts[k-1])/2;value+=(cuts[k]-cuts[k-1])*(mid>=x.next_due_time?gpv:1)*(mid>=i.next_due_time?ginv:1);}sum+=x.quantity*value;
   }out[c*T+t]=sum/total;
  }
 }return out;
}
function continuous(a,codes){
 const hist=new Map(f.history.filter(x=>x.case==='CENTRAL').map(x=>[x.code,x]));
 const period=a.countries;a.periodCountries=period;a.periodGlobal=a.global;
 a.countries={H:[],A:[],C:[]};a.classifications=[];a.openingBalances=[];
 for(let c=0;c<codes.length;c++){
  const h=hist.get(codes[c]),B=h.opening_balance_Gt;a.openingBalances.push(B);
  for(const k of ['H','A'])a.countries[k][c]=period[k][c].map(x=>x+h['history_'+k+'_Gt']);
  a.countries.C[c]=period.C[c].map(x=>x+B);a.classifications.push({code:codes[c],...classify(B,a.countries.C[c],a.years)});
 }
 a.global=Object.fromEntries(['C','H','A'].map(k=>[k,a.years.map((_,t)=>a.countries[k].reduce((sum,row)=>sum+row[t],0))]));
 a.events={countries:a.classifications.map(({code,events})=>({code,events})),global:classify(a.openingBalances.reduce((s,x)=>s+x,0),a.global.C,a.years)};
 // Remove obsolete period-only derived summaries to prevent accidental mixed-boundary plotting.
 delete a.regions;delete a.bubble;delete a.bubbleMeta;delete a.trajectorySummary;
 a._codes=codes;a.schema='pv-wrf-historical-opening-scenario/1.0';a.referenceAccountId=cohorts.id;
 return a;
}
async function main(){
 const {contexts,checkEnergy}=require(V+'/export_constraints_linkage_20261026/code/compute_accounts.cjs'),{readNpz}=require(V+'/multiscale_full_resolution_20261024/code/benchmark_core_native.cjs');
 const ctx=contexts(),parent=ctx.native.parent,codes=parent.codes,NC=codes.length;
 assert.deepEqual(codes,f.opening.map(x=>x.code));
 const configs=read(R+'/outputs/figures3_5_unified_time_metric_20261102/source_data/configuration_registry.json');
 const interfaces=readNpz(R+'/outputs/baseline_replacement_package_20261031/source_data/candidate_parent_opening_interfaces.npz');
 parent.u0=interfaces.u0_usable;parent.h0=interfaces.h0_usable_equivalent;parent.openingInverter=interfaces.inverter_first_parent_normalized;
 const fy=readNpz(V+'/multiscale_full_resolution_20261024/source_data/native_yield.npz');
 // Shared native1km slices retain the complete fine-yield distribution without duplicating pixels.
 const cdf={...fy,groupStart:[],groupEnd:[],groupWeight:[],due:[],eventFraction:[],parentOffsets:[0]};
 for(let i=0;i<parent.N;i++){
  const c=parent.countryIndex[i];if(parent.u0[i]>0)for(let t=0;t<T;t++){const w=interfaces.battery_first_due_probability_country[c*T+t];if(w>0){cdf.groupStart.push(fy.offsets[i]);cdf.groupEnd.push(fy.offsets[i+1]);cdf.groupWeight.push(w);cdf.due.push(t);cdf.eventFraction.push(interfaces.battery_first_due_fraction_country[c*T+t]);}}
  cdf.parentOffsets.push(cdf.due.length);
 }
 const stats={...ctx.native.stats,yield:fy,opening:cdf};let joint=null;stats.loadJointUTIL0=async()=>joint||(joint=await ctx.native.stats.loadJointUTIL0());
 const registry={...ctx.registry,resolved:{...ctx.registry.resolved}};
 for(const c of configs){const s=c.selection,p=c.parameters;registry.resolved[s.storage+'__'+s.life]=p;registry.resolved[p.storage_id+'__'+p.life_id]=p;}
 const cf=V+'/ssp_physical_extensions_20261027/source_data/MPI_SSP245.npz',mf=R+'/outputs/country_manufacturing_recalculation_20261028/source_data/country_factors_for_kernel.json';
 const weatherRatios={};for(const sc of ['SSP126','SSP245','SSP370','SSP585'])weatherRatios['MPI_'+sc+'__PV_TW']=readNpz(V+'/ssp_physical_extensions_20261027/source_data/MPI_'+sc+'.npz').pvRatio;
 const input={parent,stats,registry,iam:ctx.iam,climates:{roofRatios:ctx.cat.roofRatios,weatherRatios,thermalStress:{}},countryManufacturing:read(mf),openingFirstModule:interfaces.module_first_parent_normalized,openingFirstHouse:interfaces.cabinet_first_parent_normalized,openingGain:null};
 const {createCore,helpers}=require(R+'/supplementary_figures/SI_Figure6_crossed_costs_120_20261102/code/cross_operation_core.js'),core=createCore(input);


 const by=Object.fromEntries(configs.map(x=>[x.id,x])),manifest=[],regressions=[],checks=[];
 const sources=[P+'/source_data/frozen_inputs.json',P+'/source_data/fixed_reference_cohorts.json',R+'/outputs/baseline_replacement_package_20261031/source_data/candidate_parent_opening_interfaces.npz',mf,R+'/supplementary_figures/SI_Figure6_crossed_costs_120_20261102/code/cross_operation_core.js'];
 for(const sc of ['SSP126','SSP245','SSP370','SSP585'])sources.push(V+'/ssp_physical_extensions_20261027/source_data/MPI_'+sc+'.npz');
 const hashes=Object.fromEntries(sources.map(p=>[p,sha(p)]));let last=Date.now();
 const close=(a,b)=>{let e=0;for(let c=0;c<NC;c++)for(let t=0;t<T;t++)e=Math.max(e,Math.abs(a[c][t]-b[c][t]));return e;};
 async function run(cfg,s,id,prior){
  const out=J+'/accounts/'+id+'.json.gz';
  if(fs.existsSync(out)){const a=unzip(out);assert.equal(a.referenceAccountId,cohorts.id);manifest.push({id,path:out,sha256:sha(out),selection:s,configuration:cfg.id,source:'resumed'});return a;}
  const a=await core.compute(s,p=>{if(Date.now()-last>20000){console.log(JSON.stringify({id,...p}));last=Date.now();}});checkEnergy(a);
  if(prior){hashes[prior]=sha(prior);const b=unzip(prior);let e=0;for(const k of ['C','H','A'])e=Math.max(e,close(a.countries[k],b.periodCountries[k]));for(const k of Object.keys(a.annualCountry))e=Math.max(e,close(a.annualCountry[k],b.annualCountry[k]));assert(e<1e-10,'control regression '+id+' '+e);regressions.push({id,max_error_Gt:e});}
  continuous(a,codes);a.provenance={...a.provenance,current_history_policy:cohorts.id,completeness_migration:true};
  fs.writeFileSync(out,zlib.gzipSync(JSON.stringify(a),{level:3}));manifest.push({id,path:out,sha256:sha(out),selection:s,configuration:cfg.id,source:'current_history_recomputed'});
  fs.writeFileSync(J+'/source_data/new_account_manifest.partial.json',JSON.stringify(manifest,null,2));console.log(JSON.stringify({complete:id,n:manifest.length,C2100:a.global.C.at(-1)}));return a;
 }
 // Fill the four missing background tests before the rooftop/climate migration.
 for(const id of ['FIG4_L_BEST','FIG4_COMBINED']){
  const cfg=by[id+'__UNLIMITED'];input.openingGain=gainVector(cfg.parameters,codes);let qBase=null;
  for(const ex of ['UNLIMITED','CAP50','CAP0'])for(const bg of BGS){
   const s={...cfg.selection,background:bg,roof:'SSP2',climate:'SSP245',climateCoupling:'PV_TW',exportConstraint:ex};
   if(ex!=='UNLIMITED'&&bg==='NZ2050'){
    const p=R+'/outputs/figure6_bivariate_cost_export_20261104/accounts/NZ2050__'+id+'__'+ex+'.json.gz';hashes[p]=sha(p);manifest.push({id:bg+'__'+id+'__'+ex,path:p,sha256:sha(p),selection:s,configuration:cfg.id,source:'existing_verified_NZ'});continue;
   }
   const prior=ex==='UNLIMITED'?R+'/outputs/figures3_5_unified_time_metric_20261102/accounts/'+bg+'__'+id+'__UNLIMITED.json.gz':null;
   await run(cfg,s,bg+'__'+id+'__'+ex,prior);const ph=await core.buildPhysical(s);
   if(ex==='UNLIMITED'&&qBase===null)qBase=ph.quantity;
   for(const [k,v] of Object.entries(ph.quantity))assert.deepStrictEqual(v,qBase[k],'same hardware across background/export '+id+' '+k);
   checks.push({id:bg+'__'+id+'__'+ex,matched_hardware:true});
  }core.clearCache();
 }
 fs.writeFileSync(J+'/source_data/new_technology_export_manifest.json',JSON.stringify(manifest,null,2));
 const cfg=by['REF__UNLIMITED'];input.openingGain=gainVector(cfg.parameters,codes);
 for(const roof of ['SSP1','SSP2','SSP3','SSP5'])for(const climate of ['SSP126','SSP245','SSP370','SSP585']){
  for(const bg of BGS){
   const s={...cfg.selection,background:bg,roof,climate,model:'MPI',climateCoupling:'PV_TW',exportConstraint:'UNLIMITED'};
   const prior=roof==='SSP2'&&climate==='SSP245'?R+'/outputs/figures3_5_unified_time_metric_20261102/accounts/'+bg+'__REF__UNLIMITED.json.gz':null;
   await run(cfg,s,bg+'__ROOF_'+roof+'__CLIMATE_'+climate,prior);
  }core.clearCache();
 }
 for(const p of Object.keys(hashes))assert.equal(sha(p),hashes[p]);
 fs.writeFileSync(J+'/source_data/new_account_manifest.json',JSON.stringify(manifest,null,2));
 fs.writeFileSync(J+'/qa/new_account_checks.json',JSON.stringify({status:'PASS',countries:NC,parents:parent.N,history_policy:cohorts.id,regressions,hardware_checks:checks,source_hashes:hashes,external_parameters_added:0},null,2));
 console.log('PASS: missing technology/export tests and 80 rooftop-climate accounts completed.');
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
