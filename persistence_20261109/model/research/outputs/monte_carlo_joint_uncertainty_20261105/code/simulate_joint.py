"""Propagate China's module inventory spread alongside the paired grid replay."""

import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


JOB = Path(__file__).resolve().parents[1]
PILOT = JOB.parent / "monte_carlo_persistence_pilot_20261105"
sys.path.insert(0, str(PILOT / "code"))
from simulate import BACKGROUNDS, BATCH, CASES, COMPONENTS, YEARS, first_loss, outcome_summary, paired_summary, sha

DATA = JOB / "source_data"
QA = JOB / "qa"
QA.mkdir(exist_ok=True)
AGE_BRANCHES = ("CENTRAL", "AGE_MEAN", "AGE_EARLY")
RUNS = {
    "CENTRAL": (("MODULE_ONLY", 0), ("JOINT_3", 3), ("JOINT_5", 5)),
    "AGE_MEAN": (("JOINT_3", 3),),
    "AGE_EARLY": (("JOINT_3", 3),),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def block_source(length):
    """Replay the saved first-round draws without resampling the operating side."""
    factors_path = PILOT / "source_data/historical_multipliers_before_recentering.csv"
    years_path = PILOT / f"source_data/sampled_ember_years_block{length}.csv.gz"
    factors = pd.read_csv(factors_path, index_col=0)
    sampled_years = pd.read_csv(years_path, index_col=0)
    assert sampled_years.columns.astype(int).tolist() == YEARS.tolist()
    assert sampled_years.index.tolist() == list(range(len(sampled_years)))
    assert sampled_years.iloc[:, 0].eq(0).all()
    factors_arr = factors.to_numpy()
    offsets = np.arange(length)
    starts = np.arange(len(factors_arr) - length + 1)
    mean = factors_arr[starts[:, None] + offsets].mean(axis=0)
    grid_idx = factors.index.get_indexer(sampled_years.iloc[:, 1:].to_numpy().ravel()).reshape(len(sampled_years), -1)
    assert (grid_idx >= 0).all()
    assert (np.diff(grid_idx.reshape(len(grid_idx), -1, length), axis=-1) == 1).all()
    return factors.columns.tolist(), factors_arr, grid_idx, mean[np.arange(len(YEARS) - 1) % length], years_path


def load_terms(record, codes):
    filename = JOB / "annual" / Path(record["filename"]).name
    assert sha(filename) == record["sha256"]
    with gzip.open(filename, "rt", encoding="utf-8") as source:
        ledger = json.load(source)
    assert ledger["codes"] == codes and ledger["years"] == YEARS.tolist()
    annual = {name: np.asarray(vals) for name, vals in ledger["annual"].items()}
    opening = np.asarray(ledger["opening"])
    fixed = sum(annual[k] for k in COMPONENTS)
    operating = annual["gridAux"] - annual["A"]
    module = np.asarray(ledger["newChinaModuleManufacturing"]) + np.asarray(ledger["replacementChinaModuleManufacturing"])
    assert np.isfinite(module).all() and (module >= 0).all() and (module <= fixed + 1e-12).all()
    central = opening[:, None] + np.cumsum(fixed + operating, axis=-1)
    center_world = central.sum(axis=0)
    central_events, _, _ = first_loss(central, opening)
    world_event, _, _ = first_loss(center_world, opening.sum())
    np.testing.assert_array_equal(central_events, [x or 0 for x in ledger["countryFirstLoss"]])
    assert int(world_event) == (ledger["worldFirstLoss"] or 0)
    assert abs(center_world[-1] - ledger["worldC2100"]) < 1e-9
    np.testing.assert_allclose(fixed + operating, annual["net"], rtol=0, atol=1e-10)
    return (opening, fixed, operating, module), (central_events, int(world_event), central[:, -1], center_world[-1])


def replay(terms, module_scale, grid_input):
    opening, fixed, operating, module = terms
    n, size = len(module_scale), len(opening) + 1
    events = np.empty((n, size), dtype=np.int16)
    benefit = np.empty((n, size), dtype=bool)
    recovery = np.empty_like(benefit)
    ends = np.empty((n, size))
    for start in range(0, n, BATCH):
        idx = slice(start, min(start + BATCH, n))
        if grid_input is None:
            operating_values = operating
        else:
            _, factors, grid_indices, position_mean, _ = grid_input
            multipliers = factors[grid_indices[idx]] / position_mean
            multipliers = np.concatenate((np.ones_like(multipliers[:, :1, :]), multipliers), axis=1)
            operating_values = operating * multipliers.swapaxes(1, 2)
        sampled = fixed + operating_values + (module_scale[idx, None, None] - 1) * module
        annual = opening[:, None] + np.cumsum(sampled, axis=-1)
        world = annual.sum(axis=1)
        events[idx, :-1], benefit[idx, :-1], recovery[idx, :-1] = first_loss(annual, opening)
        events[idx, -1], benefit[idx, -1], recovery[idx, -1] = first_loss(world, opening.sum())
        ends[idx, :-1], ends[idx, -1] = annual[..., -1], world[:, -1]
    return events, benefit, recovery, ends


def main(branch):
    manifest = read_json(JOB / "annual" / (branch + "_manifest.json"))
    spec = read_json(DATA / "module_distribution.json")
    operating_info = read_json(PILOT / "qa/provenance_and_checks.json")
    seed_n = operating_info["draws_per_seed_per_block"]
    ext = spec["external_source"]
    cv = ext["standard_deviation"] / ext["mean"]
    variance = np.log1p(cv * cv)
    module = np.concatenate([
        np.random.default_rng(seed).lognormal(mean=-variance / 2, sigma=np.sqrt(variance), size=seed_n)
        for seed in spec["transfer"]["random_seeds"]
    ])
    blocks = {length: block_source(length) for _, length in RUNS[branch] if length}
    codes = blocks[3][0]
    assert all(len(values[2]) == len(module) and values[0] == codes for values in blocks.values())
    countries = codes + ["WORLD"]
    n = len(module)
    records = {(r["background"], r["case"]): r for r in manifest["result"]}
    outcomes, paired, raw_world, curves, convergence = [], [], [], [], []
    if branch == "CENTRAL":
        pd.DataFrame({"draw_index": np.arange(n), "China_PV_module_factor_multiplier": module}).to_csv(
            DATA / "module_multiplier_draws.csv", index=False
        )
    for mode, block in RUNS[branch]:
        for background in BACKGROUNDS:
            base = None
            for case in CASES:
                terms, central = load_terms(records[background, case], codes)
                events, benefit, recovery, end = replay(terms, module, blocks.get(block))
                if base is None:
                    base = events, end, terms[0]
                else:
                    np.testing.assert_array_equal(base[2], terms[0])
                for i, country in enumerate(countries):
                    key = {"branch": branch, "mode": mode, "background": background, "case": case,
                           "country": country, "draws": n}
                    outcomes.append({
                        **key,
                        "center_first_loss_year": (central[1] if i == len(codes) else int(central[0][i])) or None,
                        "center_C2100_Gt": central[3] if i == len(codes) else central[2][i],
                        **outcome_summary(events[:, i], benefit[:, i], recovery[:, i], end[:, i]),
                    })
                    if case != CASES[0]:
                        paired.append({
                            **key,
                            **paired_summary(base[0][:, i], events[:, i], benefit[:, i], base[1][:, i], end[:, i]),
                        })
                world = events[:, -1]
                cdf = (world[:, None] > 0) & (world[:, None] <= YEARS)
                cdf1, cdf2 = [x.mean(axis=0) for x in np.split(cdf, 2)]
                for y, probability in zip(YEARS, cdf.mean(axis=0)):
                    curves.append({"branch": branch, "mode": mode, "background": background, "case": case,
                                   "year": y, "probability": probability})
                convergence.append({"branch": branch, "mode": mode, "background": background, "case": case,
                                    "max_cdf_gap_between_seeds": np.max(np.abs(cdf1 - cdf2)),
                                    "loss_by_2100_gap_between_seeds": abs(cdf1[-1] - cdf2[-1])})
                raw_world.append(pd.DataFrame({
                    "branch": branch, "mode": mode, "background": background, "case": case,
                    "draw_index": np.arange(n), "C2100_Gt": end[:, -1],
                    "first_loss_year": pd.array(np.where(world > 0, world, np.nan), dtype="Int64"),
                    "benefit_formed_or_inherited": benefit[:, -1], "recovered_after_loss": recovery[:, -1],
                }))
                print(branch, mode, background, case, f"{cdf[:, -1].mean():.4f}", flush=True)
    for name, rows in (("outcomes", outcomes), ("pairs", paired), ("world_incidence", curves), ("convergence", convergence)):
        pd.DataFrame(rows).to_csv(DATA / f"{name}_{branch}.csv", index=False)
    pd.concat(raw_world, ignore_index=True).to_csv(
        DATA / f"world_draws_{branch}.csv.gz", index=False, compression={"method": "gzip", "mtime": 0}
    )
    meta = {
        "branch": branch, "runs": RUNS[branch], "n_per_mode_path": n, "n_per_seed": seed_n,
        "cv": cv, "lognormal_log_mean": -variance / 2, "lognormal_log_sd": float(np.sqrt(variance)),
        "module_multiplier_p05_p50_p95": np.quantile(module, [.05, .5, .95]).tolist(),
        "physical_account_manifest_sha256": sha(JOB / "annual" / (branch + "_manifest.json")),
        "distribution_source_spec_sha256": sha(DATA / "module_distribution.json"),
        "operating_grid_draw_sources": {b: sha(blocks[b][-1]) for b in blocks},
        "grid_residuals_sha256": sha(PILOT / "source_data/historical_multipliers_before_recentering.csv"),
        "maximum_central_replay_error_Gt": max(r["maxCentralError"] for r in records.values()) if branch == "CENTRAL" else None,
    }
    (QA / f"provenance_{branch}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("branch", choices=AGE_BRANCHES)
    main(parser.parse_args().branch)
