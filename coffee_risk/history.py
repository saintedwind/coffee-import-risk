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
    current_month=pd.Timestamp.now(tz='UTC').tz_localize(None).to_period('M').to_timestamp()
    if (df.date>=current_month).any():
        raise ValueError('Incomplete current month is not allowed in calibration history')
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
    if not isinstance(train,int) or train<13: raise ValueError('Training window must be at least 13 months')
    if not .5<confidence<1: raise ValueError('Confidence must be between 0.5 and 1')
    if len(monthly)<train+3: raise ValueError(f'Need at least {train+3} monthly observations')
    rows=[]
    for end in range(train-1,len(monthly)-3,3):
        vol,corr=calibrate(monthly.iloc[end-train+1:end+1])
        base=monthly.iloc[end].to_numpy()
        d=replace(deal,arabica_usd_kg=base[0],robusta_usd_kg=base[1],usd_irr=base[2])
        sample,_=simulate(d,vol,[0]*3,corr,n=5000,seed=seed+end)
        baseline=economics(d)['total_irr']
        limit=risk(sample['total_irr'],baseline,confidence)['var_irr']
        # Overlapping observed changes: descriptive baseline, not independent trials.
        window=monthly.iloc[end-train+1:end+1]
        historical_factors=(window/window.shift(3)).dropna().to_numpy()
        historical_costs=economics(d,historical_factors)['total_irr']
        historical_limit=risk(historical_costs,baseline,confidence)['var_irr']
        actual=economics(d,monthly.iloc[end+3].to_numpy()/base)['total_irr']-baseline
        rows.append(dict(origin=str(monthly.index[end].date()),target=str(monthly.index[end+3].date()),
                         var_irr=limit,realized_loss_irr=float(actual),breach=bool(actual>limit),
                         historical_var_irr=historical_limit,historical_breach=bool(actual>historical_limit),
                         quantile_loss_irr=float((confidence-(actual<limit))*(actual-limit)),
                         historical_quantile_loss_irr=float((confidence-(actual<historical_limit))*(actual-historical_limit))))
    return pd.DataFrame(rows)



def summarize_backtest(frame,confidence=.95):
    """Descriptive coverage; Wilson intervals assume independent Bernoulli trials."""
    if frame.empty or not .5<confidence<1: raise ValueError('Need results and valid confidence')
    result={'origins':len(frame),'nominal_breach_rate':1-confidence,'models':{}}
    for name,prefix in [('gbm',''),('historical','historical_')]:
        count=len(frame); hits=int(frame[prefix+'breach'].sum()); p=hits/count; z=1.959963984540054
        den=1+z*z/count
        center=(p+z*z/(2*count))/den
        half=z*np.sqrt(p*(1-p)/count+z*z/(4*count*count))/den
        result['models'][name]={'breaches':hits,'breach_rate':p,
            'wilson_95':[max(0.,center-half),min(1.,center+half)],
            'mean_quantile_loss_irr':float(frame[prefix+'quantile_loss_irr'].mean())}
    return result
