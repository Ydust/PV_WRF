'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const research = path.resolve(root, '../..');
const previous = path.join(research, 'outputs/supplementary_complete_figures_20261104');
const source = path.join(research, 'supplementary_figures/SI_main_figures_complete_20261104/source_data/F2_roof_climate_80_curves.csv');
const backgrounds = ['CP', 'NDC', 'B2C', 'NZ2050', 'LD'];
const pairs = { SSP1: 'SSP126', SSP2: 'SSP245', SSP3: 'SSP370', SSP5: 'SSP585' };

function rankCandidates() {
  const records = fs.readFileSync(source, 'utf8').trim().split(/\r?\n/).slice(1).map(line => line.split(','));
  const candidates = {};
  for (const bg of backgrounds) {
    candidates[bg] = Object.entries(pairs).map(([roof, climate]) => {
      const rows = records.filter(row => row[0] === bg && row[1] === roof && row[2] === climate);
      if (rows.length !== 76 || rows.some((row, i) => Number(row[3]) !== 2025 + i || !Number.isFinite(Number(row[4])))) {
        throw Error('Invalid annual candidate series for ' + [bg, roof, climate].join(' / '));
      }
      return { roof, climate, C2100_Gt: Number(rows.at(-1)[4]) };
    }).sort((a, b) => a.C2100_Gt - b.C2100_Gt || a.roof.localeCompare(b.roof));
  }
  return { source, sha256: crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),
    criterion: 'lowest 2100 global cumulative net emissions; lexical SSP order for exact ties',
    candidates, selected: Object.fromEntries(backgrounds.map(bg => [bg, candidates[bg][0]])) };
}

if (!process.argv.includes('--worker')) {
  for (const dir of ['accounts', 'quantities', 'source_data', 'qa', 'figures']) {
    fs.mkdirSync(path.join(root, dir), { recursive: true });
  }
  const ranking = rankCandidates();
  fs.writeFileSync(path.join(root, 'source_data/ranking.json'), JSON.stringify(ranking, null, 2));
  const workers = Number(process.argv[2] || 3);
  if (!Number.isInteger(workers) || workers < 1) throw Error('Invalid worker count');
  console.log(JSON.stringify(ranking.selected));
  const jobs = Array.from({length: workers}, (_, i) => new Promise((resolve, reject) => {
    const job = spawn(process.execPath, [__filename, '--worker', String(i), String(workers)], {stdio: 'inherit', windowsHide: true});
    job.on('error', reject);
    job.on('exit', (code, signal) => code === 0 ? resolve() : reject(Error('Worker ' + i + ' exited ' + (code ?? signal))));
  }));
  Promise.allSettled(jobs).then(results => {
    for (const result of results) if (result.status === 'rejected') {
      console.error(result.reason);
      process.exitCode = 1;
    }
  });
} else {
  const template = fs.readFileSync(path.join(previous, 'code/compute_missing.cjs'), 'utf8');
  const cut = template.indexOf(' const by=Object.fromEntries(configs.map');
  if (cut === -1) throw Error('Verified model setup anchor missing');
  const model = template.slice(0, cut) + fs.readFileSync(path.join(__dirname, 'worker.inc.js'), 'utf8');
  new Function('require', '__dirname', 'process', model)(require, __dirname, process);
}
