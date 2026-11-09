'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto'),assert=require('assert');
const J=path.resolve(__dirname,'..'),R=path.resolve(__dirname,'../..').split(path.sep).join('/'),V=path.resolve(__dirname,'../../../native').split(path.sep).join('/');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\ufeff/,''));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const {classify}=require('./classify.cjs');
const near=(x,y,label)=>assert(Math.abs(x-y)<=1e-5+1e-9*Math.max(Math.abs(x),Math.abs(y)),label+': '+x+' != '+y);
async function main(){
 const {contexts,checkEnergy}=require(V+'/export_constraints_linkage_20261026/code/compute_accounts.cjs');
 const {readNpz}=require(V+'/multiscale_full_resolution_20261024/code/benchmark_core_native.cjs');
 const ctx=contexts(),f=read(J+'/source_data/frozen_inputs.json'),codes=ctx.native.parent.codes,NC=codes.length,T=76,ix=new Map(codes.map((c,i)=>[c,i]));
 assert.deepEqual(codes,f.opening.map(r=>r.code));
 const p=ctx.registry.resolved.REF__REF;
 // This specialised adapter is exact ONLY for REF: old/new operating parameters coincide.
 // Therefore initial cohort ages affect manufacture/treatment timing, not annual dispatch.
 // All opening event quantities are rebuilt from the continuous cohort chains below.
 assert.equal(p.eta,.85);assert.equal(p.standby_W,22.5);assert.equal(p.hours,2.5);assert.equal(p.duty,1);
 assert.equal(p.effective_DoD,.9);assert.equal(p.module_years,30);assert.equal(p.inverter_years,15);assert.equal(p.housing_years,20);
 assert.equal(p.calendar_years,16.5);assert.equal(p.cycle_limit,6250);
 assert.equal(p.pv_system_gain??1,1);assert.equal(p.inverter_gain??1,1);
 assert.equal(Math.ceil(Math.min(p.calendar_years,p.cycle_limit/365)),17);
 const ip=R+'/outputs/baseline_replacement_package_20261031/source_data/candidate_parent_opening_interfaces.npz';
 const intf=readNpz(ip),parent=ctx.native.parent;
 for(let i=0;i<parent.N;i++){near(parent.p0[i],intf.p0[i],'PV unchanged');near(parent.u0[i]*.9,intf.u0_usable[i],'usable once');near(parent.h0[i]*.9,intf.h0_usable_equivalent[i],'cabinet once');}
 parent.u0=intf.u0_usable;parent.h0=intf.h0_usable_equivalent;
 const cf=V+'/ssp_physical_extensions_20261027/source_data/MPI_SSP245.npz',mf=R+'/outputs/country_manufacturing_recalculation_20261028/source_data/country_factors_for_kernel.json',kernel=R+'/outputs/figure5_storage_export_joint_20261030/code/exact_operation_core.js';
 const core=require(kernel).createCore({...ctx.native,registry:ctx.registry,iam:ctx.iam,climates:{roofRatios:ctx.cat.roofRatios,weatherRatios:{MPI_SSP245__PV_TW:readNpz(cf).pvRatio},thermalStress:{}},countryManufacturing:read(mf)});
 const sel={resolution:'native1km',iam:'REMIND',background:'CP',roof:'SSP2',climate:'SSP245',model:'MPI',storage:'REF',life:'REF',exportConstraint:'UNLIMITED',climateCoupling:'PV_TW',batteryClimateResponse:'PASSIVE'};
 let lastLog=Date.now();const physical=await core.buildPhysical(sel,pr=>{if(Date.now()-lastLog>30000){console.log(JSON.stringify(pr));lastLog=Date.now();}});
 const q=physical.quantity,expected=Object.fromEntries(['modRepl','invRepl','houseRepl','batRepl_nominal','adoptedRetired_nominal','legacyFirst'].map(k=>[k,new Float64Array(NC*T)]));
 // Future NEW expansion uses existing year-start scheduling; opening generations use their own actual due years.
 for(let c=0;c<NC;c++)for(let t=0;t<T;t++){
  let j=c*T+t;
  for(const [dest,src,L]of [['modRepl','newPV',30],['invRepl','newPV',15],['houseRepl','newHouse',20],['batRepl_nominal','newBat_nominal',17]])for(let origin=t-L;origin>=0;origin-=L)expected[dest][j]+=q[src][c*T+origin];
  expected.adoptedRetired_nominal[j]=expected.batRepl_nominal[j];
 }
 const firstByCohort=new Map();for(const e of f.events)if(!firstByCohort.has(e.cohort_id)||e.event_time<firstByCohort.get(e.cohort_id))firstByCohort.set(e.cohort_id,e.event_time);
 for(const e of f.events){
  const t=e.event_year-2025;if(t<0||t>=T)continue;const j=ix.get(e.code)*T+t;
  assert.equal(e.event,'REPLACEMENT');assert(e.event_time>=2025&&e.event_time<2101);
  if(e.device==='PV_MODULE_AND_LINKED_BOS')expected.modRepl[j]+=e.quantity;
  else if(e.device==='INVERTER')expected.invRepl[j]+=e.quantity;
  else if(e.device==='STORAGE_CABINET')expected.houseRepl[j]+=e.quantity;
  else if(e.device==='BATTERY_LFP'){
   expected.batRepl_nominal[j]+=e.quantity;
   expected[e.event_time===firstByCohort.get(e.cohort_id)?'legacyFirst':'adoptedRetired_nominal'][j]+=e.quantity;
  }else throw Error(e.device);
 }
 for(const k of Object.keys(expected))q[k].set(expected[k]);
 // Independent opening-event oracle: start from each current vintage, advance continuous interval,
 // with no consumption of the future-event table used above.
 const oracle=Object.fromEntries(Object.keys(expected).map(k=>[k,new Float64Array(NC*T)]));
 for(const r of f.components){let first=true;for(let time=r.current_component_installation_time+r.reference_service_interval_years;time<2101;time+=r.reference_service_interval_years){
  assert(time>=2025-1e-8);const t=Math.floor(time+1e-9)-2025,j=ix.get(r.code)*T+t;
  const k={PV_MODULE_AND_LINKED_BOS:'modRepl',INVERTER:'invRepl',STORAGE_CABINET:'houseRepl',BATTERY_LFP:'batRepl_nominal'}[r.device];oracle[k][j]+=r.quantity;
  if(r.device==='BATTERY_LFP')oracle[first?'legacyFirst':'adoptedRetired_nominal'][j]+=r.quantity;first=false;
 }}
 for(let c=0;c<NC;c++)for(let t=0;t<T;t++){
  const j=c*T+t;
  for(const [dest,src,L]of [['modRepl','newPV',30],['invRepl','newPV',15],['houseRepl','newHouse',20],['batRepl_nominal','newBat_nominal',17],['adoptedRetired_nominal','newBat_nominal',17]])for(let origin=0;origin<t;origin++)if((t-origin)%L===0)oracle[dest][j]+=q[src][c*T+origin];
  for(const k of Object.keys(expected))near(q[k][j],oracle[k][j],'cohort oracle '+k);
 }
 for(let c=0;c<NC;c++){near(q.legacyFirst.subarray(c*T,(c+1)*T).reduce((a,b)=>a+b,0),f.opening[c].battery_nominal_kWh,'initial nominal retired once');}
 fs.writeFileSync(J+'/source_data/reference_physical_quantities.json.gz',zlib.gzipSync(JSON.stringify({selection:sel,codes,parameters:p,quantity:Object.fromEntries(Object.entries(q).map(([k,v])=>[k,Array.from(v)]))})));
 const history=f.history.filter(r=>r.case==='CENTRAL'),by=new Map(history.map(r=>[r.code,r]));
 const records=[],groups={},flat=[];let maxClose=0,maxBridge=0;
 for(const background of ['CP','NDC','B2C','NZ2050','LD']){
  const a=await core.compute({...sel,background});checkEnergy(a);assert.equal(a.diagnostics.nonlinearFallbackParentYears,0,'REF exact factorisation must hold');
  // The kernel's period totals are retained explicitly; continuous totals add matching historical H and A.
  a.periodCountries=a.countries;a.periodGlobal=a.global;a.periodRegions=a.regions;a.periodBubble=a.bubble;a.periodEvents=a.events;a.periodTrajectorySummary=a.trajectorySummary;
  a.openingBalances=codes.map(c=>by.get(c).opening_balance_Gt);
  a.countries={C:[],H:[],A:[]};a.classifications=[];
  const g={formed_then_lost:[],opening_benefit_then_lost:[],benefit_without_observed_loss:[],no_observed_benefit:[]};
  for(let c=0;c<NC;c++){
   const h=by.get(codes[c]);for(const k of ['H','A'])a.countries[k][c]=a.periodCountries[k][c].map(x=>x+h['history_'+k+'_Gt']);
   a.countries.C[c]=a.periodCountries.C[c].map(x=>x+h.opening_balance_Gt);
   let cum=h.opening_balance_Gt;for(let t=0;t<T;t++){cum+=a.annualCountry.net[c][t];maxBridge=Math.max(maxBridge,Math.abs(cum-a.countries.C[c][t]));maxClose=Math.max(maxClose,Math.abs(a.countries.C[c][t]-a.countries.H[c][t]+a.countries.A[c][t]));}
   const cl=classify(h.opening_balance_Gt,a.countries.C[c],a.years);a.classifications.push({code:codes[c],...cl});g[cl.state].push(codes[c]);
   flat.push({background,code:codes[c],country:f.opening[c].country,opening_balance_Gt:h.opening_balance_Gt,history_status:h.status,stock_status:f.opening[c].PV_stock_status,known_zero_conflict:f.opening[c].known_installation_evidence_despite_zero,...cl,C2100_Gt:a.countries.C[c].at(-1)});
  }
  a.global=Object.fromEntries(['C','H','A'].map(k=>[k,a.years.map((_,t)=>a.countries[k].reduce((sum,row)=>sum+row[t],0))]));a.global.negative=a.years.map((_,t)=>a.countries.C.filter(row=>row[t]<0).length);
  // Do not expose obsolete period-only regional / event summaries as continuous results.
  a.regions=ctx.native.parent.regions.map(r=>{const ids=ctx.native.parent.countries.map((c,i)=>c.region===r.id?i:-1).filter(i=>i>=0);return {id:r.id,n:ids.length,...Object.fromEntries(['H','A','C'].map(k=>[k,a.years.map((_,t)=>ids.reduce((s,i)=>s+a.countries[k][i][t],0))]))};});
  a.bubble={regions:ctx.native.parent.regions12.map(r=>{const ids=ctx.native.parent.countryTo12.map((v,i)=>v===r.id?i:-1).filter(i=>i>=0);return {id:r.id,n:ids.length,...Object.fromEntries(['H','A','C'].map(k=>[k,ids.reduce((s,i)=>s+a.countries[k][i].at(-1),0)]))};})};
  a.events={countries:a.classifications.map(({code,events})=>({code,events})),global:classify(a.openingBalances.reduce((s,x)=>s+x,0),a.global.C,a.years)};
  a.trajectorySummary={openingAware:true,stateCounts:Object.fromEntries(Object.entries(g).map(([k,v])=>[k,v.length]))};
  a.schema='pv-wrf-continuing-site-historical-opening/1.0';a.referenceAccountId='HISTORY_MATCHED_LFP_REF_20261102';a._codes=codes;
  a.provenance={...a.provenance,opening_boundary:'matching continuing-site historical H and A, ending2024; not full national industry history',ref_only_adapter:true,operational_age_invariance:true,event_source:R+'/outputs/baseline_replacement_package_20261031/source_data/future_opening_events_REF.csv',input_hashes:{...f.source_hashes,[cf]:sha(cf),[mf]:sha(mf),[kernel]:sha(kernel)}};
  const file=J+'/accounts/'+background+'__REF.json.gz';fs.writeFileSync(file,zlib.gzipSync(JSON.stringify(a),{level:3}));
  groups[background]=g;records.push({background,path:file,sha256:sha(file),selection:a.selection,state_counts:a.trajectorySummary.stateCounts,C2100_Gt:a.global.C.at(-1),global_first_loss:a.events.global.first_loss_year});
  console.log(JSON.stringify(records.at(-1)));
 }
 const unions=Object.fromEntries(['formed_then_lost','opening_benefit_then_lost'].map(k=>[k,[...new Set(Object.values(groups).flatMap(g=>g[k]))].sort()]));
 assert(!unions.formed_then_lost.some(c=>unions.opening_benefit_then_lost.includes(c)));
 const contract={schema:'fixed-reference-country-cohorts/1.0',id:'HISTORY_MATCHED_LFP_REF_20261102',frozen_on:'2026-11-02',unit:'country one vote within a background',reference_selection:sel,history_boundary:'same continuing sites and component chains represented by adopted2025 inventory',groups,unions,reference_accounts:records,rules:{membership:'each background REF only; all interventions reuse REF membership',cross_background:'per-background groups differ; pooled figures use explicit deduplicated unions or separately declared common cohort',first_loss:'first negative to positive since2025, using2024 opening balance as initial sign; exact zeros bridged',terminal:'2100 sign/recovery separate; not required for initial loss-event cohort'}};
 fs.writeFileSync(J+'/source_data/fixed_reference_cohorts.json',JSON.stringify(contract,null,2));
 fs.writeFileSync(J+'/source_data/country_reference_classifications.json',JSON.stringify(flat));
 fs.writeFileSync(J+'/source_data/account_manifest.json',JSON.stringify(records,null,2));
 fs.writeFileSync(J+'/qa/runtime_checks.json',JSON.stringify({status:'PASS',future_REF_recomputed:true,countries:NC,parent_cells:parent.N,backgrounds:5,opening_components:f.components.length,future_events:f.events.length,event_oracle_checks:NC*T*6,maximum_cumulative_bridge_error_Gt:maxBridge,maximum_H_minus_A_closure_error_Gt:maxClose,old_new_operating_parameters_identical:true,original_kernel_unchanged:true,all_intervention_scenarios_recomputed:false,adapter_scope:'REF only; future differing old/new technology requires fractional virtual cohorts',main_figure_pointers_unchanged:true},null,2));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
