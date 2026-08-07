# EU5 debug-save population parser

This tool extracts only the data needed to study SOL's location-class
compensation model. It supports **uncompressed text saves produced with debug
mode enabled**; normal compressed/binary saves are rejected.

It does not deserialize the full save. The file is memory-mapped, top-level
sections are located by byte offset, and only these relationships are parsed:

- metadata location order → location id and script name;
- country id → tag and decoded SOL country-solver caches;
- population id → type, size, culture/religion and selected economic fields;
- location id → owner, market, rank, population ids, and `sol_location_*`
  cached variables.

From the project root, using the project's `eu5` Python environment:

```powershell
$env:PYTHONUTF8='1'
& C:\path\to\envs\eu5\python.exe -m tools.eu5_save_parser data\saves\save.eu5
```

Useful options:

```text
--country HUN          export only locations currently owned by HUN
--emit-populations     also export one row per population group
-o <directory>        choose the output directory
--no-strict            keep exporting when id validation reports damage
```

The default output is `data/save_analysis/<save filename>/`:

- `locations.csv`: location population vectors, within-location population
  shares, owner/market metadata, and decoded SOL classification caches;
- `countries.csv`: actual country population vectors and shares, aggregated
  from owned locations, plus country target-capacity, coefficient, solve-status,
  pressure, matrix/residual, savings and other persisted SOL/GLS variables;
- `metadata.json`: save version/date, units, selected filters, and referential
  integrity diagnostics;
- `populations.csv`: optional raw population-group table.

`population_commoners` is laborers + peasants + soldiers;
`population_lower` additionally includes tribesmen. These mirror SOL's active
four-class grouping. Population sizes remain in the save's raw units (the game
normally displays them as thousands); the parser deliberately applies no
guessed multiplier.

## Demand solution analysis

After exporting a save, replay the current 1% anchor / 96% negative-pool
classification and compare raw, exact, and total-preserving nonnegative
approximate results:

```powershell
$env:PYTHONUTF8='1'
& C:\path\to\envs\eu5\python.exe -m tools.eu5_save_parser.demand_analysis `
  data\save_analysis\<save filename>
```

Use `--use-saved-classes` to analyze the class ids persisted in the save
instead of replaying the current classifier. `--country HUN` may be repeated
to restrict the report. The default output directory is
`<analysis>/demand_strategy_analysis/`:

Use `--disable-four-stratum-gate` only for a diagnostic run that deliberately
allows worsening. The default keeps the hard gate. Diagnostic output records
the largest relative absolute-error increase among the four strata in
`approx_max_worsening_percentage`; a zero-error raw stratum that worsens is
reported as infinity rather than assigned a misleading finite percentage.

Use `--relax-total-constraint` for a separate diagnostic that adds free-total
and soft-total L2 candidates. These candidates retain nonnegative factors but
replace exact total preservation with a tunable total-drift penalty; the
default five strategies and hard gate remain unchanged without this flag.

- `demand_country_results.csv` records classification capacities, exact-solve
  feasibility, every approximation candidate strategy, the selected strategy,
  all four factors, how many strata improve or worsen in each country, and the
  selected candidate's maximum worsening percentage;
- `demand_stratum_results.csv` contains one row per country and stratum, with
  target and raw spending, signed/absolute/relative raw error, approximate and
  exact error, absolute improvement, improvement ratio, and an explicit
  `improved` / `worsened` / `unchanged` label;
- `demand_stratum_summary.csv` contains exactly four rows and never combines
  nobles, clergy, burghers, and lower into one headline score;
- `demand_strategy_summary.csv` compares the candidate strategies by the
  number of countries passing the four-stratum gate and their mean/median
  improvement ratio;
- `demand_analysis_metadata.json` records inputs, classifier parameters, and
  the approximation method.

The analyzer tries five total-constrained nonnegative strategies: the previous
balanced normalized L2 objective, raw-error-normalized L2, target-normalized
L2, absolute L2, and a minimax normalized-residual solve. Every nonempty class
active set is enumerated. By default, a candidate is accepted only when all
four strata strictly reduce their absolute target error; accepted candidates
are ranked by the mean of the four stratum improvement ratios. If no candidate
passes, the applied approximation is explicitly `gate_rejected` and keeps raw
coefficients. The diagnostic `--disable-four-stratum-gate` mode ranks all
available candidates and reports worsening instead of applying this filter.
The diagnostic `--relax-total-constraint` mode adds a free-total candidate and
three soft total-penalty candidates to test whether a small total drift buys
additional four-stratum improvements.
The reports evaluate all four strata independently so an improvement in one
cannot hide a worsening in another.
