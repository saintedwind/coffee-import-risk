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
3. Enter USD/IRR as **rial per USD**. Multiply toman quotes by 10. Verify the FX market and settlement availability yourself.
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
- Total = landed cost + finance.
- Sellable quantity = imported quantity × (1 − shrinkage).
- Revenue = sellable quantity × fixed net sale price.
- Margin = (revenue − total cost) / revenue.
- Required price at margin m = cost per sellable kg / (1 − m).

Duty base is simplified to CIF. The model does not infer local tax law. Add nonrecoverable taxes/fees explicitly; recoverable VAT cash timing, payment schedules, inventory resale valuation, roasting conversion yields and hedging fees require extensions. Shrinkage can represent aggregate mass loss, but this is a green-coffee shipment model.

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

