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
