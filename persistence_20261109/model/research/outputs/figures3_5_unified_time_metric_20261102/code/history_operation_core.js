/* Exact CDF integration of the registered roof-PV/storage annual model.
 * No representative fine weather, no interpolated coarse carbon accounts.
 * Nonlinear flows are integrated against the full weighted empirical CDF.
 * Pure UMD: Node and browser/worker use exactly the same implementation.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.FullResolutionCore=api;})(typeof window!=='undefined'?window:globalThis,function(){
'use strict';
const T=76,EPS=1e-10,YEARS=Array.from({length:T},(_,i)=>2025+i);
const ANNUAL=['newManufacturing','replacementManufacturing','treatment','gridAux','A','H','net'];
const QTY=['newPV','modRepl','invRepl','newBat_nominal','batRepl_nominal','adoptedRetired_nominal','legacyFirst','newHouse','houseRepl'];
const ENERGY=['generation','useful','loss','pvAux','gridAux','charge','discharge','curtailment','export'];
const WEIGHTS=Array.from({length:12},(_,k)=>Math.sin(Math.PI*(k+.5)/12));
{const sum=WEIGHTS.reduce((a,b)=>a+b,0);for(let k=0;k<12;k++)WEIGHTS[k]/=sum;}
const check=(value,message)=>{if(!value)throw new Error(message);};
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const finite=Number.isFinite;
function lowerBound(x,value,start,end){while(start<end){const mid=(start+end)>>>1;if(x[mid]<value)start=mid+1;else end=mid;}return start;}
function cdfBounds(cdf,group){return cdf.groupStart?[Number(cdf.groupStart[group]),Number(cdf.groupEnd[group])]:[Number(cdf.offsets[group]),Number(cdf.offsets[group+1])];}
function prefixTotal(prefix,start,end){return end>start?prefix[end-1]:0;}
function prefixRange(prefix,start,lo,hi){return hi>lo?prefix[hi-1]-(lo>start?prefix[lo-1]:0):0;}
function cdfTotal(cdf,group,prefix){const [a,b]=cdfBounds(cdf,group);return prefixTotal(cdf[prefix],a,b)*(cdf.groupWeight?cdf.groupWeight[group]:1);}
function cdfRange(cdf,group,lo,hi,prefix){const [a,b]=cdfBounds(cdf,group);const l=lowerBound(cdf.x,lo,a,b),r=lowerBound(cdf.x,hi,a,b);return prefixRange(cdf[prefix],a,l,r)*(cdf.groupWeight?cdf.groupWeight[group]:1);}
function lineCurve(m=0,b=0){return [{lo:0,hi:Infinity,m,b}];}
function valueAt(curve,x){let lo=0,hi=curve.length;while(lo+1<hi){const mid=(lo+hi)>>>1;if(curve[mid].lo<=x)lo=mid;else hi=mid;}const s=curve[lo];return s.m*x+s.b;}
function coefficients(curve,x){let lo=0,hi=curve.length;while(lo+1<hi){const mid=(lo+hi)>>>1;if(curve[mid].lo<=x)lo=mid;else hi=mid;}return curve[lo];}
function mergeSegments(segments){const out=[];for(const s of segments){if(!(s.hi>s.lo))continue;const p=out.at(-1);if(p&&p.hi===s.lo&&p.m===s.m&&p.b===s.b)p.hi=s.hi;else out.push({...s});}return out.length?out:lineCurve();}
function combine(a,b,kind){
 const knots=[...new Set([...a.map(s=>s.lo),...b.map(s=>s.lo),Infinity])].sort((x,y)=>x-y),out=[];
 for(let k=0;k<knots.length-1;k++){
  const lo=knots[k],hi=knots[k+1],mid=finite(hi)?(lo+hi)/2:lo+Math.max(1,Math.abs(lo));
  const aa=coefficients(a,mid),bb=coefficients(b,mid);
  if(kind==='add'){out.push({lo,hi,m:aa.m+bb.m,b:aa.b+bb.b});continue;}
  const dm=aa.m-bb.m,db=aa.b-bb.b,root=dm!==0?-db/dm:Infinity;
  const cuts=finite(root)&&root>lo&&root<hi?[lo,root,hi]:[lo,hi];
  for(let j=0;j<cuts.length-1;j++){const l=cuts[j],h=cuts[j+1],v=finite(h)?(l+h)/2:l+Math.max(1,Math.abs(l)),s=aa.m*v+aa.b<=bb.m*v+bb.b?aa:bb;out.push({lo:l,hi:h,m:s.m,b:s.b});}
 }
 return mergeSegments(out);
}
const scaleCurve=(curve,scale)=>curve.map(s=>({...s,m:s.m*scale,b:s.b*scale}));
const addCurves=(a,b)=>combine(a,b,'add');
const minCurves=(a,b)=>combine(a,b,'min');
function sumCappedTerms(slopes,caps){
 const knots=[0,Infinity];for(let k=0;k<slopes.length;k++)if(slopes[k]>0&&caps[k]>0)knots.push(caps[k]/slopes[k]);
 const unique=[...new Set(knots)].sort((a,b)=>a-b),out=[];
 for(let i=0;i<unique.length-1;i++){const lo=unique[i],hi=unique[i+1],x=finite(hi)?(lo+hi)/2:lo+Math.max(1,lo);let m=0,b=0;
  for(let k=0;k<slopes.length;k++){if(slopes[k]*x<caps[k])m+=slopes[k];else b+=caps[k];}
  out.push({lo,hi,m,b});}
 return mergeSegments(out);
}
function integrate(curve,cdf,group,weightPrefix='prefixA',momentPrefix='prefixAY'){
 const [start,end]=cdfBounds(cdf,group);if(start===end)return 0;let sum=0,lo=start;
 for(const segment of curve){if(lo>=end)break;const hi=finite(segment.hi)?lowerBound(cdf.x,segment.hi,lo,end):end;
  if(hi>lo)sum+=segment.m*prefixRange(cdf[momentPrefix],start,lo,hi)+segment.b*prefixRange(cdf[weightPrefix],start,lo,hi);lo=hi;}
 return sum*(cdf.groupWeight?cdf.groupWeight[group]:1);
}
function openingChargeCurve(p0,u0,share,direct,ratio,eta,hours,duty){
 if(!(u0>0&&share>0&&p0>0&&duty>0))return lineCurve();
 const cap=u0/share,power=cap/hours,slopes=WEIGHTS.map(w=>p0*ratio*w*(1-direct)/365);
 const available=sumCappedTerms(slopes,WEIGHTS.map(()=>power));
 const charge=minCurves(available,lineCurve(0,cap/Math.sqrt(eta)));
 // All registered durations <=10h. The12h discharge window can supply
 // >=1.2*cap, while charged stored energy gives <=sqrt(eta)*cap.
 return scaleCurve(charge,365*share*duty);
}
function rhoChargeCurve(b,share,direct,ratio,eta,hours,duty){
 if(!(b>0&&share>0&&duty>0))return lineCurve();
 const available=sumCappedTerms(WEIGHTS.map(()=>b/hours),WEIGHTS.map(w=>ratio*w*(1-direct)/365));
 return scaleCurve(minCurves(available,lineCurve(b/Math.sqrt(eta),0)),365*share*duty);
}
function scalarOperation(generation,usable,share,direct,eta,hours,duty=1){
 if(!(usable>0&&share>0&&duty>0))return {charge:0,discharge:0,loss:0,delivered:generation};
 const cap=usable/share,power=cap/hours;let available=0;
 for(const weight of WEIGHTS)available+=Math.max(0,Math.min(generation/365*weight*(1-direct),power));
 const day=Math.min(available,cap/Math.sqrt(eta));const charge=day*365*share*duty,discharge=Math.min(day*eta,12*power)*365*share*duty;
 return {charge,discharge,loss:charge-discharge,delivered:generation-(charge-discharge)};
}

// Conditional representative-day export experiment. The full weighted source
// CDF is retained. All expressions are piecewise linear in Y, or in rho after
// dividing by Y. These are allocation proxies, not measured national loads.
const maxCurves=(a,b)=>addCurves(addCurves(a,b),scaleCurve(minCurves(a,b),-1));
const positiveCurve=a=>maxCurves(a,lineCurve());
function constrainedCurvesOriginal(o={}){
 const {pvCapacity=1,ratio=1,share=0,direct=.4,eta=.85,hours=2.5,duty=1,nightAlpha=1,exportRatio=.5,variable='Y'}=o;
 check(pvCapacity>=0&&ratio>=0&&share>=0&&share<=1&&direct>=0&&direct<=1&&eta>0&&eta<=1&&hours>0&&duty>=0&&duty<=1&&nightAlpha>=0&&exportRatio>=0,'Invalid bounded-operation parameters');
 if(pvCapacity===0&&!(o.usable>0)&&!(o.usableRhoCoeff>0)&&!(o.standbyDailyPerEquipped>0)){const z=lineCurve();return Object.fromEntries(['generation','useful','loss','pvAux','gridAux','charge','discharge','curtailment','export','directUse','auxiliary'].map(k=>[k,z]));}
 const y=variable==='rho'?lineCurve(0,1):lineCurve(1,0),zero=lineCurve();
 const weights=o.dayWeights||WEIGHTS,peak=Math.max(...WEIGHTS);
 check(weights.length===12&&weights.every(w=>Number.isFinite(w)&&w>=0)&&Math.abs(weights.reduce((a,b)=>a+b,0)-1)<1e-10,'Day weights must be12 nonnegative fractions summing to1');
 const U=share>0?(variable==='rho'?lineCurve((o.usableRhoCoeff||0)/share,0):lineCurve(0,(o.usable||0)/share)):zero;
 const P=scaleCurve(U,1/hours),G=scaleCurve(y,pvCapacity*ratio),surplus=scaleCurve(G,(1-direct)/365);
 const cap=scaleCurve(y,exportRatio*(1-direct)*pvCapacity*peak/365),night=scaleCurve(y,nightAlpha*direct*pvCapacity/365);
 let available=zero,clipped=zero,recoverable=zero;
 for(const w of weights){const h=scaleCurve(surplus,w),clip=positiveCurve(addCurves(h,scaleCurve(cap,-1)));available=addCurves(available,minCurves(h,P));clipped=addCurves(clipped,clip);recoverable=addCurves(recoverable,minCurves(clip,P));}
 let q=zero;if(share>0&&duty>0){q=minCurves(available,scaleCurve(U,1/Math.sqrt(eta)));q=minCurves(q,scaleCurve(P,12/eta));q=minCurves(q,scaleCurve(addCurves(night,scaleCurve(cap,12)),1/eta));}
 const recovered=minCurves(q,recoverable),factor=365*share*duty;
 const charge=scaleCurve(q,factor),discharge=scaleCurve(charge,eta),loss=addCurves(charge,scaleCurve(discharge,-1));
 const auxCoef=(o.standby_W??22.5)*(o.standby_hours_year??6000)/1000/(o.standby_usable_unit_kWh??12.96)/365;
 const auxDaily=o.standbyDailyPerEquipped==null?scaleCurve(U,auxCoef):lineCurve(0,o.standbyDailyPerEquipped);
 const pvAux=scaleCurve(minCurves(scaleCurve(auxDaily,.5),scaleCurve(q,eta)),factor),aux=scaleCurve(auxDaily,365*share),gridAux=addCurves(aux,scaleCurve(pvAux,-1));
 const curtailment=addCurves(scaleCurve(clipped,365),scaleCurve(recovered,-factor));
 const dayExport=addCurves(addCurves(scaleCurve(surplus,365),scaleCurve(charge,-1)),scaleCurve(curtailment,-1));
 const deliveredNight=addCurves(discharge,scaleCurve(pvAux,-1)),nightSelf=minCurves(deliveredNight,scaleCurve(night,factor));
 const nightExport=positiveCurve(addCurves(deliveredNight,scaleCurve(nightSelf,-1))),exp=addCurves(dayExport,nightExport);
 const useful=addCurves(addCurves(addCurves(G,scaleCurve(loss,-1)),scaleCurve(curtailment,-1)),scaleCurve(pvAux,-1));
 return {generation:G,useful,loss,pvAux,gridAux,charge,discharge,curtailment,export:exp,directUse:addCurves(scaleCurve(G,direct),nightSelf),auxiliary:aux};
}
// Algebraically factored form of the SAME12-slot representative-day expressions.
// All curve intersections and native-CDF integrals remain exact; no Y rounding.
function constrainedCurves(o={}){
 const {pvCapacity=1,ratio=1,share=0,direct=.4,eta=.85,hours=2.5,duty=1,nightAlpha=1,exportRatio=.5,variable='Y'}=o;
 check(pvCapacity>=0&&ratio>=0&&share>=0&&share<=1&&direct>=0&&direct<=1&&eta>0&&eta<=1&&hours>0&&duty>=0&&duty<=1&&nightAlpha>=0&&exportRatio>=0,'Invalid bounded-operation parameters');
 const weights=o.dayWeights||WEIGHTS;check(weights.length===12&&weights.every(x=>finite(x)&&x>=0)&&Math.abs(weights.reduce((a,b)=>a+b,0)-1)<1e-10,'Invalid12-slot weights');
 if(pvCapacity===0&&!(o.usable>0)&&!(o.usableRhoCoeff>0)&&!(o.standbyDailyPerEquipped>0)){const z=lineCurve();return Object.fromEntries(['generation','useful','loss','pvAux','gridAux','charge','discharge','curtailment','export','directUse','auxiliary'].map(k=>[k,z]));}
 const isRho=variable==='rho',zero=lineCurve(),Y=isRho?lineCurve(0,1):lineCurve(1,0);
 const u=share>0?(isRho?(o.usableRhoCoeff||0)/share:(o.usable||0)/share):0;
 const U=isRho?lineCurve(u,0):lineCurve(0,u),P=scaleCurve(U,1/hours),G=scaleCurve(Y,pvCapacity*ratio);
 const slopeS=pvCapacity*ratio*(1-direct)/365,cap=exportRatio*(1-direct)*pvCapacity*Math.max(...WEIGHTS)/365,night=nightAlpha*direct*pvCapacity/365;
 const surplus=weights.map(w=>slopeS*w),clips=surplus.map(x=>Math.max(0,x-cap));
 if(!(share>0&&u>0&&duty>0)){
  const clipped=365*clips.reduce((a,b)=>a+b,0),curtailment=scaleCurve(Y,clipped),auxCoef=(o.standby_W??22.5)*(o.standby_hours_year??6000)/1000/(o.standby_usable_unit_kWh??12.96)/365;
  const auxDaily=o.standbyDailyPerEquipped==null?scaleCurve(U,auxCoef):lineCurve(0,o.standbyDailyPerEquipped),aux=scaleCurve(auxDaily,365*share);
  return {generation:G,useful:scaleCurve(Y,pvCapacity*ratio-clipped),loss:zero,pvAux:zero,gridAux:aux,charge:zero,discharge:zero,curtailment,export:scaleCurve(Y,365*slopeS-clipped),directUse:scaleCurve(G,direct),auxiliary:aux};
 }
 const available=isRho?sumCappedTerms(weights.map(()=>u/hours),surplus):sumCappedTerms(surplus,weights.map(()=>u/hours));
 const recovery=isRho?sumCappedTerms(weights.map(()=>u/hours),clips):sumCappedTerms(clips,weights.map(()=>u/hours));
 let q=zero;
 if(share>0&&u>0&&duty>0){q=minCurves(available,scaleCurve(U,1/Math.sqrt(eta)));q=minCurves(q,scaleCurve(P,12/eta));q=minCurves(q,scaleCurve(Y,(night+12*cap)/eta));}
 const recovered=minCurves(q,recovery),factor=365*share*duty;
 const charge=scaleCurve(q,factor),discharge=scaleCurve(charge,eta),loss=scaleCurve(charge,1-eta);
 const auxCoef=(o.standby_W??22.5)*(o.standby_hours_year??6000)/1000/(o.standby_usable_unit_kWh??12.96)/365;
 const auxDaily=o.standbyDailyPerEquipped==null?scaleCurve(U,auxCoef):lineCurve(0,o.standbyDailyPerEquipped);
 const pvAux=scaleCurve(minCurves(scaleCurve(auxDaily,.5),scaleCurve(q,eta)),factor),aux=scaleCurve(auxDaily,365*share),gridAux=addCurves(aux,scaleCurve(pvAux,-1));
 const curtailment=addCurves(scaleCurve(Y,365*clips.reduce((a,b)=>a+b,0)),scaleCurve(recovered,-factor));
 const dayExport=addCurves(addCurves(scaleCurve(Y,365*slopeS),scaleCurve(charge,-1)),scaleCurve(curtailment,-1));
 const deliveredNight=addCurves(discharge,scaleCurve(pvAux,-1)),nightSelf=minCurves(deliveredNight,scaleCurve(Y,night*factor));
 const nightExport=positiveCurve(addCurves(deliveredNight,scaleCurve(nightSelf,-1))),exp=addCurves(dayExport,nightExport);
 const useful=addCurves(addCurves(addCurves(G,scaleCurve(loss,-1)),scaleCurve(curtailment,-1)),scaleCurve(pvAux,-1));
 return {generation:G,useful,loss,pvAux,gridAux,charge,discharge,curtailment,export:exp,directUse:addCurves(scaleCurve(G,direct),nightSelf),auxiliary:aux};
}

function scalarConstrainedOperation(o={}){
 const {pvCapacity=1,ratio=1,share=0,direct=.4,eta=.85,hours=2.5,duty=1,nightAlpha=1,exportRatio=.5}=o;
 const Y=o.variable==='rho'?1:(o.cleanY??1400),usable=o.variable==='rho'?(o.usableRhoCoeff||0)*(o.rho??1):(o.usable||0),weights=o.dayWeights||WEIGHTS;
 check(weights.length===12&&weights.every(w=>Number.isFinite(w)&&w>=0)&&Math.abs(weights.reduce((a,b)=>a+b,0)-1)<1e-10,'Day weights must be12 nonnegative fractions summing to1');
 const generation=pvCapacity*Y*ratio,S=generation*(1-direct)/365,cap=exportRatio*(1-direct)*pvCapacity*Y*Math.max(...WEIGHTS)/365,L=nightAlpha*direct*pvCapacity*Y/365,U=share>0?usable/share:0,P=U/hours;
 let available=0,clipped=0,recoveryLimit=0;for(const w of weights){const surplus=S*w,clip=Math.max(0,surplus-cap);available+=Math.min(surplus,P);clipped+=clip;recoveryLimit+=Math.min(clip,P);}
 const q=U>0&&duty>0?Math.min(available,U/Math.sqrt(eta),12*P/eta,(L+12*cap)/eta):0,r=Math.min(q,recoveryLimit),factor=365*share*duty;
 const charge=q*factor,discharge=eta*charge,loss=charge-discharge,auxDaily=o.standbyDailyPerEquipped??(U*(o.standby_W??22.5)*(o.standby_hours_year??6000)/1000/(o.standby_usable_unit_kWh??12.96)/365);
 const auxiliary=365*share*auxDaily,pvAux=factor*Math.min(.5*auxDaily,eta*q),gridAux=auxiliary-pvAux,curtailment=Math.max(0,365*clipped-factor*r),dayExport=365*S-charge-curtailment,netNight=discharge-pvAux,nightSelf=Math.min(netNight,L*factor),exp=dayExport+Math.max(0,netNight-nightSelf),useful=generation-loss-curtailment-pvAux;
 return {generation,useful,loss,pvAux,gridAux,charge,discharge,curtailment,export:Math.max(0,exp),directUse:generation*direct+nightSelf,auxiliary};
}

function interval(params,nu){return Math.max(1,Math.ceil(Math.min(params.calendar_years,nu>0?params.cycle_limit/nu:Infinity)-EPS));}
function constantInterval(params){const low=interval(params,365*params.duty),high=interval(params,0);return low===high?high:null;}
function nestedMatrix(count){return Array.from({length:count},()=>Array(T).fill(0));}
function classify(values){let first=0,last=0,crossings=0,zeroYears=0;const events=[];for(let t=0;t<T;t++){const sign=Math.sign(values[t]);if(!sign){zeroYears++;continue;}if(!first)first=sign;if(last&&last!==sign){crossings++;events.push({year:YEARS[t],fromSign:last,toSign:sign});}last=sign;}
 const id=first===0?'all_zero':crossings>=2?'repeated':crossings===1?(last<0?'once_to_negative':'once_to_positive'):(first<0?'all_negative':'all_positive');return {id,crossings,firstSign:first,lastSign:last,zeroYears,events};}
function ratioAt(array,p,t){return Array.isArray(array[p])||ArrayBuffer.isView(array[p])?array[p][t]:array[p*T+t];}

function createCore(input){
 const parent=input.parent,stats=input.stats,iam=input.iam,climates=input.climates||{};
 check(parent&&stats&&iam&&input.registry,'Full-resolution source data are incomplete');
 const N=Number(parent.N||stats.N||parent.area?.length),NC=(parent.codes||iam.country_codes).length;
 check(N>0&&NC>0,'Registered parent/country dimensions missing');
 const registry=input.registry;
 const table=registry.resolved_parameters_by_pair||registry.resolved||registry.parameters||registry;
 const aliases=registry.storageAliases||input.storageAliases||{MAIN:'REF',T0:'REF'};
 const codes=parent.codes||iam.country_codes,countries=parent.countries||codes.map(code=>({code,name:code,region:'Unknown'}));
 const regions=parent.regions||[],regions12=parent.regions12||[],map12=parent.countryTo12||[];
 const models=Array.isArray(iam.models)?iam.models:Object.entries(iam.models||iam).map(([id,m])=>({id,...m}));
 let yieldCDF=stats.yield||stats.yieldCDF;
 const rhoCDF=stats.rho||stats.rhoCDF,openingCDF=stats.opening;
 check(rhoCDF&&openingCDF,'Exact rho/opening CDFs are required');
 const getVector=(name,p)=>{const a=parent[name]||parent.inputs?.[name];check(a,'Parent vector missing: '+name);return Number(a[p]);};
 const parentArea=p=>getVector('area',p);
 const areaSum=p=>parent.allocatedArea?Number(parent.allocatedArea[p]):yieldCDF?cdfTotal(yieldCDF,p,'prefixA'):Number(parent.area[p]);
 const yieldSum=p=>parent.sumAY?Number(parent.sumAY[p]):cdfTotal(yieldCDF,p,'prefixAY');
 let yieldPromise=null,jointPromise=null,cache=null,pending=null,generation=0;
 async function ensureYield(){if(yieldCDF)return yieldCDF;if(!yieldPromise)yieldPromise=(async()=>{const loader=stats.loadYield||input.loadYield;check(typeof loader==='function','Exact yield CDF required for fixed-kWh capacity settings');yieldCDF=await loader();check(yieldCDF?.offsets&&yieldCDF?.prefixAY,'Yield CDF schema incomplete');stats.yield=yieldCDF;return yieldCDF;})();return yieldPromise;}
 async function ensureJoint(){if(stats.jointUTIL0)return stats.jointUTIL0;if(!jointPromise)jointPromise=(async()=>{const loader=stats.loadJointUTIL0||input.loadJointUTIL0;check(typeof loader==='function','Exact joint(parent,rho,due,Y) statistics required for this binding auxiliary-power case');const value=await loader();check(value?.parentOffsets&&value?.rho,'Joint CDF schema incomplete');stats.jointUTIL0=value;return value;})();return jointPromise;}
 function resolve(selection={}){
  const s={resolution:selection.resolution||stats.resolution||'native1km',iam:selection.iam||'REMIND',background:selection.background||'CP',roof:selection.roof||'FIXED',climate:selection.climate||'CLEAN_CONTROL',model:selection.model??'MPI',storage:selection.storage||'REF',life:selection.life||'REF',exportConstraint:selection.exportConstraint||'UNLIMITED',climateCoupling:selection.climateCoupling||'RADIATION_ONLY',batteryClimateResponse:selection.batteryClimateResponse||'PASSIVE'};
  check(['RADIATION_ONLY','PV_TW','PV_BATTERY'].includes(s.climateCoupling),'Unregistered physical climate coupling');
  check(['PASSIVE','BUFFERED','NEUTRAL'].includes(s.batteryClimateResponse),'Unregistered battery climate response');
  check(['UNLIMITED','CAP50','CAP25','CAP0'].includes(s.exportConstraint),'Unregistered export constraint');
  if(['HOLD','CLEAN_CONTROL'].includes(s.climate))s.model=null;
  const alias=aliases[s.storage]||s.storage,storage=typeof alias==='string'?alias:alias.canonical||alias.id||'REF';
  let params=table[storage+'__'+s.life];if(selection.comparisonShare!==undefined){check(selection.comparisonShare===0||selection.comparisonShare===1,'Invalid paired share override');s.comparisonShare=selection.comparisonShare;params={...params,share:selection.comparisonShare};}check(params,'Unregistered common storage/lifetime pair: '+storage+'/'+s.life);
  if(s.climateCoupling==='PV_BATTERY')check(params.chemistry_id==='LFP_GRAPHITE','Temperature-aging parameters are registered only for LFP; no silent chemistry transfer');
  check(params.eta>0&&params.eta<=1&&params.hours>0&&params.hours<=10&&params.duty>=0&&params.duty<=1,'Operating parameters exceed the verified representative-day domain');
  check(params.effective_DoD>0&&params.effective_DoD<=1,'Invalid effectiveDoD');
  return {selection:s,params};
 }
 function key(selection){const {selection:s}=resolve(selection);return ['full-resolution',s.resolution,s.iam,s.background,s.roof,s.climate,s.model||'STATIC',s.storage,s.life,'EX_'+s.exportConstraint,...(s.climateCoupling==='RADIATION_ONLY'?[]:['CL_'+s.climateCoupling,'BC_'+s.batteryClimateResponse]),...(s.comparisonShare===undefined?[]:['PAIR_FC'+100*s.comparisonShare])].join('::');}
 function weather(s){if(s.climate==='CLEAN_CONTROL')return null;if(s.climate==='HOLD')return 'HOLD';const name=(s.model||'MPI')+'_'+s.climate+(s.climateCoupling==='RADIATION_ONLY'?'':'__PV_TW'),values=climates.weatherRatios?.[name]||climates.weather?.[name];check(values&&values.length===N*T||values&&values.length===N,'Climate relative path missing/incomplete: '+name);return values;}
 function roof(s){const g=climates.roofRatios?.[s.roof]||climates.roofs?.[s.roof];if(s.roof==='FIXED'&&!g)return Array(T).fill(1);check(g&&g.length===T,'Roof relative path missing: '+s.roof);return g;}
 function physicalKey(s,p){return JSON.stringify({resolution:s.resolution,roof:s.roof,climate:s.climate,model:s.model,climateCoupling:s.climateCoupling,batteryClimateResponse:s.batteryClimateResponse,
  parameters:Object.fromEntries(['chemistry_id','effective_DoD','calendar_years','cycle_limit','module_years','inverter_years','housing_years','share','size_multiplier','capacity_basis','nominal_kWh_per_kWp','eta','standby_W','standby_hours_year','standby_usable_unit_kWh','hours','duty','pv_system_gain','inverter_gain'].map(k=>[k,p[k]]))});}
 async function buildUnlimitedPhysical(selection,onProgress){
  const {selection:s,params:p}=resolve(selection),pk=physicalKey(s,p);
  if(cache?.key===pk)return cache.value;if(pending?.key===pk)return pending.promise;
  const job=++generation;
  const promise=(async()=>{
   const began=typeof performance!=='undefined'?performance.now():Date.now(),G=roof(s),R=weather(s);
   const fixedK=p.capacity_basis==='nominal_kWh_per_kWp_equipped_PV';
   if(fixedK)await ensureYield();
   const countryQuantity=Object.fromEntries(QTY.map(name=>[name,new Float64Array(NC*T)]));
   const countryEnergy=Object.fromEntries(ENERGY.map(name=>[name,new Float64Array(NC*T)]));
   const designEFWeightedUseful=new Float64Array(NC*T),designEFWeightedAux=new Float64Array(NC*T);
   const workQuantity=Object.fromEntries(QTY.map(name=>[name,new Float64Array(T)]));
   const workEnergy=Object.fromEntries(ENERGY.map(name=>[name,new Float64Array(T)]));
   const thermal=s.climateCoupling==='PV_BATTERY',newTauConstant=thermal?null:constantInterval(p),coef=p.standby_hours_year/1000/p.standby_usable_unit_kWh;
   const pvGain=p.pv_system_gain??1,invGain=p.inverter_gain??1;
   check(pvGain>=1&&invGain>=1&&pvGain*invGain<=1.15,'Operating gain outside declared finite range');
   let nonlinearFallbackParents=0,jointQueries=0,lowestNewMargin=Infinity,lowestOpeningMargin=Infinity;
   for(let i=0;i<N;i++){
    if(job!==generation)throw new Error('Physical calculation superseded by a newer selection');
    const quantity=workQuantity,energy=workEnergy;
    for(const name of QTY)quantity[name].fill(0);for(const name of ENERGY)energy[name].fill(0);
    const normArea=parentArea(i),area=areaSum(i),sumY=yieldSum(i),p0=getVector('p0',i)/normArea,u0=getVector('u0',i)/normArea,h0=getVector('h0',i)/normArea;
    const cap=getVector('cap0',i)/normArea,f0=getVector('fc',i),fn=p.share==null?f0:p.share,du=getVector('du',i),fold=getVector('Fold',i);
    const basisK=p.capacity_basis==='nominal_kWh_per_kWp_equipped_PV';
    const perU=basisK?fn*p.nominal_kWh_per_kWp*p.effective_DoD*p.size_multiplier:null;
    const b=fold*(1-du)*p.size_multiplier;
    const sumU=basisK?perU*area:fn*b*cdfTotal(rhoCDF,i,'prefixW1');
    const newTauMass=new Map(),oldGroups=[];
    // Temperature affects adopted cohorts. Historical opening first removal
    // remains the registered event, with no fabricated pre-2025 thermal history.
    const stressId=(s.model||'MPI')+'_'+s.climate;
    const stress=thermal&&s.model?climates.thermalStress?.[stressId]?.[s.batteryClimateResponse]:null;
    check(!thermal||!s.model||stress,'LFP thermal aging input missing');
    const prefix=new Float64Array(T+1);
    for(let t=0;t<T;t++){const v=stress?ratioAt(stress,i,t):1;check(finite(v)&&v>0,'Invalid calendar stress');prefix[t+1]=prefix[t]+v/p.calendar_years;}
    const nextCache=new Map();
    function nextDue(start,cycleTau){
     const k=start+':'+cycleTau;if(nextCache.has(k))return nextCache.get(k);
     let next=Math.min(T,start+cycleTau);
     for(let t=start+1;t<=next;t++)if(prefix[t]-prefix[start]>=1-EPS){next=t;break;}
     nextCache.set(k,next);return next;
    }
    const clock=nu=>thermal?(nu>0?Math.max(1,Math.ceil(p.cycle_limit/nu-EPS)):Infinity):interval(p,nu);
    function addRenewals(start,mass,tau,includeStart=false,opening=false){
     for(let t=includeStart?start:(thermal?nextDue(start,tau):start+tau);t<T;t=thermal?nextDue(t,tau):t+tau){
      quantity.batRepl_nominal[t]+=mass/p.effective_DoD;
      if(!opening||t>start)quantity.adoptedRetired_nominal[t]+=mass/p.effective_DoD;
     }
    }
    if(sumU>0){
     if(newTauConstant!==null)newTauMass.set(newTauConstant,sumU);
     else if(basisK){const design=openingChargeCurve(1,perU,fn,du,fold,p.eta,p.hours,p.duty),[a,z]=cdfBounds(yieldCDF,i);
      for(let j=a;j<z;j++){const charge=valueAt(design,yieldCDF.x[j]),nu=perU>0?charge*Math.sqrt(p.eta)/perU:0,tau=clock(nu);newTauMass.set(tau,(newTauMass.get(tau)||0)+perU*yieldCDF.area[j]);}}
     else{const design=rhoChargeCurve(b,fn,du,fold,p.eta,p.hours,p.duty),[a,z]=cdfBounds(rhoCDF,i);
      for(let j=a;j<z;j++){const zeta=rhoCDF.x[j],unit=fn*b*zeta,nu=unit>0?valueAt(design,zeta)*Math.sqrt(p.eta)/unit:0,tau=clock(nu);newTauMass.set(tau,(newTauMass.get(tau)||0)+fn*b*rhoCDF.w1[j]);}}
    }
    if(u0>0){
     const a=Number(openingCDF.parentOffsets[i]),z=Number(openingCDF.parentOffsets[i+1]);
     const design=openingChargeCurve(p0,u0,f0,du,fold,p.eta,p.hours,p.duty);
     for(let g=a;g<z;g++){const due=Number(openingCDF.due[g]),groupArea=cdfTotal(openingCDF,g,'prefixA'),mass=new Map();
      if(newTauConstant!==null)mass.set(newTauConstant,groupArea);
      else{const [x0,x1]=cdfBounds(openingCDF,g);for(let j=x0;j<x1;j++){const nu=valueAt(design,openingCDF.x[j])*Math.sqrt(p.eta)/u0,tau=clock(nu);mass.set(tau,(mass.get(tau)||0)+openingCDF.area[j]*(openingCDF.groupWeight?openingCDF.groupWeight[g]:1));}}
      oldGroups.push({g,due,area:groupArea,tauArea:mass});
      if(due<T)quantity.legacyFirst[due]+=u0*groupArea/.9;
      for(const [tau,A]of mass)addRenewals(due,u0*A,tau,true,true);
     }
    }
    const increments=new Float64Array(T),cumPV=new Float64Array(T);let previous=p0,cumulative=0;
    const initialInv=parent.openingInverter||parent.inputs?.openingInverter;
    check(initialInv,'Opening inverter phase vector required');
    const invRenewed=new Float64Array(T),initialInvFirst=new Float64Array(T);let openingRenewed=0;
    for(let t=0;t<T;t++){
     const rawFirst=Number(initialInv[i*T+t]);
     check(rawFirst>=-1e-10*Math.max(1,getVector('p0',i)),'Opening phase inversion produced a negative initial cohort');
     initialInvFirst[t]=Math.max(0,rawFirst);openingRenewed+=initialInvFirst[t];
     invRenewed[t]=p0>0?Math.min(1,openingRenewed/getVector('p0',i)):1;
    }
    if(p0>0)check(Math.abs(openingRenewed-getVector('p0',i))<1e-6+1e-9*getVector('p0',i),'Opening inverter first phases do not cover initial capacity');
    for(let t=0;t<T;t++){
     const target=p0+(cap*G[t]-p0)*parent.progress[t],increment=target-previous;previous=target;check(increment>=-1e-10,'Roof/deployment path generated negative new installation');increments[t]=Math.max(0,increment);cumulative+=increments[t];cumPV[t]=cumulative;
     const j=t;quantity.newPV[j]=increments[t]*area;quantity.newBat_nominal[j]=increments[t]*sumU/p.effective_DoD;quantity.newHouse[j]=increments[t]*sumU;
     for(let origin=t-p.module_years;origin>=0;origin-=p.module_years)quantity.modRepl[j]+=increments[origin]*area;
     for(let origin=t-p.inverter_years;origin>=0;origin-=p.inverter_years)quantity.invRepl[j]+=increments[origin]*area;
     for(let origin=t-p.housing_years;origin>=0;origin-=p.housing_years)quantity.houseRepl[j]+=increments[origin]*sumU;
     const md=getVector('modDue',i),id=getVector('invDue',i),hd=getVector('houseDue',i);
     for(let first=0;first<=t;first++)if((t-first)%p.module_years===0)quantity.modRepl[j]+=Number(input.openingFirstModule[i*T+first])*area/normArea;
     if(p.inverter_years===15){for(let first=0;first<=t;first++)if((t-first)%15===0)quantity.invRepl[j]+=initialInvFirst[first]*area/normArea;}
     else if(p0>0){
      // Each original first-due phase is retained. Its descendants use the new interval.
      for(let first=0;first<=t;first++)if((t-first)%p.inverter_years===0)
       quantity.invRepl[j]+=initialInvFirst[first]*area/normArea;
     }
     for(let first=0;first<=t;first++)if((t-first)%p.housing_years===0)quantity.houseRepl[j]+=Number(input.openingFirstHouse[i*T+first])*area/normArea;
     if(!thermal)for(const [tau,mass]of newTauMass)for(let origin=t-tau;origin>=0;origin-=tau){const amount=increments[origin]*mass/p.effective_DoD;quantity.batRepl_nominal[j]+=amount;quantity.adoptedRetired_nominal[j]+=amount;}
    }
    if(thermal)for(const [tau,mass]of newTauMass)for(let origin=0;origin<T;origin++)if(increments[origin]>0)addRenewals(origin,increments[origin]*mass,tau);
    const ymin=parent.minY?Number(parent.minY[i]):yieldCDF.x[Number(yieldCDF.offsets[i])],rhomax=rhoCDF.x[Number(rhoCDF.offsets[i+1])-1];
    const sameOld=p.eta===.85&&p.hours===2.5&&p.duty===1;
    let lastR=NaN,lastValues=null;
    for(let t=0;t<T;t++){
     const j=t,ratio=R==='HOLD'?fold:R?ratioAt(R,i,t):1;check(finite(ratio)&&ratio>0,'Invalid climate multiplier');
     const ratioNew=ratio*pvGain*invGain;
     const ratioOld=ratio*(input.openingGain?input.openingGain[getVector('countryIndex',i)*T+t]:1);
     const operatingKey=ratioNew+'::'+ratioOld;
     let curves=lastR===operatingKey?lastValues:null;
     if(!curves){
      const newCurve=basisK?openingChargeCurve(1,perU,fn,du,ratioNew,p.eta,p.hours,p.duty):rhoChargeCurve(b,fn,du,ratioNew,p.eta,p.hours,p.duty);
      const newCharge=basisK?integrate(newCurve,yieldCDF,i):integrate(newCurve,rhoCDF,i,'prefixW','prefixW1');
      const oldCurve=openingChargeCurve(p0,u0,f0,du,ratioOld,.85,2.5,1),afterCurve=sameOld?oldCurve:openingChargeCurve(p0,u0,f0,du,ratioOld,p.eta,p.hours,p.duty);
      let oldTotal=0,afterTotal=0;
      if(u0>0){if(yieldCDF){oldTotal=integrate(oldCurve,yieldCDF,i);afterTotal=sameOld?oldTotal:integrate(afterCurve,yieldCDF,i);}
       else for(const group of oldGroups){oldTotal+=integrate(oldCurve,openingCDF,group.g);afterTotal+=integrate(afterCurve,openingCDF,group.g);}}
      const oldMinimum=u0>0?valueAt(oldCurve,ymin)*.85/u0:Infinity,afterMinimum=u0>0?valueAt(afterCurve,ymin)*p.eta/u0:Infinity;
      const newMinimum=sumU>0?(basisK?valueAt(newCurve,ymin)*p.eta/perU:valueAt(newCurve,rhomax)*p.eta/(fn*b*rhomax)):Infinity;
      curves={newCurve,newCharge,oldCurve,afterCurve,oldTotal,afterTotal,oldMinimum,afterMinimum,newMinimum};lastR=operatingKey;lastValues=curves;
     }
     let oldCharge=0,oldDischarge=0,beforeArea=0;
     const beforeFraction=g=>t<g.due?1:t>g.due?0:Number(openingCDF.eventFraction[g.g]);
     if(u0>0){for(const group of oldGroups)beforeArea+=beforeFraction(group)*group.area;
      if(sameOld){oldCharge=curves.oldTotal;oldDischarge=oldCharge*.85;}
      else{const w=beforeArea/area;oldCharge=w*curves.oldTotal+(1-w)*curves.afterTotal;oldDischarge=w*curves.oldTotal*.85+(1-w)*curves.afterTotal*p.eta;}
     }
     const newCharge=cumPV[t]*curves.newCharge,newDischarge=newCharge*p.eta,charge=oldCharge+newCharge,discharge=oldDischarge+newDischarge,loss=charge-discharge;
     const auxiliary=(u0*(beforeArea*22.5+(area-beforeArea)*p.standby_W)+cumPV[t]*sumU*p.standby_W)*coef;
     const newMargin=curves.newMinimum-.5*p.standby_W*coef;
     const oldMargin=beforeArea>0?curves.oldMinimum-.5*22.5*coef:Infinity;
     const afterMargin=area-beforeArea>Math.max(1e-7,area*1e-12)?curves.afterMinimum-.5*p.standby_W*coef:Infinity;
     lowestNewMargin=Math.min(lowestNewMargin,newMargin);lowestOpeningMargin=Math.min(lowestOpeningMargin,oldMargin,afterMargin);
     let pvAux;
     if(newMargin>=-1e-9&&oldMargin>=-1e-9&&afterMargin>=-1e-9)pvAux=.5*auxiliary;
     else if(!(u0>0)){
      const halfNew=basisK?lineCurve(0,.5*cumPV[t]*perU*p.standby_W*coef):lineCurve(.5*cumPV[t]*fn*b*p.standby_W*coef,0);
      const newD=scaleCurve(curves.newCurve,cumPV[t]*p.eta),combined=minCurves(halfNew,newD);
      pvAux=basisK?integrate(combined,yieldCDF,i):integrate(combined,rhoCDF,i,'prefixW','prefixW1');
     }else if(basisK){
      pvAux=0;for(const group of oldGroups){const f=beforeFraction(group);for(const [before,weight]of [[true,f],[false,1-f]]){if(!weight)continue;const oldD=scaleCurve(before?curves.oldCurve:curves.afterCurve,before?.85:p.eta),newD=scaleCurve(curves.newCurve,cumPV[t]*p.eta);
       const halfAux=lineCurve(0,.5*(u0*(before?22.5:p.standby_W)+cumPV[t]*perU*p.standby_W)*coef);
       pvAux+=weight*integrate(minCurves(halfAux,addCurves(oldD,newD)),openingCDF,group.g);}}
     }else{
      // Exact joint fallback only when separation cannot be proved. UTIL0
      // commonly reaches this branch before the opening battery's first due.
      nonlinearFallbackParents++;pvAux=0;
      if(p.duty===0&&beforeArea<=Math.max(1e-7,area*1e-12))pvAux=0;
      else{const joint=await ensureJoint(),g0=Number(joint.parentOffsets[i]),g1=Number(joint.parentOffsets[i+1]);
       for(let g=g0;g<g1;g++){for(const [before,weight]of [[true,beforeArea/area],[false,1-beforeArea/area]]){if(weight<=0||p.duty===0&&!before)continue;
        const zeta=Number(joint.rho[g]),newDperY=valueAt(curves.newCurve,zeta)*cumPV[t]*p.eta;
        const oldD=scaleCurve(before?curves.oldCurve:curves.afterCurve,before?.85:p.eta);
        const halfAux=lineCurve(.5*cumPV[t]*fn*b*zeta*p.standby_W*coef,.5*u0*(before?22.5:p.standby_W)*coef);
        pvAux+=weight*integrate(minCurves(halfAux,addCurves(oldD,lineCurve(newDperY,0))),joint,g);jointQueries++;}}
      }
     }
     const generation=(p0*ratioOld+cumPV[t]*ratioNew)*sumY,gridAux=auxiliary-pvAux,useful=generation-loss-pvAux;
     check(pvAux>=-1e-4&&gridAux>=-1e-4&&useful>=-1e-4,'Negative energy after exact auxiliary allocation');
     energy.generation[j]=generation;energy.useful[j]=useful;energy.loss[j]=loss;energy.pvAux[j]=pvAux;energy.gridAux[j]=gridAux;energy.charge[j]=charge;energy.discharge[j]=discharge;
    }
    const country=getVector('countryIndex',i),anchor=getVector('ef2025',i);
    check(country>=0&&country<NC&&anchor>=0&&finite(anchor),'Nonnegative registered country-specific EF2025 anchor required for exact country weighting');
    for(let t=0;t<T;t++){const j=country*T+t;
     for(const name of QTY)countryQuantity[name][j]+=quantity[name][t];
     for(const name of ENERGY)countryEnergy[name][j]+=energy[name][t];
     designEFWeightedUseful[j]+=energy.useful[t]*anchor;designEFWeightedAux[j]+=energy.gridAux[t]*anchor;}
    if((i&63)===63){onProgress?.({stage:'physical',done:i+1,total:N,selection:s});await tick();}
   }
   const value={selection:s,parameters:p,N,NC,T,aggregation:'country_exact',quantity:countryQuantity,energy:countryEnergy,designEFWeightedUseful,designEFWeightedAux,units:'country additive total kWh/kWp and kg-based factors; carbon not yet applied',diagnostics:{nonlinearFallbackParentYears:nonlinearFallbackParents,jointQueries,lowestNewMargin,lowestOpeningMargin,referenceCycleYear:'2025 design Yold (cleanY*Fold), frozen through2100',physical_ms:(typeof performance!=='undefined'?performance.now():Date.now())-began}};
   if(job===generation)cache={key:pk,value};return value;
  })();pending={key:pk,promise};try{return await promise;}finally{if(pending?.promise===promise)pending=null;}
 }

 let constrainedCache=null,constrainedPending=null,constrainedGeneration=0;
 async function buildPhysical(selection,onProgress){
  const {selection:s,params:p}=resolve(selection);
  if(s.exportConstraint==='UNLIMITED')return buildUnlimitedPhysical(s,onProgress);
  const pk=physicalKey(s,p)+'::'+s.exportConstraint;
  if(constrainedCache?.key===pk)return constrainedCache.value;if(constrainedPending?.key===pk)return constrainedPending.promise;
  const job=++constrainedGeneration,promise=(async()=>{
   // Matched hardware/replacement clocks come from the unchanged reference
   // design-cycle algorithm; only actual operating energy is re-evaluated.
   const base=await buildUnlimitedPhysical({...s,exportConstraint:'UNLIMITED'},onProgress),G=roof(s),R=weather(s),began=Date.now();
   const e=Object.fromEntries(ENERGY.map(k=>[k,new Float64Array(NC*T)])),weightedUseful=new Float64Array(NC*T),weightedAux=new Float64Array(NC*T);
   check((p.pv_system_gain??1)===1&&(p.inverter_gain??1)===1,'Bounded PV/inverter performance gains require explicit support');
   const beta={CAP50:.5,CAP25:.25,CAP0:0}[s.exportConstraint],fixedK=p.capacity_basis==='nominal_kWh_per_kWp_equipped_PV';if(fixedK)await ensureYield();
   const nightAlpha=input.exportAssumptions?.nightAlpha??1;
   for(let i=0;i<N;i++){
    if(job!==constrainedGeneration)throw new Error('Constrained physical calculation superseded by a newer selection');
    const norm=parentArea(i),area=areaSum(i),sumY=yieldSum(i),p0=getVector('p0',i)/norm,u0=getVector('u0',i)/norm,cap=getVector('cap0',i)/norm,f0=getVector('fc',i),fn=p.share==null?f0:p.share,du=getVector('du',i),fold=getVector('Fold',i);
    const perU=fixedK?fn*p.nominal_kWh_per_kWp*p.effective_DoD*p.size_multiplier:0,b=fold*(1-du)*p.size_multiplier;
    const groups=[];if(u0>0)for(let g=Number(openingCDF.parentOffsets[i]);g<Number(openingCDF.parentOffsets[i+1]);g++)groups.push({g,due:Number(openingCDF.due[g]),fraction:Number(openingCDF.eventFraction[g])});
    const c=getVector('countryIndex',i),anchor=getVector('ef2025',i);let lastRatio=NaN,pre=null;
    for(let t=0;t<T;t++){
     const ratio=R==='HOLD'?fold:R?ratioAt(R,i,t):1,installedNew=(cap*G[t]-p0)*parent.progress[t];check(installedNew>=-1e-10,'Negative bounded deployment');
     if(ratio!==lastRatio&&s.resolution==='legacy1deg'){
      const Y=getVector('Yold',i)/fold,common={direct:du,ratio,exportRatio:beta,nightAlpha,cleanY:Y,standby_hours_year:p.standby_hours_year,standby_usable_unit_kWh:p.standby_usable_unit_kWh};
      const newer=scalarConstrainedOperation({...common,pvCapacity:1,usable:fixedK?perU:fn*b*getVector('rho',i)*Y,share:fn,eta:p.eta,hours:p.hours,duty:p.duty,standby_W:p.standby_W});
      const before=scalarConstrainedOperation({...common,pvCapacity:p0,usable:u0,share:f0,eta:.85,hours:2.5,duty:1,standby_W:22.5}),after=scalarConstrainedOperation({...common,pvCapacity:p0,usable:u0,share:f0,eta:p.eta,hours:p.hours,duty:p.duty,standby_W:p.standby_W});
      pre={newer:Object.fromEntries(ENERGY.map(k=>[k,newer[k]*area])),old:[{due:getVector('batDue',i),before:Object.fromEntries(ENERGY.map(k=>[k,before[k]*area])),after:Object.fromEntries(ENERGY.map(k=>[k,after[k]*area]))}],oldNoBattery:null};lastRatio=ratio;
     }
     if(ratio!==lastRatio){
      const common={direct:du,ratio,exportRatio:beta,nightAlpha,standby_hours_year:p.standby_hours_year,standby_usable_unit_kWh:p.standby_usable_unit_kWh};
      const newCurves=constrainedCurves({...common,pvCapacity:1,usable:perU,usableRhoCoeff:fn*b,variable:fixedK?'Y':'rho',share:fn,eta:p.eta,hours:p.hours,duty:p.duty,standby_W:p.standby_W});
      const newer=Object.fromEntries(ENERGY.map(k=>[k,fixedK?integrate(newCurves[k],yieldCDF,i):integrate(newCurves[k],rhoCDF,i,'prefixW','prefixW1')]));
      const openingCommon={...common,ratio:ratio*(input.openingGain?input.openingGain[c*T+t]:1)},before=constrainedCurves({...openingCommon,pvCapacity:p0,usable:u0,share:f0,eta:.85,hours:2.5,duty:1,standby_W:22.5}),after=(p.eta===.85&&p.hours===2.5&&p.duty===1&&p.standby_W===22.5)?before:constrainedCurves({...openingCommon,pvCapacity:p0,usable:u0,share:f0,eta:p.eta,hours:p.hours,duty:p.duty,standby_W:p.standby_W});
      const old=groups.map(g=>({due:g.due,fraction:g.fraction,weight:openingCDF.groupWeight[g.g]})),oldBefore=Object.fromEntries(ENERGY.map(k=>[k,integrate(before[k],yieldCDF,i)])),oldAfter=after===before?oldBefore:Object.fromEntries(ENERGY.map(k=>[k,integrate(after[k],yieldCDF,i)]));
      // No opening battery still has PV direct use/export/curtailment.
      const oldNoBattery=u0>0?null:Object.fromEntries(ENERGY.map(k=>[k,valueAt(before[k],1)*sumY]));
      pre={newer,old,oldNoBattery,oldBefore,oldAfter};lastRatio=ratio;
     }
     const j=c*T+t;for(const k of ENERGY){let v=installedNew*pre.newer[k];if(pre.oldNoBattery)v+=pre.oldNoBattery[k];else{let w=0;for(const g of pre.old)w+=g.weight*(t<g.due?1:t>g.due?0:g.fraction);v+=w*pre.oldBefore[k]+(1-w)*pre.oldAfter[k];}
      const tolerance=1e-8*Math.max(1,(p0+installedNew)*ratio*sumY);check(Number.isFinite(v)&&v>=-tolerance,'Invalid bounded energy '+k);v=Math.max(0,v);e[k][j]+=v;if(k==='useful')weightedUseful[j]+=anchor*v;if(k==='gridAux')weightedAux[j]+=anchor*v;}
    }
    if((i&63)===63){onProgress?.({stage:'export-operation',done:i+1,total:N,selection:s});await tick();}
   }
   const value={...base,selection:s,energy:e,designEFWeightedUseful:weightedUseful,designEFWeightedAux:weightedAux,diagnostics:{...base.diagnostics,exportConstraint:s.exportConstraint,export_ratio:beta,night_load_alpha:nightAlpha,matchedHardware:true,operation:'12h sine PV / 12h flat night acceptance; curtailment-first PV-only charging',cap_reference:'clean2025 S0 unbuffered surplus peak, proportional to deployed PV',bounded_operation_ms:Date.now()-began}};
   if(job===constrainedGeneration)constrainedCache={key:pk,value};return value;
  })();constrainedPending={key:pk,promise};try{return await promise;}finally{if(constrainedPending?.promise===promise)constrainedPending=null;}
 }

 async function compute(selection,onProgress){
  const {selection:s,params:p}=resolve(selection),physical=await buildPhysical(s,onProgress),q=physical.quantity,e=physical.energy;
  const model=models.find(m=>m.id===s.iam);check(model,'Actual IAM inputs missing: '+s.iam);
  const ef=model.efRelative?.[s.background]||model.ef_country?.[s.background],mf=model.manufacturing?.[s.background];
  check(ef&&mf,'Matched actual grid/manufacturing background missing: '+s.iam+'/'+s.background);
  const national=input.countryManufacturing;
  check(national&&national.backgrounds&&national.country_codes,'Country manufacturing factors are required');
  check(JSON.stringify(national.country_codes)===JSON.stringify(codes),'Country manufacturing code order mismatch');
  const cmf=national.backgrounds[s.background];
  check(cmf&&cmf.module.length===NC*T&&cmf.inverter.length===NC*T,'Matched country manufacturing matrix missing');
  const annual=Object.fromEntries(ANNUAL.map(name=>[name,nestedMatrix(NC)]));
  const density=Number(parent.density||parent.density_kWp_m2),freight=Number(parent.freight),retirement=parent.retirement;
  check(density>0&&finite(freight)&&retirement,'PV manufacturing/retirement source constants incomplete');
  for(let country=0;country<NC;country++){
   for(let t=0;t<T;t++){
    const j=country*T+t,allMF=p.all_manufacturing_multiplier??1;
    check(allMF>0&&allMF<=1,'All-device manufacturing factor outside(0,1]');
    const pv=cmf.module[j]*allMF+(mf.mounting[t]*allMF+freight)/density+mf.electrical[t]*allMF,
      bf=p.module_manufacturing_kgCO2e_per_nominal_kWh*(p.manufacturing_profile==='fixed'?1:mf.battery[t]/mf.battery[0])*p.manufacturing_multiplier*allMF;
    const grid=Math.max(ratioAt(ef,country,t),0),newM=q.newPV[j]*(pv+cmf.inverter[j]*allMF)+q.newBat_nominal[j]*bf+q.newHouse[j]*mf.housing[t]*allMF;
    const replacement=q.modRepl[j]*pv+q.invRepl[j]*cmf.inverter[j]*allMF+q.batRepl_nominal[j]*bf+q.houseRepl[j]*mf.housing[t]*allMF;
    const treatment=q.modRepl[j]/density*retirement.module_kg_co2e_per_m2+q.invRepl[j]*retirement.inverter_kg_co2e_per_kwp_dc+q.legacyFirst[j]*retirement.lfp_hydromet_kg_co2e_per_nominal_kwh+q.adoptedRetired_nominal[j]*p.eol_factor_kgCO2e_per_nominal_kWh;
    const aux=physical.designEFWeightedAux[j]*grid,A=physical.designEFWeightedUseful[j]*grid,H=newM+replacement+treatment+aux;
    for(const [name,value]of Object.entries({newManufacturing:newM,replacementManufacturing:replacement,treatment,gridAux:aux,A,H,net:H-A}))annual[name][country][t]+=value/1e12;
   }
   if((country&63)===63){onProgress?.({stage:'carbon',done:country+1,total:NC,selection:s});await tick();}
  }
  const cumulative={C:nestedMatrix(NC),H:nestedMatrix(NC),A:nestedMatrix(NC)};
  for(let c=0;c<NC;c++)for(let t=0;t<T;t++)for(const [name,source]of [['C','net'],['H','H'],['A','A']])cumulative[name][c][t]=(t?cumulative[name][c][t-1]:0)+annual[source][c][t];
  const annualGlobal=Object.fromEntries(ANNUAL.map(name=>[name,YEARS.map((_,t)=>annual[name].reduce((sum,row)=>sum+row[t],0))]));
  const global={...Object.fromEntries(['C','H','A'].map(name=>[name,YEARS.map((_,t)=>cumulative[name].reduce((sum,row)=>sum+row[t],0))])),negative:YEARS.map((_,t)=>cumulative.C.filter(row=>row[t]<0).length)};
  const geographic=regions.map(r=>{const ids=countries.map((c,j)=>c.region===r.id?j:-1).filter(j=>j>=0);const out={id:r.id,n:ids.length};
   for(const name of ['A','H','C'])out[name]=YEARS.map((_,t)=>ids.reduce((sum,c)=>sum+cumulative[name][c][t],0));
   out.negative=YEARS.map((_,t)=>ids.filter(c=>cumulative.C[c][t]<0).length);out.annual=Object.fromEntries(ANNUAL.map(name=>[name,YEARS.map((_,t)=>ids.reduce((sum,c)=>sum+annual[name][c][t],0))]));return out;});
  const endCountry=Object.fromEntries(ANNUAL.map(name=>[name,annual[name].map(row=>row.reduce((sum,x)=>sum+x,0))]));
  const bubbleFields=['newManufacturing','replacementManufacturing','treatment','gridAux','A','H'];
  const bubbles=regions12.map(r=>{const ids=map12.map((id,j)=>id===r.id?j:-1).filter(j=>j>=0),out={id:r.id,n:ids.length,negativeCountryCount:ids.filter(c=>cumulative.C[c][T-1]<0).length};
   for(const name of bubbleFields)out[name]=ids.reduce((sum,c)=>sum+endCountry[name][c],0);out.C=ids.reduce((sum,c)=>sum+cumulative.C[c][T-1],0);return out;});
  const bubGlobal={n:NC,negativeCountryCount:global.negative[T-1]};for(const name of bubbleFields)bubGlobal[name]=endCountry[name].reduce((sum,x)=>sum+x,0);bubGlobal.C=global.C[T-1];
  const groupNames=['all_negative','once_to_negative','repeated','once_to_positive','all_positive'],entries=cumulative.C.map(classify),counts=Object.fromEntries(groupNames.map(name=>[name,entries.filter(e=>e.id===name).length])),allZero=entries.filter(e=>e.id==='all_zero').length;
  const trajectorySummary={counts,entries:entries.map(({events,...rest})=>rest),total:NC,classified:NC-allZero,allZero,zeroYears:entries.reduce((sum,e)=>sum+e.zeroYears,0)};
  const id=key(s),values=bubbles.flatMap(r=>[r.A,r.H]).filter(v=>v>0),maxAbs=Math.max(...bubbles.map(r=>Math.abs(r.C)),1e-12),domain=values.length?[10**Math.floor(Math.log10(Math.min(...values))-1),10**Math.ceil(Math.log10(Math.max(...values))+1)]:[.1,10];
  const diagnostics={...physical.diagnostics,energy_totals:Object.fromEntries(ENERGY.map(name=>[name,e[name].reduce((sum,x)=>sum+x,0)])),weatherChangesHardware:s.climateCoupling==='PV_BATTERY',exactWeightedCDF:true,noRepresentativeFineClimate:true};
  const energyCountry=Object.fromEntries(ENERGY.map(k=>[k,k==='export'&&s.exportConstraint==='UNLIMITED'?null:Array.from({length:NC},(_,c)=>Array.from(e[k].subarray(c*T,(c+1)*T)))]));
  const energyGlobal=Object.fromEntries(ENERGY.map(k=>[k,energyCountry[k]===null?null:YEARS.map((_,t)=>energyCountry[k].reduce((sum,row)=>sum+row[t],0))]));
  const out={energyCountry,energyGlobal,exportComparison:null,schema:'pv-wrf-export-constraint-account/1.0',id,key:id,sourceAccountId:id,resolution:s.resolution,selection:s,...s,iamModel:model.model||model.label||s.iam,iamVersion:model.version||2,weather:s.model?s.model+'_'+s.climate:s.climate,years:YEARS.slice(),referenceAccountId:registry.reference_account_id||registry.referenceAccount||'STORAGE_REF_LFP_20261023',parameters:p,global,countries:cumulative,annualCountry:annual,annualGlobal,regions:geographic,bubble:{key:id,regions:bubbles,global:bubGlobal},bubbleMeta:{regions:regions12,scales:{xDomain:domain,hDomain:domain,maxAbsC:maxAbs},currentScenarioAreaScale:true},trajectorySummary,events:{countries:entries.map((e,i)=>({code:codes[i],events:e.events})),global:classify(global.C)},diagnostics,provenance:{reference_account_id:registry.reference_account_id||'STORAGE_REF_LFP_20261023',method:'Exact piecewise-linear weighted-CDF integration with joint auxiliary clamp when required',cycle_reference:'Frozen2025 designYold cycling constraint; PV_BATTERY adds monthly-temperature-driven cumulative calendar damage, not a full SOH/DoD aging model',physical_climate_coupling:s.climateCoupling,battery_thermal_response:s.batteryClimateResponse,resolution:s.resolution},units:{annualCountry:'Gt CO2e/year',countries:'Gt CO2e cumulative'}};
  onProgress?.({stage:'complete',done:N,total:N,selection:s});return out;
 }
 return Object.freeze({compute,buildPhysical,resolve,key,clearCache:()=>{cache=null;constrainedCache=null;generation++;constrainedGeneration++;},dimensions:{N,NC,T},helpers});
}
const helpers=Object.freeze({constrainedCurves,constrainedCurvesOriginal,scalarConstrainedOperation,maxCurves,positiveCurve,lowerBound,cdfTotal,cdfRange,lineCurve,valueAt,scaleCurve,addCurves,minCurves,sumCappedTerms,integrate,openingChargeCurve,rhoChargeCurve,scalarOperation,interval,constantInterval,classify,weights:WEIGHTS.slice()});
return Object.freeze({createCore,helpers,annualFields:ANNUAL.slice(),quantityFields:QTY.slice(),energyFields:ENERGY.slice()});
});
