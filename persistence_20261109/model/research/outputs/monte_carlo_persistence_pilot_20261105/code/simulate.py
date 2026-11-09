"""Paired annual grid-factor replay of the current SSP2 accounts."""

import gzip
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


JOB = Path(__file__).resolve().parents[1]
RESEARCH = JOB.parents[1]
BASE = RESEARCH / "outputs/figures3_5_unified_time_metric_20261102"
HISTORY = RESEARCH / "outputs/baseline_replacement_package_20261031"
COHORTS = RESEARCH / "outputs/opening_balance_reference_cohorts_20261102"


DATA = JOB / "source_data"
QA = JOB / "qa"
DATA.mkdir(exist_ok=True)
QA.mkdir(exist_ok=True)

YEARS = np.arange(2025, 2101)
HIST_YEARS = np.arange(2000, 2024)
EVALUATION_YEARS = (2050, 2060, 2075, 2100)
BACKGROUNDS = ("CP", "NDC", "B2C", "NZ2050", "LD")
CASES = (
    "REF__UNLIMITED",
    "FIG4_M_BEST__UNLIMITED",
    "FIG4_L_BEST__UNLIMITED",
    "FIG4_E_BEST__UNLIMITED",
    "STORAGE_FC0__CAP50",
)
LABELS = dict(zip(CASES, ("参考", "M30制造改善", "延寿", "运行改善", "新增不配储＋外送能力50%")))
COMPONENTS = ("newManufacturing", "replacementManufacturing", "treatment")
BATCH = 64
PILOT_DRAWS = 512
FORMAL_DRAWS_PER_SEED = 4096
SEEDS = (6110501, 6110502)
BLOCK_LENGTHS = (3, 5)
PERCENTILES = (5, 50, 95)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


def first_loss(curves, opening):
    """Keep neutral years in the timeline and ignore them for sign changes."""
    negative = curves < 0
    earlier_benefit = np.concatenate(
        (np.broadcast_to(opening < 0, negative.shape[:-1])[..., None], negative[..., :-1]), axis=-1
    )
    observed = (curves > 0) & np.logical_or.accumulate(earlier_benefit, axis=-1)
    has_event = observed.any(axis=-1)
    benefit = negative.any(axis=-1) | (opening < 0)
    event_year = np.where(has_event, YEARS[observed.argmax(axis=-1)], 0)
    recovery = (negative & (YEARS > event_year[..., None])).any(axis=-1) & has_event
    return event_year.astype(np.int16), benefit, recovery


def prepare_history(codes):
    manifest = load_json(HISTORY / "sources/download_manifest.json")
    raw_meta = next(row for row in manifest if row["id"] == "Ember_yearly_global.csv")
    raw = HISTORY / "sources/Ember_yearly_global.csv"
    hist = HISTORY / "source_data/historical_grid_raw.csv"
    assert sha(raw) == raw_meta["sha256"]
    field = "Emissions intensity (gCO2e/kWh)"
    original = pd.read_csv(raw, usecols=["ISO 3 code", "Year", "Electricity source", field], low_memory=False)
    entries = pd.read_csv(hist).query("year in @HIST_YEARS and code in @codes and source_id == 'EMBER_20261031'").copy()
    original_rows = original.iloc[entries.csv_row_one_based.to_numpy() - 2]
    assert np.array_equal(original_rows["ISO 3 code"], entries.code)
    assert np.array_equal(original_rows.Year, entries.year)
    assert original_rows["Electricity source"].str.casefold().eq("total generation").all()
    assert np.allclose(original_rows[field] / 1000, entries.kgCO2e_kWh, rtol=0, atol=1e-13)
    pivot = entries.pivot(index="year", columns="code", values="kgCO2e_kWh").reindex(index=HIST_YEARS, columns=codes)
    eligible = (pivot.notna() & (pivot > 0)).all().to_numpy()
    entries["included_in_distribution"] = entries.code.isin(np.asarray(codes)[eligible])
    entries.to_csv(DATA / "ember_values_used.csv", index=False, encoding="utf-8-sig")
    levels = pivot.loc[:, eligible].to_numpy()
    trends = np.lib.stride_tricks.sliding_window_view(levels, 5, axis=0).mean(axis=-1)
    factor = np.ones((len(trends), len(codes)))
    factor[:, eligible] = levels[2:-2] / trends
    residual_years = HIST_YEARS[2:-2]
    pd.DataFrame(factor, columns=codes, index=residual_years).rename_axis("historical_year").to_csv(
        DATA / "historical_multipliers_before_recentering.csv"
    )
    coverage = pd.DataFrame({
        "country": codes,
        "valid_source_years": (pivot.notna() & (pivot > 0)).sum().to_numpy(),
        "sampled": eligible,
    })
    coverage.to_csv(DATA / "country_sampling_coverage.csv", index=False)
    return factor, residual_years, eligible, raw_meta, sha(hist)


