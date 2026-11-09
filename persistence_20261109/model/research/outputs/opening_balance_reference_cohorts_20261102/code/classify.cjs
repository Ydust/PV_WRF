'use strict';
// Strict signs, with exact zeros skipped; no arbitrary Gt threshold or rounded years.
function classify(opening,values,years){
 if(!Number.isFinite(opening)||values.length!==years.length||!values.every(Number.isFinite))throw Error('Invalid continuous account');
 let last=Math.sign(opening),benefit=opening<0,formation=null,loss=null;const events=[];
 for(let t=0;t<values.length;t++){
  const sign=Math.sign(values[t]);if(sign===0)continue;
  if(sign<0&&!benefit){benefit=true;formation=years[t];}
  if(last&&last!==sign){events.push({year:years[t],direction:last<0?'negative_to_positive':'positive_to_negative'});if(last<0&&sign>0&&loss===null)loss=years[t];}
  last=sign;
 }
 const state=loss!==null?(opening<0?'opening_benefit_then_lost':'formed_then_lost'):(benefit?'benefit_without_observed_loss':'no_observed_benefit');
 const afterLoss=loss===null?[]:events.filter(x=>x.year>loss);
 return {state,opening_sign:Math.sign(opening),formation_year:formation,first_loss_year:loss,
  first_positive_to_negative_year:events.find(e=>e.direction==='positive_to_negative')?.year??null,
  recovery_after_loss:afterLoss.some(e=>e.direction==='positive_to_negative'),
  recovered_at_2100:loss!==null&&values.at(-1)<0,
  positive_at_2100:values.at(-1)>0,terminal_zero:values.at(-1)===0,
  repeated_crossings:events.length>=2,event_count:events.length,events};
}
module.exports={classify};
if(require.main===module){
 const a=require('assert');
 a.equal(classify(0,[-1,1],[2025,2026]).state,'formed_then_lost');
 a.equal(classify(-1,[1,-1,1],[2025,2026,2027]).state,'opening_benefit_then_lost');
 a.equal(classify(-1,[1,-1,1],[2025,2026,2027]).first_loss_year,2025);
 a.equal(classify(1,[-1,0,0,1],[2025,2026,2027,2028]).first_loss_year,2028);
 a.equal(classify(0,[0,0],[2025,2026]).state,'no_observed_benefit');
 a.equal(classify(1,[-1,-2],[2025,2026]).state,'benefit_without_observed_loss');
 a.equal(classify(-1,[1,-1],[2025,2026]).recovered_at_2100,true);
 a.equal(classify(0,[-1,0],[2025,2026]).first_loss_year,null);
 a.equal(classify(0,[-1,0],[2025,2026]).terminal_zero,true);
 a.equal(classify(0,[-1e-15,1e-15],[2025,2026]).first_loss_year,2026);
 console.log('10 state/event boundary assertions PASS');
}
