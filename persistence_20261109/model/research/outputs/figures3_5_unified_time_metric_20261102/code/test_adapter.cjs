'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),{helpers:h}=require('./history_operation_core.js');
let checks=0;function near(a,b){assert(Math.abs(a-b)<1e-9*Math.max(1,Math.abs(a),Math.abs(b)),a+' != '+b);checks++;}
// Shared native parent slice: prefix sums reset within the original parent.
const base={x:[1,3,7],offsets:[0,3],prefixA:[2,7,18],prefixAY:[2,17,94]},virtual={...base,groupStart:[0,0],groupEnd:[3,3],groupWeight:[.35,.65]};
for(const curve of [h.lineCurve(2,5),h.minCurves(h.lineCurve(4,0),h.lineCurve(0,10)),h.positiveCurve(h.lineCurve(3,-5))]){
 const a=h.integrate(curve,base,0),b=h.integrate(curve,virtual,0),c=h.integrate(curve,virtual,1);near(b,.35*a);near(c,.65*a);near(b+c,a);
}
near(h.cdfTotal(virtual,0,'prefixA')+h.cdfTotal(virtual,1,'prefixA'),18);near(h.cdfRange(virtual,0,2,8,'prefixA'),.35*16);
// Direct scalar and unfactored-curve oracles across both variables and boundaries.
for(const variable of ['Y','rho'])for(const ratio of [.7,1,1.3])for(const share of [0,.3,1])for(const beta of [0,.25,.5])for(const duty of [0,.5,1]){
 const o={pvCapacity:1.2,ratio,share,direct:.4,eta:.9,hours:2.5,duty,exportRatio:beta,variable,usable:2.3,usableRhoCoeff:.002,standby_W:22.5},a=h.constrainedCurves(o),b=h.constrainedCurvesOriginal(o);
 for(const x of variable==='Y'?[100,650,1400,2800]:[100,650,1400,2800]){
  const scalar=h.scalarConstrainedOperation({...o,cleanY:variable==='Y'?x:1,rho:variable==='rho'?x:1});
  for(const k of Object.keys(a)){near(h.valueAt(a[k],x),h.valueAt(b[k],x));near(h.valueAt(a[k],x),scalar[k]);}
 }
}
// Replacing half way through a year: time-weight separately before/after, not a full year of both.
for(const f of [0,.25,.5,.9,1]){
 const old=h.scalarConstrainedOperation({cleanY:1400,pvCapacity:1,ratio:1,usable:2,share:.5,direct:.4,eta:.85,hours:2.5,duty:1,standby_W:22.5,exportRatio:0});
 const newer=h.scalarConstrainedOperation({cleanY:1400,pvCapacity:1,ratio:1,usable:2,share:.5,direct:.4,eta:.9,hours:2.5,duty:1,standby_W:5,exportRatio:0});
 const e=Object.fromEntries(Object.keys(old).map(k=>[k,f*old[k]+(1-f)*newer[k]]));
 near(e.generation,e.useful+e.loss+e.pvAux+e.curtailment);near(e.charge,e.discharge+e.loss);near(e.auxiliary,e.pvAux+e.gridAux);
}
// A joint PV/inverter upgrade at different times within one calendar year.
const cuts=[2026,2026.25,2026.75,2027],gain=[1,1.1,1.1*1.02];near(cuts.slice(1).reduce((s,x,i)=>s+(x-cuts[i])*gain[i],0),.25+.5*1.1+.25*1.122);
fs.mkdirSync(path.resolve(__dirname,'../qa'),{recursive:true});
fs.writeFileSync(path.resolve(__dirname,'../qa/adapter_unit_checks.json'),JSON.stringify({status:'PASS',checks,full_weighted_native_slices:true,partial_year_energy_conservation:true,distinct_joint_vintage_timing:true},null,2));
console.log(checks+' adapter assertions PASS');
