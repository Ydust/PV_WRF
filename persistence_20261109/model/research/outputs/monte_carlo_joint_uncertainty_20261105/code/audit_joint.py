"""Verify exported simulation probabilities and make aligned round comparisons."""

import json
import numpy as np
import pandas as pd
from simulate_joint import (
    AGE_BRANCHES, BACKGROUNDS, CASES, DATA, JOB, PILOT, QA, RUNS, YEARS,
    block_source, load_terms, replay, read_json, sha,
)


def main():
    first = PILOT / "source_data"
    first_world = pd.read_csv(first / "global_draw_outcomes.csv.gz")
    old = pd.read_csv(first / "outcome_summary.csv")
    old_pairs = pd.read_csv(first / "paired_summary.csv")
    old_groups = old.loc[old.block.eq(3) & old.case.eq(CASES[0]), ["background", "country", "country_group"]]
    for table in (old, old_pairs):
        table["branch"] = "CENTRAL"
        table["mode"] = "GRID_ONLY_" + table.block.astype(str)
    old = old.rename(columns={"central_first_loss_year": "center_first_loss_year", "central_C2100_Gt": "center_C2100_Gt"})
    base_modes, pair_modes, global_frames = [old], [old_pairs], []
    thresholds = []
    distribution_check = []
    audit = {"branches": {}, "grid_replay_benchmarks": []}
    for branch in AGE_BRANCHES:
        path = JOB / "annual" / f"{branch}_manifest.json"
        manifest = read_json(path)
        meta = read_json(QA / f"provenance_{branch}.json")
        assert meta["physical_account_manifest_sha256"] == sha(path)
        outcomes = pd.read_csv(DATA / f"outcomes_{branch}.csv")
        pairs = pd.read_csv(DATA / f"pairs_{branch}.csv")
        raw = pd.read_csv(DATA / f"world_draws_{branch}.csv.gz")
        traces = pd.read_csv(DATA / f"world_incidence_{branch}.csv").set_index(["mode", "background", "case", "year"]).sort_index()
        n = meta["n_per_mode_path"]
        expected = len(RUNS[branch]) * len(BACKGROUNDS) * len(CASES)
        assert len(manifest["result"]) == len(BACKGROUNDS) * len(CASES)
        assert len(raw) == expected * n and len(outcomes) == expected * 232
        assert len(pairs) == len(RUNS[branch]) * len(BACKGROUNDS) * (len(CASES) - 1) * 232
        assert not outcomes.duplicated(["mode", "background", "case", "country"]).any()
        assert not pairs.duplicated(["mode", "background", "case", "country"]).any()
        assert outcomes.draws.eq(n).all() and pairs.draws.eq(n).all()
        codes = old_groups.loc[old_groups.background.eq(BACKGROUNDS[0]) & old_groups.country.ne("WORLD"), "country"].tolist()
        for record in manifest["result"]:
            terms, _ = load_terms(record, codes)
            opening, fixed, operating, affected = terms
            initial = opening.sum()
            center = initial + np.cumsum((fixed + operating).sum(axis=0))
            cumul_affected = np.cumsum(affected.sum(axis=0))
            assert initial < 0 and (cumul_affected > 0).all()
            required = 1 - center / cumul_affected
            year_index = required.argmin()
            thresholds.append({
                "branch": branch, "background": record["background"], "case": record["case"],
                "threshold_multiplier_for_any_first_loss": required[year_index],
                "year_defining_threshold": int(YEARS[year_index]),
                "center_opening_balance_Gt": initial,
                "center_C2100_Gt": center[-1],
                "affected_module_manufacturing_2025_2100_Gt": cumul_affected[-1],
            })
        np.testing.assert_allclose(
            outcomes[["p_loss_by_2100", "p_benefit_no_loss", "p_no_benefit"]].sum(axis=1), 1, rtol=0, atol=1e-12
        )
        np.testing.assert_allclose(pairs[[
            "p_earlier", "p_later", "p_same_year", "p_avoided_loss", "p_lost_formation",
            "p_new_loss", "p_neither_has_loss",
        ]].sum(axis=1), 1, rtol=0, atol=1e-12)
        world = outcomes.loc[outcomes.country.eq("WORLD")].set_index(["mode", "background", "case"])
        wpairs = pairs.loc[pairs.country.eq("WORLD")].set_index(["mode", "background", "case"])
        reference = raw.loc[raw.case.eq(CASES[0])].set_index(["mode", "background", "draw_index"]).sort_index()
        for key, sample in raw.groupby(["mode", "background", "case"]):
            mode, bg, case = key
            sample = sample.sort_values("draw_index")
            assert sample.draw_index.tolist() == list(range(n))
            years = sample.first_loss_year.to_numpy()
            observed = np.isfinite(years)
            benefit = sample.benefit_formed_or_inherited.to_numpy()
            assert (benefit | ~observed).all()
            cdf = np.mean(years[:, None] <= YEARS, axis=0)
            np.testing.assert_allclose(traces.loc[key].probability, cdf, rtol=0, atol=1e-12)
            assert world.loc[key, "event_draws"] == observed.sum()
            if case == CASES[0]:
                continue
            ref = reference.loc[(mode, bg)].loc[sample.draw_index]
            ref_years = ref.first_loss_year.to_numpy()
            gain = ref.C2100_Gt.to_numpy() - sample.C2100_Gt.to_numpy() > 1e-9
            delayed = years > ref_years
            avoided = np.isfinite(ref_years) & ~observed & benefit
            earlier = years < ref_years
            for statistic, expected_value in (
                ("p_carbon_improves_and_persistence_improves", np.mean(gain & (delayed | avoided))),
                ("p_carbon_improves_but_loss_earlier", np.mean(gain & earlier)),
            ):
                assert abs(wpairs.loc[key, statistic] - expected_value) < 1e-12
        base_modes.append(outcomes)
        pair_modes.append(pairs)
        global_frames.append(raw.loc[raw["mode"].eq("JOINT_3")])
        audit["branches"][branch] = {"outcome_rows": len(outcomes), "pair_rows": len(pairs),
                                     "world_draw_rows": len(raw), "annual_world_probabilities": len(traces)}
        if branch == "CENTRAL":
            anchor = {(x["background"], x["case"]): x for x in manifest["result"]}
            block = block_source(3)
            for bg, case in (("B2C", CASES[0]), ("NZ2050", CASES[-1]), ("LD", CASES[0])):
                terms, _ = load_terms(anchor[bg, case], block[0])
                events, _, _, c2100 = replay(terms, np.ones(n), block)
                benchmark = first_world.loc[
                    first_world.block.eq(3) & first_world.background.eq(bg) & first_world.case.eq(case)
                ].sort_values("draw_index")
                np.testing.assert_array_equal(events[:, -1], benchmark.first_loss_year.fillna(0).to_numpy())
                error = float(np.max(np.abs(c2100[:, -1] - benchmark.C2100_Gt.to_numpy())))
                assert error < 1e-9
                audit["grid_replay_benchmarks"].append({"path": bg, "case": case, "max_C2100_difference_Gt": error})
            lognormal = pd.read_csv(DATA / "module_multiplier_draws.csv").China_PV_module_factor_multiplier.to_numpy()
            z = (np.log(lognormal) - meta["lognormal_log_mean"]) / meta["lognormal_log_sd"]
            normal = 1 + meta["cv"] * z
            assert (normal > 0).all()
            for bg, case in (("B2C", CASES[1]), ("NDC", CASES[-1])):
                terms, _ = load_terms(anchor[bg, case], block[0])
                normal_years, _, _, _ = replay(terms, normal, block)
                distribution_check.append({
                    "path": bg, "case": case, "draws": n,
                    "lognormal_event_by_2100": world.loc[("JOINT_3", bg, case), "p_loss_by_2100"],
                    "normal_event_by_2100": np.mean(normal_years[:, -1] > 0),
                })

    outcomes = pd.concat(base_modes, ignore_index=True)
    pairs = pd.concat(pair_modes, ignore_index=True)
    if "country_group" in outcomes:
        outcomes = outcomes.drop(columns="country_group")
    if "country_group" in pairs:
        pairs = pairs.drop(columns="country_group")
    for filename, table in (("all_outcomes_comparison", outcomes), ("all_pairs_comparison", pairs)):
        table = table.merge(old_groups, on=["background", "country"], how="left", validate="many_to_one")
        assert table.country_group.notna().all()
        table.drop(columns="block", errors="ignore").to_csv(DATA / f"{filename}.csv", index=False)
    outcomes.loc[outcomes.country.eq("WORLD")].drop(columns="block", errors="ignore").to_csv(
        DATA / "world_outcome_comparison.csv", index=False
    )
    pairs.loc[pairs.country.eq("WORLD")].drop(columns="block", errors="ignore").to_csv(
        DATA / "world_pair_comparison.csv", index=False
    )
    ages = pd.concat(global_frames, ignore_index=True)
    presence = ages.pivot(index=["background", "case", "draw_index"], columns="branch", values="first_loss_year")
    status = presence.notna()
    age_cmp = pd.DataFrame({
        "mean_age_event_status_changes": status.AGE_MEAN.ne(status.CENTRAL),
        "early_age_event_status_changes": status.AGE_EARLY.ne(status.CENTRAL),
    }).groupby(level=[0, 1]).sum()
    age_cmp.to_csv(DATA / "age_world_event_disagreements.csv")
    pd.DataFrame(thresholds).to_csv(DATA / "world_module_thresholds_at_fixed_grid.csv", index=False)
    pd.DataFrame(distribution_check).to_csv(DATA / "distribution_shape_sensitivity.csv", index=False)
    (QA / "audit_results.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
