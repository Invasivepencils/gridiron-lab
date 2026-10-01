# Gridiron Lab

An NFL quantitative research project exploring team strength, player availability,
and pregame win probabilities. The goal is to measure whether injury information
improves forecasts on unseen games, then compare calibrated forecasts with
contemporaneous market prices after trading costs.

**Status: working research scaffold.** This version has an online team-strength
baseline, injury-scenario simulation, CSV validation, chronological backtesting,
and an optional free-data acquisition adapter. It does not yet have fitted player
effects, verified real-season injury coverage, or evidence of a trading edge.
All bundled examples are synthetic and use fictional teams and players.

## Run the example

Requires Python 3.11 or newer. From this project directory:

```powershell
python -m gridiron_lab.cli backtest --games examples/games.csv --injuries examples/injuries.csv --out reports/demo-backtest.json
python -m gridiron_lab.cli forecast --games examples/games.csv --injuries examples/injuries.csv --game-id DEMO_4 --cutoff 2024-09-28T17:00:00Z --out reports/demo-forecast.json
python -m unittest discover -s tests -v
```

The backtest compares Brier score, log loss, and calibration bins. Injury-adjusted
and baseline scores are compared on the same subset with injury reports. Ties are
excluded from binary scoring and counted separately. Run parameters and SHA-256
input hashes are saved with each report. Lower Brier and log loss are better;
the tiny example is only a functionality check, not performance evidence.

## Free public data

```powershell
python -m pip install -e ".[data]"
python -m gridiron_lab.cli fetch --seasons 2022 2023 2024 2025 2026 --out data/raw
```

This optional adapter archives nflverse schedules, team/player stats, injury
reports, and snap counts, alongside a retrieval manifest. It flags empty tables,
download failures, and missing seasons when a season column exists. The adapter
requires internet access and has not been tested against live downloads in this
initial scaffold. Large-scale play-by-play ingestion and feature engineering
remain to be implemented; the baseline currently trains on game scores.

Raw provider CSVs are **not** interchangeable with the normalized engine inputs.
The next implementation step is a provider-to-engine normalization layer with
coverage checks, stable team/player IDs, official-result reconciliation, and
documented timestamp semantics. Do not manufacture publication timestamps from
game dates. Preserve raw files; do not redistribute provider data until its
license and source-specific terms have been checked.

Primary source references:

- [nflreadpy load functions](https://nflreadpy.nflverse.com/api/load_functions/)
- [nflverse availability schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
- [nflverse data dictionaries](https://nflreadr.nflverse.com/articles/)
- [Kalshi market rules](https://help.kalshi.com/en/articles/13823822-market-rules)

The current availability page reports daily injury updates. An older cached page
reported an injury-data interruption after 2024, so actual season coverage must
be verified rather than assumed. Participation data from 2023 onward is released
after the postseason, making it unsuitable as an in-season live source. nflverse
recommends refreshing play-by-play after weekly stat corrections. Downloaded
historical data can contain revisions unavailable at historical prediction time.

## Input contracts

`games.csv` fields:

- `game_id`, `season`, `week`, `home`, `away`: stable matchup identifiers.
- `kickoff`: timezone-aware ISO timestamp; postseason season is the NFL season.
- `home_score`, `away_score`: both blank for future games, both populated otherwise.
- `result_available_at`: earliest verified time the result was usable by this
  research process; required after kickoff for completed games.
- `neutral`: `true` or `false`; suppresses home-field advantage when true.

`injuries.csv` fields:

- `game_id`, `team`, `player_id`: matchup and player identity.
- `observed_at`: time the report became available, not merely its nominal date.
- `absence_probability`: externally supplied probability in [0, 1]. No automatic
  conversion of questionable/doubtful designations into invented probabilities.
- `impact_points`: assumed nonnegative loss in team scoring margin when absent,
  relative to a specified replacement. This is not a learned player ranking.
- `impact_sd`: standard deviation for a Gaussian effect truncated at zero.
  Truncation means `impact_points` is a location parameter, not exactly the mean
  when uncertainty is substantial.
- `impact_available_at`: when this estimate or assumption was first available.
  An estimate fitted using future-season outcomes cannot enter an earlier forecast.
- `source`: report provenance; retain URL and original publication metadata in
  the source archive. The example uses an explicit synthetic label.

Latest known report per team/player is selected at the forecast cutoff. Later
reports are excluded. Duplicate timestamps and future impact estimates fail.
Missing reports are missing coverage, not evidence of a fully healthy lineup.

## Modeling approach and limits

Team ratings update after usable results, based on clipped prediction errors in
score margin. New seasons shrink old ratings toward league average. A Gaussian
margin model turns relative ratings and home-field advantage into probabilities.
Defaults are transparent but uncalibrated; no parameters were selected on real
data in this version.

The injury simulator samples absences and uncertain effects, then integrates
game-level margin noise analytically. It reports probability changes, simulation
standard error, and 5th/95th percentiles across injury scenarios. These percentiles
are not posterior credible intervals, and simulation precision does not measure
model accuracy. Simultaneous absences are assumed independent; shared injury
risks, replacement interactions, and team-rating uncertainty are not modeled.

The baseline describes historically observed rosters, not a hypothetical healthy
team. Adding losses for players already absent in recent games can double count
their effect. Production modeling should jointly estimate team strength and
availability, or define effects relative to the roster represented by the baseline.
Isolated player probability changes are scenario sensitivities, not additive
attributions or demonstrated causal effects.

## Research milestones

1. Verify and normalize 2022–2026 free datasets; report season/week coverage,
   missingness, revisions, identity mappings, and timestamp quality. Current-season
   data is partial. Archive prospective injury snapshots from now onward.
2. Add lagged opponent-adjusted EPA/play, success rate, turnovers, pressure,
   rest, travel, and roster continuity using only information available at cutoff.
3. Estimate regularized player effects by position and replacement quality, with
   partial pooling and uncertainty. Treat quarterback effects separately. Control
   for team, opponent, role, and shared snaps. Avoid equating fantasy production
   with impact on winning or claiming observational effects are causal.
4. Learn designation-to-availability probabilities on training windows. Fit team
   and player effects together to address baseline double counting.
5. Evaluate rolling season/week splits and tune only inside earlier training
   windows. Reserve a final season as untouched evaluation. Compare score ratings,
   EPA baselines, injury models, and timestamp-matched market probabilities.
   Bootstrap uncertainty by week/season; assess position and injury-coverage strata.
6. Produce weekly predictions at fixed horizons (e.g. 72h, 24h, 90m), roster
   scenarios, contextual player-impact rankings, and forecast revision logs.
7. Add read-only Kalshi quotes with bid/ask, timestamp, fees, liquidity, and exact
   settlement semantics. For a $1 binary payout, expected net payoff per contract
   is `p - executable_price - fees - slippage`; tie/void rules may change this.
   A likely winner is not necessarily a favorable price. Validate any decision
   threshold out of sample and paper-track it prospectively.

## GitHub

Repository: [Invasivepencils/gridiron-lab](https://github.com/Invasivepencils/gridiron-lab).
CI, a license selected by the author, live ingestion, and a dashboard can be
added in subsequent iterations.
