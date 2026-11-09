'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=path.resolve(__dirname,'../..').split(path.sep).join('/'),J=path.resolve(__dirname,'..'),SRC=R+'/outputs/figures3_5_unified_time_metric_20261102';
for(const d of ['source_data','outputs','qa','quantities','annual'])fs.mkdirSync(J+'/'+d,{recursive:true});
let src=fs.readFileSync(SRC+'/code/history_operation_core.js','utf8');
function replace(a,b){assert(src.includes(a),a);src=src.replace(a,b);}
replace("const countryQuantity=Object.fromEntries", "const valuation=Object.fromEntries(['direct','night','stock'].map(k=>[k,new Float64Array(NC*T)]));\n   const countryQuantity=Object.fromEntries");
replace("energy.generation[j]=generation;", "const vj=getVector('countryIndex',i)*T+t;\n     valuation.direct[vj]+=generation*du;\n     valuation.night[vj]+=(p0*(u0>0?(beforeArea/area+(1-beforeArea/area)*p.duty):p.duty)*f0+cumPV[t]*fn*p.duty)*sumY*du;\n     valuation.stock[vj]+=(p0+cumPV[t])*area;\n     energy.generation[j]=generation;");
replace("quantity:countryQuantity,energy:countryEnergy,", "quantity:countryQuantity,energy:countryEnergy,valuation,");
fs.writeFileSync(J+'/code/history_valuation_adapter.js',src);
fs.copyFileSync(SRC+'/code/fast_curves.js',J+'/code/fast_curves.js');
const old=fs.readFileSync(SRC+'/code/recompute.cjs','utf8');
const prefix=old.slice(0,old.indexOf('async function main()'));
let setup=old.slice(old.indexOf(' const {contexts,checkEnergy}'),old.indexOf(' const physicalKey=c=>'));
setup=setup.slice(0,setup.indexOf(" const src3="))+" const configs=read('"+SRC+"/source_data/configuration_registry.json');\n"+setup.slice(setup.indexOf(' const interfaces='));
setup=setup.replace("require('./history_operation_core.js')","require('./history_valuation_adapter.js')");
const body=`
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
`;
fs.writeFileSync(J+'/code/replay.cjs',prefix+"const SRC='"+SRC+"';\nasync function main(){\n"+setup+body);
console.log('Prepared additive valuation adapter; scientific energy arrays unchanged.');
