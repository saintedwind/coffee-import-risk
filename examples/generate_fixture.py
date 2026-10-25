"""Generate illustrative history, never market data."""
from pathlib import Path
import numpy as np
import pandas as pd
rng=np.random.default_rng(2026)
values=np.exp(np.cumsum(rng.normal(0,.06,(72,3)),axis=0))*[6,4,800000]
df=pd.DataFrame(values,columns=['arabica_usd_kg','robusta_usd_kg','usd_irr'])
df.insert(0,'date',pd.date_range('2019-01-01',periods=72,freq='MS'))
df['classification']='ILLUSTRATIVE_SYNTHETIC_NOT_MARKET_DATA'
df.to_csv(Path(__file__).with_name('ILLUSTRATIVE_history.csv'),index=False)

