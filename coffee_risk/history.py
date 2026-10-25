import numpy as np
import pandas as pd
from dataclasses import replace
from .model import simulate,economics,risk
COLS=['arabica_usd_kg','robusta_usd_kg','usd_irr']

def validate_history(frame):
    df=frame.copy()
    if not set(['date']+COLS).issubset(df.columns):
        raise ValueError('Required columns: date,'+','.join(COLS))
    df['date']=pd.to_datetime(df['date'],errors='raise',utc=True).dt.tz_localize(None)
    if df.date.isna().any() or df.date.duplicated().any(): raise ValueError('Missing or duplicate dates')
    if (df.date>pd.Timestamp.now(tz='UTC').tz_localize(None)).any(): raise ValueError('Future dates')
    df[COLS]=df[COLS].apply(pd.to_numeric,errors='raise')
    if not np.isfinite(df[COLS]).all().all() or (df[COLS]<=0).any().any():
        raise ValueError('History must contain finite positive values')
    monthly=df.sort_values('date').set_index('date')[COLS].resample('MS').mean()
    if monthly.isna().any().any(): raise ValueError('Missing calendar months; no forward filling is allowed')
    return monthly

def calibrate(monthly):
    if len(monthly)<13: raise ValueError('Need 13 aligned monthly observations; six months is too short')
    ret=np.log(monthly/monthly.shift(1)).dropna()
    vol=ret.std(ddof=1).to_numpy()*np.sqrt(12)
    corr=ret.corr().fillna(0).to_numpy(copy=True)
    np.fill_diagonal(corr,1)
    return vol,corr

def backtest(monthly,deal,train=24,confidence=.95,seed=42):
    if deal.months!=3: raise ValueError('Backtest supports three-month horizon')
    if len(monthly)<train+3: raise ValueError(f'Need at least {train+3} monthly observations')
    rows=[]
    for end in range(train-1,len(monthly)-3,3):
        vol,corr=calibrate(monthly.iloc[end-train+1:end+1])
        base=monthly.iloc[end].to_numpy()
        d=replace(deal,arabica_usd_kg=base[0],robusta_usd_kg=base[1],usd_irr=base[2])
        sample,_=simulate(d,vol,[0]*3,corr,n=5000,seed=seed+end)
        baseline=economics(d)['total_irr']
        limit=risk(sample['total_irr'],baseline,confidence)['var_irr']
        actual=economics(d,monthly.iloc[end+3].to_numpy()/base)['total_irr']-baseline
        rows.append(dict(origin=str(monthly.index[end].date()),target=str(monthly.index[end+3].date()),
                         var_irr=limit,realized_loss_irr=float(actual),breach=bool(actual>limit)))
    return pd.DataFrame(rows)


