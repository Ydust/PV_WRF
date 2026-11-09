'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const { classify } = require('./model/research/outputs/opening_balance_reference_cohorts_20261102/code/classify.cjs');

const refDir = path.join(__dirname, 'data', 'reference');
const expected = JSON.parse(fs.readFileSync(path.join(__dirname, 'data/figure2/reference_curves.json'), 'utf8').replace(/^\uFEFF/, ''));
const counts = { CP: 24, NDC: 101, B2C: 106, NZ2050: 161, LD: 165 };
const lossYears = { CP: null, NDC: null, B2C: 2083, NZ2050: 2045, LD: 2052 };

for (const [pathway, expectedCount] of Object.entries(counts)) {
    const { years, countries } = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(refDir, pathway + '.json.gz'))));
    assert.deepEqual(years, Array.from({ length: 76 }, (_, i) => 2025 + i));
    assert.equal(new Set(countries.map(c => c.country)).size, 231);
    let losses = 0;
    const global = Array(years.length).fill(0);
    let opening = 0;
    for (const country of countries) {
        const result = classify(country.opening, country.annual_cumulative, years);
        assert.equal(result.first_loss_year, country.expected_first_loss, country.country);
        assert.equal(result.state, country.expected_state, country.country);
        losses += Number(result.first_loss_year !== null);
        opening += country.opening;
        country.annual_cumulative.forEach((value, index) => { global[index] += value; });
    }
    assert.equal(losses, expectedCount);
    global.forEach((value, index) => assert.ok(Math.abs(value - expected[pathway].C[index]) < 1e-9));
    const firstLoss = classify(opening, global, years).first_loss_year;
    assert.equal(firstLoss, lossYears[pathway]);
    console.log(pathway, 'countries with first loss:', losses, 'global first-loss year:', firstLoss);
}

