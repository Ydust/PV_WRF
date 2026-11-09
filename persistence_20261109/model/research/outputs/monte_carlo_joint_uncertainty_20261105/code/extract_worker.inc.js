 const base = R + '/outputs/figures3_5_unified_time_metric_20261102';
 const ages = R + '/supplementary_figures/SI_Figure2_robustness_20261105';
 const eligible = ['REF__UNLIMITED', 'FIG4_M_BEST__UNLIMITED', 'FIG4_L_BEST__UNLIMITED',
                   'FIG4_E_BEST__UNLIMITED', 'STORAGE_FC0__CAP50'];
 const configMap = new Map(configs.map(item => [item.id, item]));
 const currentMap = new Map(read(base + '/source_data/account_manifest.json')
   .map(item => [item.background + '__' + item.configuration_id, item]));
 const factoryPath = R + '/outputs/country_manufacturing_recalculation_20261028/source_data/adopted_country_device_manufacturing_origins.json';
 const moduleOrigins = new Map(read(factoryPath).filter(item => item.device === 'MODULE')
   .map(item => [item.country, item.manufacturer]));
 assert.equal(moduleOrigins.size, NC);
 const targets = codes.map(code => moduleOrigins.get(code) === 'CHN');
 const sourceFiles = [
   base + '/code/history_operation_core.js', base + '/code/recompute.cjs',
   base + '/source_data/account_manifest.json', factoryPath, mf,
   P + '/source_data/frozen_inputs.json', cf,
   R + '/outputs/baseline_replacement_package_20261031/source_data/candidate_parent_opening_interfaces.npz',
 ];
 if (ageCase) {
   const duePath = ages + '/source_data/' + ageCase + '_first_due.npz';
   const compPath = ages + '/source_data/' + ageCase + '_PV_components.json';
   const revised = readNpz(duePath);
   input.openingFirstModule = revised.module_first_parent_normalized;
   parent.openingInverter = revised.inverter_first_parent_normalized;
   const replaceDevices = ['PV_MODULE_AND_LINKED_BOS', 'INVERTER'];
   f.components = f.components.filter(item => !replaceDevices.includes(item.device)).concat(read(compPath));
   f.history = f.history.filter(item => item.case === ageCase).map(item => ({ ...item, case: 'CENTRAL' }));
   assert.equal(f.history.length, NC);
   sourceFiles.push(duePath, compPath);
 }
 const core = require(base + '/code/history_operation_core.js').createCore(input);
 const fields = ['newManufacturing', 'replacementManufacturing', 'treatment', 'gridAux', 'A', 'net'];
 const result = [];
 let last = Date.now();
 for (const id of eligible) {
   const cfg = configMap.get(id);
   assert(cfg);
   input.openingGain = gainVector(cfg.parameters, codes);
   for (const background of BGS) {
     const selection = { ...cfg.selection, background, roof: 'SSP2', climate: 'SSP245', climateCoupling: 'PV_TW' };
     const oldId = background + '__' + id;
     const old = currentMap.get(oldId);
     assert(old);
     const oldPath = base + '/accounts/' + oldId + '.json.gz';
     assert.equal(sha(oldPath), old.sha256);
     const former = unzip(oldPath);
     const modeled = await core.compute(selection, progress => {
       if (Date.now() - last > 45000) {
         console.log(branch, background, id, progress.stage, progress.done);
         last = Date.now();
       }
     });
     checkEnergy(modeled);
     continuous(modeled, codes);
     assert.deepEqual(modeled.parameters, former.parameters);
     const { quantity: q } = await core.buildPhysical(selection);
     const factors = input.countryManufacturing.backgrounds[background].module;
     const weight = modeled.parameters.all_manufacturing_multiplier ?? 1;
     const newModule = codes.map((_, c) => modeled.years.map((_, t) => {
       const j = c * T + t;
       return targets[c] ? q.newPV[j] * factors[j] * weight / 1e12 : 0;
     }));
     const replModule = codes.map((_, c) => modeled.years.map((_, t) => {
       const j = c * T + t;
       return targets[c] ? q.modRepl[j] * factors[j] * weight / 1e12 : 0;
     }));
     let maxCentralError = 0;
     for (let c = 0; c < NC; c++) {
       for (let t = 0; t < T; t++) {
         assert(newModule[c][t] >= 0 && newModule[c][t] <= modeled.annualCountry.newManufacturing[c][t] + 1e-12);
         assert(replModule[c][t] >= 0 && replModule[c][t] <= modeled.annualCountry.replacementManufacturing[c][t] + 1e-12);
         if (!ageCase) {
           for (const k of fields) maxCentralError = Math.max(maxCentralError,
             Math.abs(modeled.annualCountry[k][c][t] - former.annualCountry[k][c][t]));
           maxCentralError = Math.max(maxCentralError, Math.abs(modeled.countries.C[c][t] - former.countries.C[c][t]));
         }
       }
     }
     if (!ageCase) {
       assert(maxCentralError < 1e-9, 'Central model replay mismatch');
       assert.deepEqual(modeled.openingBalances, former.openingBalances);
       assert.deepEqual(modeled.classifications, former.classifications);
     } else {
       assert.deepEqual(modeled.annualCountry.newManufacturing, former.annualCountry.newManufacturing);
     }
     const slim = {
       branch, case: id, background, codes, years: modeled.years, opening: modeled.openingBalances,
       annual: Object.fromEntries(fields.map(k => [k, modeled.annualCountry[k]])),
       newChinaModuleManufacturing: newModule, replacementChinaModuleManufacturing: replModule,
       countryFirstLoss: modeled.classifications.map(x => x.first_loss_year),
       worldFirstLoss: modeled.events.global.first_loss_year, worldC2100: modeled.global.C.at(-1),
     };
     const filename = work + '/annual/' + branch + '__' + oldId + '.json.gz';
     fs.writeFileSync(filename, zlib.gzipSync(JSON.stringify(slim), { level: 2 }));
     result.push({ case: id, background, filename, sha256: sha(filename), centralAccountSHA256: old.sha256, maxCentralError });
     console.log(branch, background, id, modeled.events.global.first_loss_year, modeled.global.C.at(-1));
   }
 }
 assert.equal(result.length, eligible.length * BGS.length);
 fs.writeFileSync(work + '/annual/' + branch + '_manifest.json', JSON.stringify({
   branch, ageCase, manufacturer: 'CHN', installationCountriesWithChinaReference: targets.filter(Boolean).length,
   inputHashes: Object.fromEntries(sourceFiles.map(p => [p, sha(p)])), result,
 }, null, 2));
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
