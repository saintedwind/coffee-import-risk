# Coffee Risk — transparent coffee import pricing

A runnable Python/Streamlit application for Arabica/Robusta imports into Iran: shipment sizing, blended purchase value, landed costs, pricing, correlated three-month Monte Carlo, cost-overrun VaR/CVaR, stress testing and retrospective validation.

**No trained AI, fabricated live prices, or automatic trading.** The intelligence is explicit statistical calibration, data validation and reproducible scenario calculations. All startup inputs are illustrative. Contract-specific inputs cannot be reliably inferred from a public market feed.

## Run locally

Python 3.11 or 3.12 recommended. From this repository directory:

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m streamlit run app.py
```

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m streamlit run app.py
```

Open the local address printed by Streamlit (normally http://localhost:8501). No API keys are required. No network is used until a Fetch button is pressed. Manual mode works offline after installation.

Tests: `python -m unittest discover -s tests -v` using the virtual environment's Python. GitHub Actions runs on Python 3.11 and 3.12. UI tests use Streamlit AppTest. Network adapter tests use explicit fixtures, not live dependencies. See VALIDATION.md for actual delivery checks.

Docker alternative:

```sh
docker build -t coffee-risk .
docker run --rm -p 127.0.0.1:8501:8501 coffee-risk
```

Dependencies in requirements.txt are pinned at the application level. For a strict deployment lock, freeze the resolved environment after install; platform-specific transitive packages can differ.

## Workflow

1. Choose Arabica weight percentage (Robusta is the remainder). The 60/40 default is only an example.
2. Enter supplier prices manually, or fetch each benchmark and explicitly select **Fetched reference**. Add supplier quality/origin premiums if needed.
3. Choose IRR or toman for money input/display; conversion to internal IRR is automatic. Do not multiply toman input manually. Verify the FX market and settlement availability yourself.
4. Size the shipment by kilograms or coffee-only USD purchase value. Enter sale price, logistics, duty, financing and shrinkage.
5. Set unfixed coffee/FX percentages. A fixed USD invoice has 0% coffee exposure but may still have FX exposure.
6. Set volatility, expected return and correlations manually; alternatively fetch aligned reference history or upload your own history to estimate volatility/correlation.
7. Inspect margin, scenarios, distribution, cost-overrun VaR/CVaR and stress heatmap. Download the audit JSON and simulations.
8. Use the History tab for rolling validation. Downloaded audit JSON can be replayed: `python replay.py coffee-risk-run.json`.

## Real data and provenance

| Input | Adapter | What it actually represents |
|---|---|---|
| Arabica | [FRED PCOFFOTMUSDM](https://fred.stlouisfed.org/series/PCOFFOTMUSDM) | IMF Other Mild Arabica monthly global benchmark |
| Robusta | [FRED PCOFFROBUSDM](https://fred.stlouisfed.org/series/PCOFFROBUSDM) | IMF Robusta monthly global benchmark |
| USD/IRR | [Frankfurter v2](https://frankfurter.dev/) | Available reference FX, **not verified Iranian free-market or executable settlement FX** |
| Supplier/settlement quotes | Manual entry | User-provided source and observation date; not independently verified |
| Joint historical prices | Automatic 2/3/5/10-year fetch or CSV upload | Monthly coffee plus monthly mean reference FX; custom settlement-market history can be uploaded |

FRED quotes are US cents per pound; conversion is cents / 100 / 0.45359237 = USD/kg for **both** series. These are not ICE futures and no futures roll adjustment is appropriate. Monthly observation dates denote the month, not publication time. Publication time is not invented.

Each successful fetch records source URL, original observation date, retrieval UTC time, unit, source description and SHA-256 of the response. The application labels it provider-retrieved, never guarantees that it is a verified live quote. Provider identity is retained for FX when supplied. Old coffee observations (>75 days) and FX observations (>7 days) trigger a warning. A failed refresh shows an error and retains previous successful data with their old timestamps; it never substitutes demo data.

All fetched values can be overridden by switching to manual entry, with original provider metadata preserved in the audit. Manual source left blank is classified illustrative/unverified. The audit records active values, deal terms, premiums via adjusted prices, model parameters, seed and outputs.

FRED/IMF data have their own attribution/usage terms. Source links are included; downloaded market datasets are **not bundled or relicensed** under the code license. Check provider rights before redistributing history. The free-market Iranian FX rate cannot safely be inferred from official/reference FX; the application intentionally requires manual or licensed history for that market. Automatic historical downloads use reference FX only, retain provider metadata, restrict to completed calendar months and join on common months without filling gaps.

## Model contract

Factors are ordered Arabica, Robusta, USD/IRR. Weight fractions sum to one. Purchase value shares are proportional to weight × USD/kg; they are not weight shares.

- Coffee invoice = quantity × weighted effective unit prices.
- Effective price = current price × [1 + unfixed_fraction × (simulated_factor − 1)].
- Effective FX follows the same rule; it applies to all USD goods, freight and insurance.
- CIF = (invoice + foreign freight/fees) × (1 + insurance rate).
- Landed cost = CIF × effective FX × (1 + duty rate) + local costs.
- Finance = landed cost × annual simple finance rate × 3/12.
- Total = landed cost + finance + roasting + packaging + distribution.
- Sellable quantity = imported quantity × (1 − transit shrinkage) × roasting yield.
- Potential revenue = sellable quantity × list sale price × (1 − discount). Sold allocation and unsold stock are shown separately.
- Margin = (revenue − total cost) / revenue.
- Required net price at margin m = cost per sellable kg / (1 − m); required list price also divides by (1 − discount).

Duty base is simplified to CIF. The model does not infer local tax law. Add nonrecoverable taxes/fees explicitly; recoverable VAT cash timing, payment schedules, inventory resale valuation, hedging fees require extensions. Roasting yield/cost, packaging, distribution, discounts and provisional sold/inventory allocations are implemented. Shrinkage can represent aggregate mass loss, but select the output stage explicitly; global green benchmarks are not roasted supplier offers.

Monte Carlo uses correlated geometric Brownian terminal factors:
`exp((mu − sigma²/2)T + sigma sqrt(T) Z)`, T=0.25 years, Z correlated normal. Mu is annual expected arithmetic growth in the GBM sense; sigma is annual log-return volatility. Correlation must be positive semidefinite, including singular valid matrices. No invalid matrix is silently repaired.

Logistics has a separate mean-one lognormal multiplier whose coefficient of variation is user-set. It affects USD freight and local costs, independently of markets. Correlation and volatilities are constant; jumps and structural breaks are not modeled.

**Loss = simulated total cost − baseline total cost.** VaR is its confidence quantile; CVaR is the exact empirical upper-tail average with fractional boundary weighting. Negative VaR is allowed. Loss probability means negative modeled contribution margin at the fixed sale price. These are distinct measures. Suggested risk-covered selling price uses the cost quantile divided by sellable kg and (1−target margin).

The dashboard shows distribution percentiles, an approximate binomial Monte Carlo error bar and ten-batch VaR stability range. These quantify numerical sampling noise, **not** parameter uncertainty. Editable stress scenarios are intended to explore parameter/model uncertainty.

## Calibration and backtesting

CSV schema:
`date,arabica_usd_kg,robusta_usd_kg,usd_irr`.
Dates are ISO Gregorian. Values must be finite and positive. Duplicate/future dates and missing calendar months are rejected. Daily observations are averaged monthly. Never mix different FX regimes without documenting it.

`examples/ILLUSTRATIVE_history.csv` is deterministic synthetic test data, **not real market history**. It is deliberately named and classified as illustrative. It exercises upload, calibration and backtesting offline.

Historical covariance uses contemporaneous monthly log returns, annualized by 12; zero-volatility series have zero cross-correlations and diagonal one. No forward filling, interpolating or expanding six monthly observations into fake daily samples.

At least 13 monthly levels are required for calibration. For meaningful estimates, prefer 36–60+ aligned months and examine regime changes. Six-month data remain available for recent-history inspection but are insufficient for trustworthy tail estimation.

Backtest: rolling 24-month training windows, zero drift, 5,000 seeded simulations per origin, non-overlapping three-month forecast targets, constant deal terms and fixed logistics. Future observations are excluded from training. It reports actual cost overrun, predicted VaR, breaches, nominal breach rate and Wilson interval. At least 27 months are required even for one test. Small samples cannot establish calibration quality.

This is a **retrospective revised-data** test: historical publication vintages and release lags are not available, so it must not be described as a real-time trading validation. Historical logistics and sale prices are not validated. The UI's drift/logistics assumptions are intentionally not reused in this narrower market-risk backtest.

## Repository structure

- app.py — interactive dashboard and audit exports
- coffee_risk/model.py — pure economics and simulation functions
- coffee_risk/data.py — bounded HTTPS adapters and provenance
- coffee_risk/history.py — validation, calibration, rolling tests
- replay.py — reproduce downloaded run without the dashboard
- tests/ — accounting identities, exposures, units, distributions, missing-data and UI tests
- examples/ — explicitly synthetic history and its generator
- .github/workflows/tests.yml — CI
- .env.example, Dockerfile, .streamlit/config.toml — setup

## Repository

Published source: https://github.com/saintedwind/coffee-import-risk

```sh
git clone https://github.com/saintedwind/coffee-import-risk.git
cd coffee-import-risk
```

The code and explicitly illustrative example data are included. Private supplier quotes, credentials, downloaded market histories and the original conversation are not part of this repository. See README.fa.md for the Persian guide and VALIDATION.md for recorded checks.

Streamlit Community Cloud can deploy app.py from that repository using requirements.txt. For public deployment, add authentication and review supplier-data privacy; uploaded histories and run values are session data. No arbitrary provider URLs or executable uploads are accepted.

## Scope

Useful for transparent decision support and scenario comparison, not a guarantee of future prices or margins. Public benchmarks differ from origin, grade, freight terms and executable settlement prices. All defaults, including duties and FX, must be replaced before evaluating an actual transaction.


## Extended real-data evaluation (2026-10-25)

See [the evaluation report](reports/REVIEW_2026-10-25_FA.md) and [machine-readable results](reports/2026-10-25-usd/results.json). The comparison covers 120 actual FRED coffee months, two training windows and three quantiles. At 95% confidence with 24-month training, GBM breached 6/32 times (18.75%), versus nominal 5%: tail coverage is inadequate in this sample. Do not present the model as validated for procurement decisions.

Run `python live_validate.py --coffee-usd --years 10 --output reports/new-run` for coffee-only USD evaluation. Without `--coffee-usd`, the command requires actual reference FX too. Failed downloads are recorded and never replaced with synthetic values. The USD-only path uses an identity currency conversion; it does not simulate or validate Iranian FX.

The dashboard now compares GBM against historical three-month changes and reports mean quantile loss (lower is better). Training data exclude forecast targets. Overlapping historical training changes and shared rolling windows limit independence; Wilson intervals are descriptive. Current incomplete months are rejected from calibration history. Real data evaluated here are revised monthly averages, not real-time publication vintages.

## Probabilistic model comparison — 2026-10-26

Added joint moving-block resampling, EWMA-filtered historical scenarios, positive-conditioned Student-t simple returns (fixed df=5), and block-bootstrap parameter sensitivity. See [the full methods and limitations](reports/PROBABILISTIC_REVIEW_2026-10-26_FA.md) and [fresh real-data results](reports/2026-10-26-advanced/results.json).

Run `python live_validate.py --coffee-usd --advanced --years 10 --output reports/new-run`. The dashboard History tab offers the same fixed-model comparison (24-month training) and sensitivity export; the primary scenario engine is not silently switched. Results are retrospective revised monthly benchmarks, not prospective validation. Chronological partitions overlap previously inspected data and are NOT an untouched holdout. No hyperparameter selection or winner promotion occurred.

The 120-month real FRED evaluation includes 24/36/60-month training and 90/95/99% quantiles. With 24-month training at 95%, breaches were GBM 6/32, historical 6/32, block 6/32, EWMA-block 4/32, Student-t 5/32. EWMA improves coverage counts but has worse quantile loss than GBM. No uniformly superior or decision-grade model is claimed. FX retrieval failed explicitly; successful results are coffee-only USD. Bootstrap artificial histories are parameter perturbations, never fabricated market observations. Parameter ranges are not calibrated confidence intervals. Recorded evidence is retained; publication recheck is documented below.

## Operational release — 2026-10-27

See [the detailed evaluation](reports/2026-10-27-release/RELEASE_REVIEW_FA.md) and [numeric results](reports/2026-10-27-release/results.json). IRR/toman conversion, component costs, roasting/sales allocations, five operational engines, evidence manifests, private documents and digest-checked future forecast records are implemented. Private records are excluded from Git and Docker build contexts. No uploaded invoice has been independently verified.

The dated example [manifest](reports/2026-10-27-release/market-scenario-manifest.json) uses actual monthly FRED benchmarks and user-reported 271,000 toman/USD with explicitly assumed commercial costs. Load via Shipment evidence. It is not an actual trade invoice or a live retail quote. Snapshot values remain dated; fetching new data does not imply transaction verification.

The history-only FX identity is not an exchange rate feed. Set FX unfixed=0 for operational coffee-only scenarios; retrospective tests are USD-only. Manual GBM risk assumptions remain separate from history-based forecasts. zero_log makes simulated terminal mean log growth equal across methods; it does not equalize expected arithmetic growth. No model is automatically promoted.

68 tests passed, and all five engines were exercised through Streamlit AppTest with real fetched history; audit replay matched exactly. Raw market history stays outside the repository. Results still show inadequate risk coverage and large mismatches to some seller listings. No forced fit to market prices or guarantee of decision accuracy is claimed. See the report for all assumptions and failed comparisons. Run `python evaluate_release.py` to reproduce this dated release scenario; retailer/FX reference observations in that script are frozen on 2026-10-27, not automatically refreshed quotes. The forecast registry is local and digest-checked, not trusted timestamping. Do not represent past-data tests as prospective validation.

## Publication audit

See [publication checks and retained limitations](reports/PUBLICATION_2026-11-01.md). October experiment reports preserve their original dates and may describe the then-local state; they are not fresh market quotes. Historical prices and claimed live runs are not redated to publication time.