def block_draws(factor, residual_years, length):
    """Resample synchronized contiguous country vectors and preserve the mean by block position."""
    assert (len(YEARS) - 1) % length == 0
    n_starts = len(factor) - length + 1
    offsets = np.arange(length)
    candidates = factor[np.arange(n_starts)[:, None] + offsets]
    position_mean = candidates.mean(axis=0)
    normalized = candidates / position_mean
    assert np.allclose(normalized.mean(axis=0), 1, rtol=0, atol=1e-13)
    draws = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        starts = rng.integers(n_starts, size=(FORMAL_DRAWS_PER_SEED, (len(YEARS) - 1) // length))
        draws.append((starts[..., None] + offsets).reshape(FORMAL_DRAWS_PER_SEED, -1))
    draws = np.concatenate(draws)
    source_years = np.column_stack((np.zeros(len(draws), dtype=int), residual_years[draws]))
    pd.DataFrame(source_years, columns=YEARS).rename_axis("draw_index").to_csv(
        DATA / f"sampled_ember_years_block{length}.csv.gz", compression={"method": "gzip", "mtime": 0}
    )
    future_positions = np.arange(len(YEARS) - 1) % length
    return draws, position_mean[future_positions]


def load_account(background, case, manifest, codes=None):
    record = manifest[background, case]
    path = BASE / "accounts" / (background + "__" + case + ".json.gz")
    assert sha(path) == record["sha256"]
    with gzip.open(path, "rt", encoding="utf-8") as source:
        account = json.load(source)
    assert (account["roof"], account["climate"], account["iam"]) == ("SSP2", "SSP245", "REMIND")
    assert account["years"] == YEARS.tolist()
    assert codes is None or account["_codes"] == codes
    return account


def prepare_account(account):
    annual = {key: np.asarray(value) for key, value in account["annualCountry"].items()}
    opening = np.asarray(account["openingBalances"])
    fixed = sum(annual[key] for key in COMPONENTS)
    operating = annual["gridAux"] - annual["A"]
    net = fixed + operating
    central = opening[:, None] + np.cumsum(net, axis=-1)
    central_global = central.sum(axis=0)
    closure = float(max(
        np.max(np.abs(central - np.asarray(account["countries"]["C"]))),
        np.max(np.abs(central_global - np.asarray(account["global"]["C"]))),
        np.max(np.abs(net - annual["net"])),
    ))
    assert closure < 1e-9
    year, _, _ = first_loss(central, opening)
    global_year, _, _ = first_loss(central_global, opening.sum())
    classifications = account["classifications"]
    assert [row["code"] for row in classifications] == account["_codes"]
    assert year.tolist() == [row["first_loss_year"] or 0 for row in classifications]
    assert int(global_year) == (account["events"]["global"]["first_loss_year"] or 0)
    return (opening, fixed, operating), (year, int(global_year), central[:, -1], central_global[-1]), closure


def simulate(terms, factor, draws, position_mean):
    opening, fixed, operating = terms
    n = len(draws)
    size = len(opening) + 1
    end = np.empty((n, size))
    events = np.empty((n, size), dtype=np.int16)
    benefit = np.empty((n, size), dtype=bool)
    recovery = np.empty_like(benefit)
    for start in range(0, n, BATCH):
        ix = slice(start, min(start + BATCH, n))
        multipliers = factor[draws[ix]] / position_mean
        multipliers = np.concatenate((np.ones_like(multipliers[:, :1, :]), multipliers), axis=1)
        years_net = fixed + operating * multipliers.swapaxes(1, 2)
        curves = opening[:, None] + np.cumsum(years_net, axis=-1)
        global_curves = curves.sum(axis=1)
        events[ix, :-1], benefit[ix, :-1], recovery[ix, :-1] = first_loss(curves, opening)
        events[ix, -1], benefit[ix, -1], recovery[ix, -1] = first_loss(global_curves, opening.sum())
        end[ix, :-1] = curves[..., -1]
        end[ix, -1] = global_curves[:, -1]
    assert np.all(benefit | (events == 0))
    return events, benefit, recovery, end


def quantiles(values, method="linear"):
    if not len(values):
        return [None] * len(PERCENTILES)
    return np.percentile(values, PERCENTILES, method=method).tolist()


def outcome_summary(events, benefit, recovery, end):
    happened = events > 0
    return {
        **{f"p_loss_by_{t}": np.mean(happened & (events <= t)) for t in EVALUATION_YEARS},
        "p_benefit_no_loss": np.mean(benefit & ~happened),
        "p_no_benefit": np.mean(~benefit),
        "p_loss_then_recovery": np.mean(recovery),
        "event_draws": int(happened.sum()),
        **dict(zip(("loss_year_p05", "loss_year_p50", "loss_year_p95"), quantiles(events[happened], "inverted_cdf"))),
        **dict(zip(("C2100_Gt_p05", "C2100_Gt_p50", "C2100_Gt_p95"), quantiles(end))),
    }


def paired_summary(base_event, case_event, case_benefit, base_end, case_end):
    both = (base_event > 0) & (case_event > 0)
    delta = case_event[both] - base_event[both]
    earlier = both & (case_event < base_event)
    later = both & (case_event > base_event)
    avoided = (base_event > 0) & (case_event == 0) & case_benefit
    lost_formation = (base_event > 0) & ~case_benefit
    newly_lost = (base_event == 0) & (case_event > 0)
    carbon_gain = base_end - case_end
    # A one-ton guard keeps floating point noise from counting as a paired carbon gain.
    carbon_better = carbon_gain > 1e-9
    return {
        "both_event_draws": int(both.sum()),
        "p_earlier": np.mean(earlier),
        "p_later": np.mean(later),
        "p_same_year": np.mean(both & (case_event == base_event)),
        "p_avoided_loss": np.mean(avoided),
        "p_lost_formation": np.mean(lost_formation),
        "p_new_loss": np.mean(newly_lost),
        "p_neither_has_loss": np.mean((base_event == 0) & (case_event == 0)),
        "p_carbon_improves": np.mean(carbon_better),
        "p_carbon_improves_and_persistence_improves": np.mean(carbon_better & (later | avoided)),
        "p_carbon_improves_but_loss_earlier": np.mean(carbon_better & earlier),
        **dict(zip(("delay_year_p05", "delay_year_p50", "delay_year_p95"), quantiles(delta, "inverted_cdf"))),
        **dict(zip(("gain_Gt_p05", "gain_Gt_p50", "gain_Gt_p95"), quantiles(carbon_gain))),
    }


def main():
    manifest_path = BASE / "source_data/account_manifest.json"
    manifest = {(x["background"], x["configuration_id"]): x for x in load_json(manifest_path)}
    first_account = load_account(BACKGROUNDS[0], CASES[0], manifest)
    codes = first_account["_codes"]
    countries = codes + ["WORLD"]
    cohorts_path = COHORTS / "source_data/fixed_reference_cohorts.json"
    cohort = load_json(cohorts_path)["groups"]
    factor, residual_years, sampled, raw_meta, historic_sha = prepare_history(codes)
    primary = []
    paired = []
    curves = []
    convergence = []
    all_global_draws = []
    account_hashes = {}
    sampled_operating_share = {}
    max_closure = 0.0
    for length in BLOCK_LENGTHS:
        draws, position_mean = block_draws(factor, residual_years, length)
        for background in BACKGROUNDS:
            scope = cohort[background]
            roles = {c: role for role in ("formed_then_lost", "opening_benefit_then_lost") for c in scope[role]}
            base_opening = None
            for case in CASES:
                account = load_account(background, case, manifest, codes)
                account_hashes[f"{background}__{case}"] = manifest[background, case]["sha256"]
                terms, central, closure = prepare_account(account)
                max_closure = max(closure, max_closure)
                events, benefit, recovery, end = simulate(terms, factor, draws, position_mean)
                if base_opening is None:
                    base_opening = terms[0]
                    base = events, benefit, end
                    abs_operating = np.abs(terms[2])
                    sampled_operating_share[background] = float(abs_operating[sampled].sum() / abs_operating.sum())
                else:
                    assert np.array_equal(base_opening, terms[0])
                for i, country in enumerate(countries):
                    key = {
                        "block": length, "background": background, "case": case, "country": country,
                        "country_group": "world" if country == "WORLD" else roles.get(country, "outside_fixed_loss_cohorts"),
                        "draws": len(events),
                    }
                    primary.append({
                        **key,
                        "central_first_loss_year": (central[1] if i == len(codes) else int(central[0][i])) or None,
                        "central_C2100_Gt": central[3] if i == len(codes) else central[2][i],
                        **outcome_summary(events[:, i], benefit[:, i], recovery[:, i], end[:, i]),
                    })
                    if case != CASES[0]:
                        paired.append({
                            **key,
                            **paired_summary(base[0][:, i], events[:, i], benefit[:, i], base[2][:, i], end[:, i]),
                        })
                world = events[:, -1]
                cdf = (world[:, None] > 0) & (world[:, None] <= YEARS)
                for t, p in zip(YEARS, cdf.mean(axis=0)):
                    curves.append({"block": length, "background": background, "case": case, "year": t, "probability": p})
                first, second = np.split(cdf, 2)
                loss_p = cdf[:, -1].mean()
                event_year_medians = [
                    quantiles(w[w > 0], "inverted_cdf")[1] for w in np.split(world, 2)
                ]
                check = {
                    "block": length, "background": background, "case": case, "draws": len(draws),
                    "max_cdf_difference_between_seeds": np.max(np.abs(first.mean(axis=0) - second.mean(axis=0))),
                    "max_cdf_difference_pilot_to_full": np.max(np.abs(cdf[:PILOT_DRAWS].mean(axis=0) - cdf.mean(axis=0))),
                    "seed_1_loss_year_p50": event_year_medians[0],
                    "seed_2_loss_year_p50": event_year_medians[1],
                    "loss_by_2100_mcse": np.sqrt(loss_p * (1 - loss_p) / len(draws)),
                }
                if case != CASES[0]:
                    slices = (slice(None, FORMAL_DRAWS_PER_SEED), slice(FORMAL_DRAWS_PER_SEED, None))
                    joint = [
                        paired_summary(base[0][sl, -1], world[sl], benefit[sl, -1], base[2][sl, -1], end[sl, -1])
                        ["p_carbon_improves_and_persistence_improves"]
                        for sl in slices
                    ]
                    check["joint_improvement_difference_between_seeds"] = abs(joint[0] - joint[1])
                convergence.append(check)
                all_global_draws.append(pd.DataFrame({
                    "block": length, "background": background, "case": case, "draw_index": np.arange(len(draws)),
                    "first_loss_year": pd.array(np.where(world > 0, world, np.nan), dtype="Int64"),
                    "benefit_formed_or_inherited": benefit[:, -1],
                    "recovered_after_loss": recovery[:, -1],
                    "C2100_Gt": end[:, -1],
                }))
                print(length, background, case, f"P2100={loss_p:.4f}", flush=True)

    for name, records in (
        ("outcome_summary", primary), ("paired_summary", paired),
        ("global_cumulative_incidence", curves), ("convergence", convergence),
    ):
        pd.DataFrame(records).to_csv(DATA / f"{name}.csv", index=False)
    pd.concat(all_global_draws, ignore_index=True).to_csv(
        DATA / "global_draw_outcomes.csv.gz", index=False, compression={"method": "gzip", "mtime": 0}
    )
    save_json(QA / "provenance_and_checks.json", {
        "coverage": {
            "modeled": len(codes), "sampled": int(sampled.sum()), "fixed_due_to_coverage": list(np.asarray(codes)[~sampled]),
            "sampled_share_of_reference_absolute_use_grid_net_emissions": sampled_operating_share,
        },
        "ember": raw_meta,
        "historical_extract_sha256": historic_sha,
        "calibration_years": HIST_YEARS.tolist(),
        "detrended_residual_years": residual_years.tolist(),
        "block_lengths": list(BLOCK_LENGTHS),
        "seed_values": list(SEEDS),
        "draws_per_seed_per_block": FORMAL_DRAWS_PER_SEED,
        "initial_pilot_draws": PILOT_DRAWS,
        "paired_gain_zero_tolerance_Gt": 1e-9,
        "maximum_central_replay_and_annual_closure_error_Gt": max_closure,
        "all_central_country_and_world_event_years_match": True,
        "account_manifest_sha256": sha(manifest_path),
        "fixed_cohort_manifest_sha256": sha(cohorts_path),
        "input_account_hashes": account_hashes,
        "software": {"numpy": np.__version__, "pandas": pd.__version__},
    })


if __name__ == "__main__":
    main()
