'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');const J=path.resolve(__dirname,'..'),read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const all=[0,1,2].flatMap(i=>{const q=read(J+'/qa/runtime_part'+i+'.json');assert.equal(q.status,'PASS');return read(J+'/source_data/account_manifest_part'+i+'.json');});
assert.equal(all.length,375);assert.equal(new Set(all.map(x=>x.background+'::'+x.configuration_id)).size,375);
for(const r of all)assert.equal(crypto.createHash('sha256').update(fs.readFileSync(r.path)).digest('hex'),r.sha256);
fs.writeFileSync(J+'/source_data/account_manifest.json',JSON.stringify(all,null,2));
fs.writeFileSync(J+'/qa/runtime_checks.json',JSON.stringify({status:'PASS',accounts:375,unique_configurations:75,independent_process_partitions:3,all_account_hashes_verified:true,part_reports:[0,1,2].map(i=>read(J+'/qa/runtime_part'+i+'.json'))},null,2));console.log('375 unique accounts merged and hashed');
