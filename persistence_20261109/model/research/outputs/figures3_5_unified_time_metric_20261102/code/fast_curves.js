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
