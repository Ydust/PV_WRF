 const ranking=read(J+'/source_data/ranking.json');
 const pairs=[...new Map(BGS.map(bg=>[ranking.selected[bg].roof,ranking.selected[bg]])).values()];
 const [worker,workerCount]=process.argv.slice(3).map(Number);
 const branchId='PATHWAY_OPTIMAL_MATCHED_SSP_HISTORICAL_20261105';
 const accountPrior=R+'/outputs/supplementary_complete_figures_20261104/accounts';
 const groups=new Map(),report=[];
 const priced=new Set(['REF','FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED','STORAGE_FC0','STORAGE_FC50','STORAGE_FC100','STORAGE_CAP_HALF','STORAGE_CAP_DOUBLE','STORAGE_K05','STORAGE_K1','STORAGE_K2','STORAGE_UTIL50','STORAGE_UTIL0']);
 const tech=new Set(['FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED']);
 for(const cfg of configs){
   const key=JSON.stringify(cfg.parameters);
   if(!groups.has(key))groups.set(key,[]);
   groups.get(key).push(cfg);
   const id=cfg.id.split('__')[0];
   if(cfg.selection.exportConstraint==='UNLIMITED'&&tech.has(id))for(const ex of ['CAP50','CAP0']){
     groups.get(key).push({...cfg,id:id+'__'+ex,selection:{...cfg.selection,exportConstraint:ex},uses:[],onlyMap:true});
   }
 }
 const jobs=[...groups.values()].sort((a,b)=>Number(b.some(x=>x.id==='REF__UNLIMITED'))-Number(a.some(x=>x.id==='REF__UNLIMITED'))).flatMap(group=>pairs.map(pair=>({group,pair})));
 function writeCompressed(file,obj){
   const temp=file+'.tmp';
   fs.writeFileSync(temp,zlib.gzipSync(JSON.stringify(obj),{level:2}));
   fs.renameSync(temp,file);
 }
 const serial=o=>Object.fromEntries(Object.entries(o).map(([k,v])=>[k,Array.from(v)]));
 for(const [index,{group,pair}] of jobs.entries()){
   if(index%workerCount!==worker)continue;
   input.openingGain=gainVector(group[0].parameters,codes);
   const bgs=BGS.filter(bg=>ranking.selected[bg].roof===pair.roof);
   for(const cfg of group.sort((a,b)=>Number(b.selection.exportConstraint==='UNLIMITED')-Number(a.selection.exportConstraint==='UNLIMITED'))){
     const selectedBgs=cfg.onlyMap?bgs.filter(bg=>bg==='NZ2050'):bgs;
     for(const bg of selectedBgs){
       const id=bg+'__'+cfg.id, output=J+'/accounts/'+id+'.json.gz';
       const selection={...cfg.selection,background:bg,roof:pair.roof,climate:pair.climate};
       let a;
       if(fs.existsSync(output)){
         a=unzip(output);
         assert.equal(a.referenceAccountId,branchId);
         assert.deepEqual(a._codes,codes);
       }else{
         let last=Date.now();
         a=await core.compute(selection,p=>{if(Date.now()-last>30000){console.log(JSON.stringify({worker,id,...p}));last=Date.now();}});
         checkEnergy(a);
         continuous(a,codes);
         a.referenceAccountId=branchId;
         a.provenance={...a.provenance,historical_input_policy:cohorts.id,roof_climate_reference_rule:branchId};
         writeCompressed(output,a);
       }
       let maxReferenceError;
       if(cfg.id==='REF__UNLIMITED'){
         const prior=unzip(accountPrior+'/'+bg+'__ROOF_'+pair.roof+'__CLIMATE_'+pair.climate+'.json.gz');
         maxReferenceError=Math.max(...['C','H','A'].flatMap(k=>a.countries[k].flatMap((row,c)=>row.map((x,t)=>Math.abs(x-prior.countries[k][c][t])))));
         assert(maxReferenceError<1e-10,'Previously evaluated REF regression '+id+' '+maxReferenceError);
         assert(Math.abs(a.global.C.at(-1)-ranking.selected[bg].C2100_Gt)<1e-9,'Candidate ranking regression '+id);
       }
       report.push({id,path:output,configuration_id:cfg.id,background:bg,selection,sha256:sha(output),maxReferenceError});
       console.log(JSON.stringify({worker,complete:id,C2100:a.global.C.at(-1),maxReferenceError}));
       if(selection.exportConstraint==='UNLIMITED'&&priced.has(cfg.id.split('__')[0])){
         const file=J+'/quantities/'+pair.roof+'__'+cfg.id+'.json.gz';
         if(!fs.existsSync(file)){
           const p=await core.buildPhysical(selection);
           assert(p.valuation&&p.valuation.direct.length===NC*T);
           let error=0;
           for(const k of Object.keys(p.energy).filter(k=>a.energyCountry[k]!==null))for(let c=0;c<NC;c++)for(let t=0;t<T;t++){
             error=Math.max(error,Math.abs(p.energy[k][c*T+t]-a.energyCountry[k][c][t])/Math.max(1,a.energyCountry.generation[c][t]));
           }
           assert(error<1e-11,'Energy valuation replay '+id+' '+error);
           writeCompressed(file,{id:cfg.id,codes,parameters:p.parameters,selection,quantity:serial(p.quantity),valuation:serial(p.valuation),energy_replay_max_error:error,source_account:output,source_account_sha256:sha(output)});
         }
       }
     }
     fs.writeFileSync(J+'/source_data/worker_'+worker+'_manifest.json',JSON.stringify(report,null,2));
   }
   core.clearCache();
 }
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
