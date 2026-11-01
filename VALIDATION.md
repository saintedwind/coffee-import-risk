# Delivery validation

Checked on 2026-10-24 using Python 3.12 on Windows.

- 30 automated tests passed, zero failures and zero skips.
- Includes Streamlit AppTest default rendering, changing blend to 100% Arabica, purchase-value sizing, reference/manual override, missing-fetch fail-closed behavior, historical calibration and rolling backtest interaction.
- Numerical checks cover a hand-calculated invoice, value shares, fixed-price/FX exposures, deterministic zero volatility, seeded reproducibility, simulated correlation and expected returns, positive-semidefinite validation and upper-tail risk.
- Data checks cover unit conversion, unavailable sources, wrong currency pairs, malformed history, missing months and future-training exclusion.
- A dashboard audit JSON was exported and replayed: VaR/CVaR matched exactly.
- Independent Streamlit process started successfully; local HTTP health endpoint returned OK. Process was stopped after the check.
- Actual network fetches succeeded for FRED Arabica and Robusta and Frankfurter USD/IRR. Latest coffee observation month was September 2026. Retrieval occurred on 2026-10-24. These are provider observations, not independently verified executable market quotes.
- Five-year joint historical fetch returned 60 aligned monthly observations; the most recent six were April–September 2026.
- No real market-history dataset is redistributed in this archive. The included CSV is explicitly synthetic.
- Tested application versions: NumPy 2.2.6, pandas 2.3.3, Streamlit 1.50.0, Plotly 6.3.1.
- Docker and GitHub-hosted CI are supplied but were not executed in this environment.
- The interface was exercised through Streamlit AppTest, not a manual cross-browser visual inspection.
- No GitHub remote was created or pushed.

Provider status can change after this check. The application reports failures explicitly and never generates substitute live values.


## Publication recheck — 2026-10-25

All 30 automated tests passed again on the publication copy, including Streamlit AppTest and numerical/data checks. No fresh market-price claim was made in this recheck; the live-fetch observations above are dated 2026-10-24. Public source: https://github.com/saintedwind/coffee-import-risk . GitHub CI status is available in the Actions tab.

## Extended check — 2026-10-25

35 tests passed after the comparison, parameter-validation and incomplete-month changes. Actual fresh FRED requests succeeded for both coffee series (417 observations each); 120 recent complete months were evaluated in six retrospective configurations. FX requests failed explicitly. Coffee-only USD evaluation succeeded; joint FX evaluation did not. See reports/REVIEW_2026-10-25_FA.md and retained JSON/CSV receipts. The 95% GBM tail is undercovered in this sample; no claim of risk calibration success is made. Changes are local, not yet pushed.

## Probabilistic model comparison — 2026-10-26

Added joint moving-block resampling, EWMA-filtered historical scenarios, positive-conditioned Student-t simple returns (fixed df=5), and block-bootstrap parameter sensitivity. See [the full methods and limitations](reports/PROBABILISTIC_REVIEW_2026-10-26_FA.md) and [fresh real-data results](reports/2026-10-26-advanced/results.json).

Run `python live_validate.py --coffee-usd --advanced --years 10 --output reports/new-run`. The dashboard History tab offers the same fixed-model comparison (24-month training) and sensitivity export; the primary scenario engine is not silently switched. Results are retrospective revised monthly benchmarks, not prospective validation. Chronological partitions overlap previously inspected data and are NOT an untouched holdout. No hyperparameter selection or winner promotion occurred.

The 120-month real FRED evaluation includes 24/36/60-month training and 90/95/99% quantiles. With 24-month training at 95%, breaches were GBM 6/32, historical 6/32, block 6/32, EWMA-block 4/32, Student-t 5/32. EWMA improves coverage counts but has worse quantile loss than GBM. No uniformly superior or decision-grade model is claimed. FX retrieval failed explicitly; successful results are coffee-only USD. Bootstrap artificial histories are parameter perturbations, never fabricated market observations. Parameter ranges are not calibrated confidence intervals. Changes remain local pending publication.

## Operational release — 2026-10-27

68 automated tests passed. Real FRED history was retrieved anew, six retrospective model configurations compared, detailed breach attribution recorded and dated Iranian listing/FX observations compared without forced fitting. All five operational engines were exercised using actual fetched history via AppTest; downloaded audit replay matched VaR/CVaR exactly. Monetary-unit switching preserved economics. Evidence, unit, monthly-history, stage and private-storage checks are covered. No invoice validation, live execution price, complete Iranian settlement-FX risk calibration or future outcome is claimed. See reports/2026-10-27-release/RELEASE_REVIEW_FA.md. Local changes not yet pushed.

## Publication recheck — 2026-11-01

68 regression tests passed again. Source and selected October real-data evidence are published together; see reports/PUBLICATION_2026-11-01.md. Earlier references to local/unpushed status describe the historical check date, not the present publication. No new live price or invoice validation is claimed.
