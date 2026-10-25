"""Fail-closed adapters: never substitute demo observations."""
from datetime import datetime,timezone
from io import StringIO
import json,urllib.request,hashlib
import pandas as pd
import numpy as np
SERIES={'arabica_usd_kg':'PCOFFOTMUSDM','robusta_usd_kg':'PCOFFROBUSDM'}

def read_url(url):
    req=urllib.request.Request(url,headers={'User-Agent':'CoffeeRisk/1.0'})
    with urllib.request.urlopen(req,timeout=25) as response: payload=response.read(10000001)
    if len(payload)>10000000: raise ValueError('Provider response too large')
    return payload

def check_values(df):
    if df.empty or not np.isfinite(df.value).all() or (df.value<=0).any():
        raise ValueError('Empty or invalid provider values')
    if df.date.duplicated().any() or df.date.isna().any(): raise ValueError('Invalid provider dates')
    if (df.date>pd.Timestamp.now(tz='UTC').tz_localize(None)).any(): raise ValueError('Future observations')

def provenance(df,url,source,unit,kind,raw):
    row=df.sort_values('date').iloc[-1]
    return dict(source=source,url=url,observation_date=str(row.date.date()),
                retrieved_at=datetime.now(timezone.utc).isoformat(),unit=unit,kind=kind,
                value=float(row.value),sha256=hashlib.sha256(raw).hexdigest(),
                status='Provider retrieved; not an executable live quote')

def fetch_coffee(name):
    series=SERIES[name]
    endpoint=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    raw=read_url(endpoint)
    df=pd.read_csv(StringIO(raw.decode('utf-8-sig')))
    if series not in df or len(df.columns)!=2: raise ValueError('Unexpected FRED schema')
    df.columns=['date','value']
    df.date=pd.to_datetime(df.date,errors='raise')
    df.value=pd.to_numeric(df.value.replace('.',np.nan),errors='raise')/100/.45359237
    df=df.dropna().sort_values('date')
    check_values(df)
    return df,provenance(df,endpoint,'FRED / IMF '+series,'USD/kg','Monthly period average',raw)

def fetch_fx():
    endpoint='https://api.frankfurter.dev/v2/rates?base=USD&quotes=IRR&expand=providers'
    raw=read_url(endpoint)
    rows=json.loads(raw)
    if not isinstance(rows,list) or not rows: raise ValueError('USD/IRR unavailable; enter manual quote')
    if any(x.get('base')!='USD' or x.get('quote')!='IRR' for x in rows):
        raise ValueError('Unexpected currency pair')
    df=pd.DataFrame({'date':[x['date'] for x in rows],'value':[x['rate'] for x in rows]})
    df.date=pd.to_datetime(df.date,errors='raise')
    df.value=pd.to_numeric(df.value,errors='raise')
    check_values(df)
    meta=provenance(df,endpoint,'Frankfurter reference FX','IRR/USD',
                    'Reference rate; NOT verified Iranian free-market or settlement rate',raw)
    meta['providers']=rows[-1].get('providers',[])
    return df,meta


def fetch_joint_history(years=5):
    """Monthly coffee benchmarks plus monthly mean reference FX, no interpolation."""
    from .history import validate_history
    if years not in (2,3,5,10): raise ValueError('Unsupported history range')
    today=pd.Timestamp.now(tz='UTC').tz_localize(None)
    end=today.replace(day=1).normalize()-pd.Timedelta(days=1)
    start=(end.to_period('M')-(years*12-1)).to_timestamp()
    url=('https://api.frankfurter.dev/v2/rates?base=USD&quotes=IRR'
         f'&from={start.date()}&to={end.date()}')
    raw=read_url(url)
    rows=json.loads(raw)
    if not isinstance(rows,list) or not rows: raise ValueError('Reference FX history unavailable')
    if any(x.get('base')!='USD' or x.get('quote')!='IRR' for x in rows):
        raise ValueError('Unexpected historical currency pair')
    fx=pd.DataFrame({'date':[x['date'] for x in rows],'value':[x['rate'] for x in rows]})
    fx.date=pd.to_datetime(fx.date,errors='raise')
    fx.value=pd.to_numeric(fx.value,errors='raise')
    check_values(fx)
    fxmeta=provenance(fx,url,'Frankfurter historical reference FX','IRR/USD','Daily reference observations; averaged monthly',raw)
    combined=fx.set_index('date').rename(columns={'value':'usd_irr'}).resample('MS').mean()
    metas={'usd_irr':fxmeta}
    for key in SERIES:
        coffee,meta=fetch_coffee(key)
        metas[key]=meta
        combined=combined.join(coffee.set_index('date').rename(columns={'value':key}),how='inner')
    combined=combined.loc[start:end].reset_index()
    if combined.empty: raise ValueError('No common historical months')
    return validate_history(combined),metas

