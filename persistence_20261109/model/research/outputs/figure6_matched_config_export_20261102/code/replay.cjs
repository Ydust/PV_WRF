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
const SRC=R+'/outputs/figures3_5_unified_time_metric_20261102';
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
 const input={parent,stats,registry,iam:ctx.iam,climates:{roofRatios:ctx.cat.roofRatios,weatherRatios:{MPI_SSP245__PV_TW:readNpz(cf).pvRatio},thermalStress:{}},countryManufacturing:read(mf),openingFirstModule:interfaces.module_first_parent_normalized,openingFirstHouse:interfaces.cabinet_first_parent_normalized,openingGain:null};
 const {createCore,helpers}=require('./history_valuation_adapter.js'),core=createCore(input);

 const storage=['STORAGE_FC0','STORAGE_FC50','STORAGE_FC100','STORAGE_CAP_HALF','STORAGE_CAP_DOUBLE','STORAGE_K05','STORAGE_K1','STORAGE_K2','STORAGE_UTIL50','STORAGE_UTIL0'];
 const tech=['FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED'];
 const selected=configs.filter(x=>x.selection.exportConstraint==='UNLIMITED'&&['REF',...storage,...tech].includes(x.id.replace('__UNLIMITED','')));
 assert.equal(selected.length,15);fs.writeFileSync(J+'/source_data/matched_configuration_registry.json',JSON.stringify(configs.filter(x=>selected.some(y=>y.id.split('__')[0]===x.id.split('__')[0])),null,2));
 let checks=[];for(const cfg of selected){
  const file=J+'/quantities/'+cfg.id+'.json.gz';if(fs.existsSync(file)){console.log('cached '+cfg.id);continue;}
  input.openingGain=gainVector(cfg.parameters,codes);
  const s={...cfg.selection,background:'CP',roof:'SSP2',climate:'SSP245',climateCoupling:'PV_TW'};
  let last=Date.now();const p=await core.buildPhysical(s,pr=>{if(Date.now()-last>25000){console.log(JSON.stringify({id:cfg.id,...pr}));last=Date.now();}});
  const expected=unzip(SRC+'/accounts/CP__'+cfg.id+'.json.gz');let error=0;
  for(const k of ['generation','useful','loss','pvAux','gridAux','charge','discharge'])for(let c=0;c<NC;c++)for(let t=0;t<T;t++)error=Math.max(error,Math.abs(p.energy[k][c*T+t]-expected.energyCountry[k][c][t])/Math.max(1,expected.energyCountry.generation[c][t]));
  assert(error<1e-11,cfg.id+' energy replay '+error);
  const serial=o=>Object.fromEntries(Object.entries(o).map(([k,v])=>[k,Array.from(v)]));
  const out={id:cfg.id,codes,parameters:p.parameters,selection:s,quantity:serial(p.quantity),valuation:serial(p.valuation),energy_replay_max_error:error,source_account:SRC+'/accounts/CP__'+cfg.id+'.json.gz',source_account_sha256:sha(SRC+'/accounts/CP__'+cfg.id+'.json.gz'),original_core_sha256:sha(SRC+'/code/history_operation_core.js')};
  fs.writeFileSync(file,zlib.gzipSync(JSON.stringify(out),{level:3}));checks.push({id:cfg.id,error});fs.writeFileSync(J+'/qa/physical_replay.json',JSON.stringify(checks,null,2));console.log(JSON.stringify({done:cfg.id,error}));core.clearCache();
 }
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
