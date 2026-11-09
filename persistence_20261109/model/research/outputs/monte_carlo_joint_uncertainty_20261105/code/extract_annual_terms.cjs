'use strict';

// Reuse the current native-resolution model setup in memory. No active files are edited.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const work = path.resolve(__dirname, '..');
const baseCode = path.resolve(work, '../figures3_5_unified_time_metric_20261102/code');
const source = fs.readFileSync(path.join(baseCode, 'recompute.cjs'), 'utf8');
const cut = source.indexOf(' const {createCore,helpers}=require(');
assert(cut > 0);
const branches = {
  CENTRAL: null,
  AGE_MEAN: 'MEAN_AGE_ONLY',
  AGE_EARLY: 'EARLIEST_BUCKET_10Y_OLDER',
};
const branch = process.argv[2];
assert(Object.hasOwn(branches, branch));
fs.mkdirSync(path.join(work, 'annual'), { recursive: true });
const worker = fs.readFileSync(path.join(__dirname, 'extract_worker.inc.js'), 'utf8');
new Function('require', '__dirname', 'process', 'work', 'branch', 'ageCase', source.slice(0, cut) + worker)(
  require, baseCode, process, work, branch, branches[branch]
);
