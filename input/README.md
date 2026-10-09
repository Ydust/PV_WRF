Processed inputs correspond to the accompanying manuscript. Inventory outputs and scenario configurations are derived from R&D GREET 2025 Rev.1 and EIA IEO2023. Native third-party workbooks are obtained separately from their providers. Grid inputs retain the available source fields; missing original product-version, projection and population metadata are documented in Supplementary Information.

## Current main-figure processed data

The main notebook uses the existing output/Source_Data/CSV filenames for the current October submission. Original input folders and the September numerical kernel are retained. All tables below are model outputs or processed figure inputs, not new measurements. Published source values and inherited model boundaries are unchanged. Joining fields to existing CSVs preserves numeric values and does not introduce new model assumptions.

- Figure 1: 11,047 grid balances; seven negative cumulative national balances; storage manufacture divided by gross mitigation; 10,767 eligible non-negative cells and six unweighted climate medians. Negative cells are categorical; non-positive gross denominators are not filled with zero.
- Figure 2: 2040 one-percentage-point additions followed through 2049, normalised by added generation. Base PV/storage terms are separate from the explicitly conditional original-roof reference-building correction. Added columns retain both storage configurations, the 17-configuration thermal range, and the hourly extra-use/savings split. These are not national measured energy effects.
- Figure 3: annual production-event balances and event decomposition. Existing CSV columns add deterministic manufacturing envelopes via a one-to-one country/scenario/year join. Service allocation remains a separately named structural sensitivity.
- Figure 4: all nine intervention rows; seven countries each retain 192 conditional scenarios. The 13-region intervention pool differs from the seven cumulative-negative display countries.
- Figure 5: 2,048 paired draws per strategy; 37 retained regions; matched cumulative electricity delivery. Equivalent selection-rule comparisons remain in the complete CSV but are excluded from the three-rule main panel. All 10,240 strategy-draw values are used in panel d.

The main source-data workbook is an exact copy of the current submission workbook (18 worksheets). The supplementary workbook and supplementary notebook remain the September snapshot within this narrowly scoped update.

### Exact data-copy and join records

```json
[
  {
    "target": "output/Source_Data/CSV/Figure_1a.csv",
    "source": "source_data/grid.csv",
    "sha256": "8c48ef7927fce2b9c169f47dfde08a23a770e698ac1cb69124fc4b6961d6a128",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_1b.csv",
    "source": "source_data/Figure1b.csv",
    "sha256": "a7ba559efbebb5b519fb1e628e709ed0ee2dab61c024ce20ff686d3d076e3d94",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_1c.csv",
    "source": "source_data/Figure1c.csv",
    "sha256": "3859c4f0a6d203ae227baea0ba5c69fd0e3869906c1fbcb037dd9c15cfb409cb",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_1d.csv",
    "source": "source_data/Figure1d.csv",
    "sha256": "b479aa4d0290bd1333d95a73fac02c7bccc9e0003cfad63f0f080c2c9bd28964",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_3b.csv",
    "source": "source_data/event_decomposition.csv",
    "sha256": "8b6f52a0fa55c4b3da24ad44d4796457352346dff061e3d9fa54acfae3dce820",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_4a.csv",
    "source": "source_data/interventions.csv",
    "sha256": "26014c776e9658892eb147dc066c2b025b33c033e609bcd6205c29397d1904f7",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_4b_values.csv",
    "source": "source_data/conditional_sensitivity.csv",
    "sha256": "93b4eda5bb5a5674073340c5dfa50830714ec487172e8c255a136754f4d936c8",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5a_summary.csv",
    "source": "source_data/Figure_5a_summary.csv",
    "sha256": "e0ffa9e52915f5b41067a55bfd0a188f6a69e20a7794981f79351ec6a6b659e4",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5a_values.csv",
    "source": "source_data/Figure_5a_values.csv",
    "sha256": "2ad2b973158cb66479e18b63161e9d9df266ac9856bfb2cf1a2e53f196d49601",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5b.csv",
    "source": "source_data/Figure_5b.csv",
    "sha256": "2452cd39fef4ce07722c010a09aec1ad04d210af19bf8ac2679efae7e6a4a26c",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5b_summary.csv",
    "source": "source_data/Figure_5b_summary.csv",
    "sha256": "b181b40f2647c65a327a73224c16a24f16172309ed7ba57673f27b16ddd511e6",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5c_summary.csv",
    "source": "source_data/Figure_5c_summary.csv",
    "sha256": "77c29cf0436ea96c0815186550f6f1ebaf2f6bd528f38fe7c41213f78b531af8",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5c_values.csv",
    "source": "source_data/Figure_5c_values.csv",
    "sha256": "d7674fe60052e4da759dd3f3c3f43b7e696a648853f80f772e6c3ed24ccc169a",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5d.csv",
    "source": "source_data/Figure_5d.csv",
    "sha256": "c0f2cf94bec25b2e0b53d461a2eb8ee7dd3d70e0f4dda7ded1db66eb84b23ebf",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_5d_values.csv",
    "source": "source_data/Figure_5d_values.csv",
    "sha256": "27bd0849479d654d2b123fcb4343b63b3bb330148d5c285c01f7a34d09abc1c0",
    "conversion": "None; exact canonical CSV bytes"
  },
  {
    "target": "output/Source_Data/CSV/Figure_2.csv",
    "sha256": "e006415b0267af546730f0188f514489ab1ecb4662760a91ad763483e09bd181",
    "sources": [
      {
        "source": "source_data/Figure2.csv",
        "sha256": "35431de3ad2dd5f6338012dc175a88151b812705399405706854e8049ee30b9f"
      },
      {
        "source": "source_data/thermal_reference_20261008/reference_case.csv",
        "sha256": "0b7e8d37babb2ddf860b5c88cd69e1001d3557479cd88ce380a3a9c9704667ef"
      },
      {
        "source": "source_data/national_thermal_20261008/country_scenario_ranges.csv",
        "sha256": "cdd7df3ac5eafe801a3edff448222376a9dc3676b234b492c667c9447643d9fe"
      },
      {
        "source": "source_data/hourly_energy_split_20261008/country_split.csv",
        "sha256": "4ec26d5a4da104d3f40319169e9b44e40fe8543832bc498b1f28e269fdd63af0"
      }
    ],
    "conversion": "Join by country and explicit storage configuration; all base columns preserved. Additional columns contain declared thermal reference and range."
  },
  {
    "target": "output/Source_Data/CSV/Figure_3a.csv",
    "sha256": "df3e7b86326c772628b89b562d1f0729d5480b84c871c0726bd111f11bf3672c",
    "sources": [
      {
        "source": "source_data/annual_scenarios.csv",
        "sha256": "f69b1a44c6556b5047ddd8919c1b42df53599d0a9053bcb949c6c3fad0d2030b"
      },
      {
        "source": "source_data/figure3_envelopes.csv",
        "sha256": "3de53fbaa90f58a6e0e6fc7f812f19b1f21870f3c9dedd0aeb046a847b8fac64"
      }
    ],
    "conversion": "One-to-one left join by country, scenario and year; no changes to annual values."
  },
  {
    "target": "output/Source_Data/Main_Figure_Source_Data.xlsx",
    "sha256": "22f4f921ce8997f1cf33564d337a2ad6cfa4d1660c5893f1446b8aacd63380b2",
    "conversion": "Exact copy of current submission workbook: 18 worksheets, frozen model values."
  }
]
```
