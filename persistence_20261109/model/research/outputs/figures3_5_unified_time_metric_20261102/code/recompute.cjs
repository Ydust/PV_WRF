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
 const src3=R+'/outputs/figure2_three_families_control_20261031/source_data/account_manifest.json',src5=R+'/outputs/figures4_5_joint_baseline_20261031/source_data/account_manifest.json';
 const m3=read(src3).filter(x=>x.background==='CP'),m5=read(src5).filter(x=>x.background==='CP');
 const configs=[],seen=new Set();
 for(const [fig,rows]of [[3,m3],[5,m5]])for(const r of rows){const source=r.account||r.path;assert.equal(sha(source),r.sha256);const a=unzip(source),p=a.parameters,s=a.selection,key=JSON.stringify([s.storage,s.life,s.exportConstraint,p]);
  let existing=configs.find(x=>x.key===key);const use={figure:fig,scenario_id:r.scenario_id||r.configuration,family:r.family,label:r.label,export:s.exportConstraint};
  if(existing){existing.uses.push(use);continue;}
  const id=(r.scenario_id||r.configuration)+'__'+s.exportConstraint;assert(!seen.has(id));seen.add(id);configs.push({id,key,uses:[use],parameters:p,selection:s,parameter_source:source,parameter_source_sha256:sha(source)});
 }
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
 const input={parent,stats,registry,iam:ctx.iam,climates:{roofRatios:ctx.cat.roofRatios,weatherRatios:{MPI_SSP245__PV_TW:readNpz(cf).pvRatio},thermalStress:{}},countryManufacturing:read(mf),openingFirstModule:interfaces.module_first_parent_normalized,openingFirstHouse:interfaces.cabinet_first_parent_normalized,openingGain:null};
 const {createCore,helpers}=require('./history_operation_core.js'),core=createCore(input);
 const physicalKey=c=>JSON.stringify(Object.fromEntries(['effective_DoD','calendar_years','cycle_limit','module_years','inverter_years','housing_years','share','size_multiplier','capacity_basis','nominal_kWh_per_kWp','eta','standby_W','hours','duty','pv_system_gain','inverter_gain'].map(k=>[k,c.parameters[k]??null])));
 configs.sort((a,b)=>physicalKey(a).localeCompare(physicalKey(b))||a.selection.exportConstraint.localeCompare(b.selection.exportConstraint));
 fs.writeFileSync(J+'/source_data/configuration_registry.json',JSON.stringify(configs,null,2));
 const records=[],compression=process.argv.includes('--validate-compression'),smoke=process.argv.includes('--smoke')||compression,began=Date.now();let lastProgress=Date.now(),maxRefError=0;
 const partArg=process.argv.find(x=>x.startsWith('--part=')),partsArg=process.argv.find(x=>x.startsWith('--parts=')),part=partArg?Number(partArg.split('=')[1]):null,parts=partsArg?Number(partsArg.split('=')[1]):1;
 const groupKeys=[...new Set(configs.map(physicalKey))];
 const chosen=compression?configs.filter(x=>x.id==='STORAGE_FC0__CAP0'):smoke?configs.filter(x=>x.uses.some(u=>u.scenario_id==='REF')&&x.selection.exportConstraint==='UNLIMITED'):part===null?configs:configs.filter(x=>groupKeys.indexOf(physicalKey(x))%parts===part);
 for(const cfg of chosen){
  input.openingGain=gainVector(cfg.parameters,codes);
  for(const background of smoke?['CP']:BGS){
   const outFile=J+'/accounts/'+background+'__'+cfg.id+'.json.gz';
   if(!smoke&&fs.existsSync(outFile)){const a=unzip(outFile);assert.equal(a.referenceAccountId,cohorts.id);records.push({background,configuration_id:cfg.id,path:outFile,sha256:sha(outFile),uses:cfg.uses,selection:a.selection});continue;}
   const selection={...cfg.selection,background,roof:'SSP2',climate:'SSP245',climateCoupling:'PV_TW'};
   const a=await core.compute(selection,pr=>{if(Date.now()-lastProgress>30000){console.log(JSON.stringify(pr));lastProgress=Date.now();}});checkEnergy(a);
   assert.deepEqual(a.parameters,cfg.parameters);
   const physical=await core.buildPhysical(selection);for(const [k,v]of Object.entries(physical.quantity))assert(v.every(x=>Number.isFinite(x)&&x>=-1e-7),'quantity '+k);
   if(cfg.uses.some(u=>u.scenario_id==='REF')&&selection.exportConstraint==='UNLIMITED'){
    const expected=unzip(P+'/accounts/'+background+'__REF.json.gz');
    for(let c=0;c<NC;c++)for(let t=0;t<T;t++){maxRefError=Math.max(maxRefError,Math.abs(a.countries.C[c][t]-expected.periodCountries.C[c][t]));}
    assert(maxRefError<1e-10,'Frozen REF changed: '+maxRefError);
   }
   continuous(a,codes);a.provenance={...a.provenance,historical_opening_policy:cohorts.id,parameter_source:cfg.parameter_source,parameter_sha256:cfg.parameter_source_sha256,adapter_sha256:sha(J+'/code/history_operation_core.js'),original_model_overwritten:false};
   if(compression){const prev=unzip(outFile);let ec=0,ee=0,en=0,worst=null;for(let c=0;c<NC;c++)for(let t=0;t<T;t++){ec=Math.max(ec,Math.abs(a.countries.C[c][t]-prev.countries.C[c][t]));for(const k of Object.keys(a.energyCountry))if(a.energyCountry[k]!==null){const error=Math.abs(a.energyCountry[k][c][t]-prev.energyCountry[k][c][t]),relative=error/Math.max(1,Math.abs(prev.energyCountry[k][c][t]));en=Math.max(en,error/Math.max(1,prev.energyCountry.generation[c][t]));if(relative>ee){ee=relative;worst={country:codes[c],year:2025+t,field:k,error,old:prev.energyCountry[k][c][t],new:a.energyCountry[k][c][t],generation:prev.energyCountry.generation[c][t]};}}}fs.writeFileSync(J+'/qa/fast_curve_equivalence_candidate.json.gz',zlib.gzipSync(JSON.stringify(a)));const report={status:ec<1e-10&&en<1e-11?'PASS':'FAIL',country_years:NC*T,max_carbon_error_Gt:ec,max_relative_energy_error:ee,max_energy_error_normalized_to_generation:en,worst_relative_component:worst,old_adapter:sha(J+'/code/history_operation_core_v1.js'),new_adapter:sha(J+'/code/history_operation_core.js'),native_fine_distribution_preserved:true};fs.writeFileSync(J+'/qa/native_compression_validation.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));assert(report.status==='PASS');return;}
   fs.writeFileSync(outFile,zlib.gzipSync(JSON.stringify(a),{level:3}));
   records.push({background,configuration_id:cfg.id,path:outFile,sha256:sha(outFile),uses:cfg.uses,selection:a.selection});
   console.log(JSON.stringify({done:records.length,total:chosen.length*(smoke?1:5),id:cfg.id,background,C2100:a.global.C.at(-1),elapsed_seconds:(Date.now()-began)/1000}));
  }
  fs.writeFileSync(J+'/source_data/'+(smoke?'smoke_account_manifest.json':part===null?'account_manifest.json':'account_manifest_part'+part+'.json'),JSON.stringify(records,null,2));
 }
 fs.writeFileSync(J+'/qa/'+(smoke?'smoke_runtime.json':part===null?'runtime_checks.json':'runtime_part'+part+'.json'),JSON.stringify({status:'PASS',accounts:records.length,configurations:chosen.length,frozen_REF_maximum_absolute_error_Gt:maxRefError,virtual_opening_groups:cdf.due.length,source_hashes:{[src3]:sha(src3),[src5]:sha(src5),[cf]:sha(cf),[mf]:sha(mf)},cohort_hash:sha(P+'/source_data/fixed_reference_cohorts.json'),historical_scope:'conditional continuing sites;198 scenario-zero inventories retained',old_figures_unchanged:true},null,2));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
