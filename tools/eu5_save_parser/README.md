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
