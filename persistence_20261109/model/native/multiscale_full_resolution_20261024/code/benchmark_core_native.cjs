/* Node-only NPZ readback harness for the pure common core.
 * Uses actual immutable CDF arrays; no browser, server, or representative data.
 */
'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'..'),CROOT=path.dirname(ROOT),SRC=path.join(ROOT,'source_data'),OUT=path.join(ROOT,'outputs'),QA=path.join(OUT,'qa','core');fs.mkdirSync(QA,{recursive:true});
function readNpz(file){const fd=fs.openSync(file,'r'),size=fs.fstatSync(fd).size,tail=Buffer.alloc(Math.min(size,65557));fs.readSync(fd,tail,0,tail.length,size-tail.length);let e=-1;for(let j=tail.length-22;j>=0;j--)if(tail.readUInt32LE(j)===0x06054b50){e=j;break;}assert(e>=0,'NPZ ZIP directory missing');const directory=Buffer.alloc(tail.readUInt32LE(e+12));fs.readSync(fd,directory,0,directory.length,tail.readUInt32LE(e+16));const result={};let i=0;
 while(i<directory.length){assert.equal(directory.readUInt32LE(i),0x02014b50);const method=directory.readUInt16LE(i+10),compressed=directory.readUInt32LE(i+20),n=directory.readUInt16LE(i+28),extra=directory.readUInt16LE(i+30),comment=directory.readUInt16LE(i+32),offset=directory.readUInt32LE(i+42),name=directory.toString('utf8',i+46,i+46+n);const local=Buffer.alloc(30);fs.readSync(fd,local,0,30,offset);const bytes=Buffer.alloc(compressed);fs.readSync(fd,bytes,0,compressed,offset+30+local.readUInt16LE(26)+local.readUInt16LE(28));const raw=method===8?zlib.inflateRawSync(bytes):bytes;assert.equal(raw.toString('latin1',0,6),'\x93NUMPY');const major=raw[6],hl=major===1?raw.readUInt16LE(8):raw.readUInt32LE(8),base=major===1?10:12,header=raw.toString('latin1',base,base+hl),data=base+hl,descr=/'descr':\s*'([^']+)'/.exec(header)[1],shape=/'shape':\s*\(([^)]*)\)/.exec(header)[1].split(',').map(x=>Number(x.trim())).filter(x=>x>0),length=shape.reduce((a,b)=>a*b,1);let array;
  const aligned=(raw.byteOffset+data)%8===0?raw:Buffer.from(raw.subarray(data)),start=aligned===raw?raw.byteOffset+data:aligned.byteOffset;
  if(descr.endsWith('f8'))array=new Float64Array(aligned.buffer,start,length);
  else if(descr.endsWith('i8'))array=Float64Array.from(new BigInt64Array(aligned.buffer,start,length),Number);
  else if(descr.endsWith('u8'))array=Float64Array.from(new BigUint64Array(aligned.buffer,start,length),Number);
  else if(descr.endsWith('i4'))array=Float64Array.from(new Int32Array(raw.buffer,raw.byteOffset+data,length));
  else if(descr.endsWith('i2'))array=Float64Array.from(new Int16Array(raw.buffer,raw.byteOffset+data,length));
  else if(descr.endsWith('u2'))array=Float64Array.from(new Uint16Array(raw.buffer,raw.byteOffset+data,length));
  else if(descr.includes('U')||descr.includes('S')){i+=46+n+extra+comment;continue;}
  else throw new Error('Unsupported numerical NPZ dtype '+descr+' in '+name);
  result[name.replace(/\.npy$/,'')]=array;i+=46+n+extra+comment;
 }
 fs.closeSync(fd);return result;
}
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function main(){const began=Date.now(),window={};vm.runInNewContext(fs.readFileSync(path.join(OUT,'parent_inputs.js'),'utf8'),{window});const packed=window.NATIVE_FULL_INPUTS.parent_inputs;const baseWindow={};vm.runInNewContext(fs.readFileSync(path.join(CROOT,'mainpage_roof_climate_integration_20261021/outputs/base_inputs.js'),'utf8'),{window:baseWindow});const old=baseWindow.INTEGRATED_BASE_INPUTS;
 const parent={...packed,...readNpz(path.join(SRC,'parent_inputs.npz')),countries:old.countries,regions:old.regions,regions12:old.regions12,countryTo12:old.countryTo12};delete parent.arrays;
 console.log('Loaded parent',parent.N,Date.now()-began);
 const stats={N:parent.N,resolution:'native1km',rho:readNpz(path.join(SRC,'native_rho.npz')),opening:readNpz(path.join(SRC,'native_opening.npz')),loadYield:async()=>readNpz(path.join(SRC,'native_yield.npz')),loadJointUTIL0:async()=>readNpz(path.join(SRC,'native_util0_joint.npz'))};
 console.log('Loaded native CDF',Date.now()-began,'ms');
 const common=read(path.join(SRC,'common_parameter_registry.json')),registry={resolved:read(path.join(SRC,'resolved_parameters_by_pair.json')),storageAliases:common.storageAliases,reference_account_id:'STORAGE_REF_LFP_20261023'},iam=read(path.join(SRC,'iam_inputs.json')),catalog=read(path.join(SRC,'full_catalog.json'));
 const {createCore}=require(path.join(OUT,'full_resolution_core.js'));const core=createCore({parent,stats,registry,iam,climates:{roofRatios:catalog.roofRatios,weatherRatios:{}}});let last=Date.now();
 const account=await core.compute({resolution:'native1km',storage:'REF',life:'REF',iam:'REMIND',background:'CP',roof:'FIXED',climate:'CLEAN_CONTROL'},progress=>{if(Date.now()-last>1000){console.log(progress.stage,progress.done,progress.total,Date.now()-began);last=Date.now();}});
 const reference=readNpz(path.join(CROOT,'unified_storage_reference_20261023/source_data/fine_weather_account/country_annual_accounts.npz')),errors={};
 for(const field of ['newManufacturing','replacementManufacturing','treatment','gridAux','A','H','net']){let max=0;for(let c=0;c<231;c++)for(let t=0;t<76;t++)max=Math.max(max,Math.abs(account.annualCountry[field][c][t]-reference[field][c*76+t]/1e12));errors[field]=max;assert(max<1e-8,'Native baseline mismatch '+field+'='+max+'Gt');}
 const result={status:'PASS',scope:'Pure Node exact CDF common-core baseline versus completed original native annual account; no browser validation',parentCount:parent.N,countryCount:231,C2100_Gt:account.global.C.at(-1),negative:account.global.negative.at(-1),maximum_annual_difference_Gt:errors,diagnostics:account.diagnostics,core_sha256:hash(path.join(OUT,'full_resolution_core.js')),wall_ms:Date.now()-began};
 assert(Math.abs(account.global.C.at(-1)+32.928802182824896)<1e-8);assert.equal(account.global.negative.at(-1),158);
 fs.writeFileSync(path.join(QA,'native_REF_baseline_readback.json'),JSON.stringify(result,null,2));fs.writeFileSync(path.join(QA,'native_REF_actual_account.json'),JSON.stringify(account));console.log(JSON.stringify(result));
}
module.exports={readNpz};
if(require.main===module)main().catch(e=>{fs.writeFileSync(path.join(QA,'native_REF_baseline_readback.json'),JSON.stringify({status:'FAIL',error:e.message,stack:e.stack},null,2));console.error(e.stack);process.exitCode=1;});
