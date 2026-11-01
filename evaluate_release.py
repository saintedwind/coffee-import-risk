"""Release evaluation: real benchmark fetch, explicit assumptions, no forced price fit."""
import json,urllib.request,hashlib,sys
from pathlib import Path
from dataclasses import replace,asdict
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from coffee_risk import data
from coffee_risk.model import Deal,economics,risk
from coffee_risk.money import cost_breakdown,required_price,from_irr
from coffee_risk.history import validate_history
from coffee_risk.alternatives import compare,comparison_summary,forecast_sample
from coffee_risk.diagnostics import explain_failures,paired_loss_sensitivity
from coffee_risk.registry import register

OUT=Path(__file__).parent/'reports'/'2026-10-27-release'
OUT.mkdir(parents=True,exist_ok=True)
WORK=Path(__file__).resolve().parents[2]/'work'/'coffee-release'
WORK.mkdir(parents=True,exist_ok=True)
receipts=[]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def read(url):
    req=urllib.request.Request(url,headers={'User-Agent':'CoffeeRisk/1.1'})
    with opener.open(req,timeout=30) as response:raw=response.read(10000001)
    if len(raw)>10000000:raise ValueError('Provider response too large')
    receipts.append({'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    return raw
data.read_url=read
report={'evaluation_date_client':'2026-10-27','started_at':datetime.now(timezone.utc).isoformat(),'receipts':receipts,'status':'failed'}
try:
    frames=[];sources={}
    for key in data.SERIES:
        frame,sources[key]=data.fetch_coffee(key)
        frames.append(frame.set_index('date').rename(columns={'value':key}))
    history=frames[0].join(frames[1],how='inner')
    history['usd_irr']=1. # USD conversion identity only, NOT manufactured exchange rate observations.
    history=validate_history(history.tail(120).reset_index())
    history.to_csv(WORK/'actual_coffee_usd_history.csv')
    (WORK/'history-sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    report.update(status='benchmarks_fetched',months=len(history),first=str(history.index[0].date()),last=str(history.index[-1].date()),sources=sources)
    latest=history.iloc[-1]
    user_fx=2710000.
    public_fx=2695000.  # Manually inspected TGJU page, explicitly a listing, not execution.
    report['fx_inputs']={'user':{'irr_per_usd':user_fx,'toman_per_usd':271000,'source':'User message; not executable verified FX'},
                         'public':{'irr_per_usd':public_fx,'source':'https://www.tgju.org/profile/price_dollar_rl','status':'Public display inspected 2026-10-27; source time 19:59:58; not settlement quote'}}
    market_rows=[{'name':'Robusta Vietnam 1 kg roasted','price_toman_kg':2487000,'source':'https://amircano.com/product/قهوه-روبوستا-ویتنام-عمده-بسته-۱۰-کیلو/','stage':'roasted','channel':'retail','available':False,'source_date':None},
                 {'name':'Arabica Brazil Santos 1 kg roasted','price_toman_kg':5700000,'source':'https://kaam.coffee/shop/so-brazil-santos-arabica','stage':'roasted','channel':'retail','available':'not independently confirmed','source_date':None},
                 {'name':'60% Arabica roasted 15 kg lot','price_toman_kg':1125000,'source':'https://eridocoffee.com/wholesale-coffee/','stage':'roasted','channel':'wholesale','available':'not independently confirmed','source_date':'1405/08/01'}]
    report['market_listings']=market_rows
    base=Deal(arabica_usd_kg=float(latest.arabica_usd_kg),robusta_usd_kg=float(latest.robusta_usd_kg),usd_irr=user_fx,sale_irr_kg=30000000.)
    report['assumptions']={'quantity_kg':20000,'freight_usd':4000,'insurance_rate':.01,'duty_rate':.05,'finance_rate':.24,'transit_loss':.02,'months':3,
                           'roast_yield':.84,'roasting_toman_input_kg':50000,'packaging_toman_output_kg':50000,'distribution_toman_output_kg':100000,
                           'target_margin':.20,'status':'Illustrative commercial assumptions; no invoice or legal duty verification. No tuning to listing prices.'}
    scenarios=[]
    for label,weight in [('arabica',1.),('robusta',0.),('blend60_40',.6)]:
        for stage in ('green','roasted'):
            d=replace(base,arabica_weight=weight,roast_yield=.84 if stage=='roasted' else 1.,
                      roast_cost_irr_input_kg=500000 if stage=='roasted' else 0.,
                      packaging_irr_output_kg=500000 if stage=='roasted' else 0.,
                      selling_cost_irr_output_kg=1000000 if stage=='roasted' else 0.)
            e=economics(d)
            public=economics(replace(d,usd_irr=public_fx))
            quote=next((x for x in market_rows if x['name'].startswith('Arabica' if label=='arabica' else 'Robusta') and stage=='roasted'),None) if label!='blend60_40' else market_rows[2] if stage=='roasted' else None
            scenarios.append({'label':label,'stage':stage,'deal':asdict(d),'cost_toman_kg':e['cost_irr_kg']/10,
                              'required_net_price_toman_kg':required_price(e['cost_irr_kg'],.2)/10,
                              'public_fx_cost_toman_kg':public['cost_irr_kg']/10,'components':cost_breakdown(e,'toman'),
                              'listing_gap_pct':(required_price(e['cost_irr_kg'],.2)/10/quote['price_toman_kg']-1)*100 if quote else None,
                              'scope':'Global green monthly benchmark converted to current FX plus assumed costs; not a supplier invoice or forecast of retail listing.'})
    report['scenarios']=scenarios
    usd=Deal(usd_irr=1.,fx_unfixed=0.,freight_usd=0.,insurance_rate=0.,duty_rate=0.,local_cost_irr=0.,finance_rate=0.,shrinkage=0.,sale_irr_kg=1.)
    report['retrospective']={}
    for policy in ('native','zero_log'):
        for train in (24,36,60):
            f=compare(history,usd,train=train,confidence=.95,growth_policy=policy)
            key=f'{policy}_train{train}_q95'
            report['retrospective'][key]={'summary':comparison_summary(f),'paired_loss':paired_loss_sensitivity(f),
                'mean_excess_over_var':{name:float(g.loc[g.breach,'excess_over_var'].mean()) if g.breach.any() else None for name,g in f.groupby('method')}}
            f.rename(columns={'var_irr':'var_usd','cvar_irr':'cvar_usd'}).to_csv(OUT/(key+'.csv'),index=False)
            failures=explain_failures(history,usd,f)
            (OUT/(key+'-failures.json')).write_text(json.dumps(failures,indent=2),encoding='utf-8')
    # Explicit historical reconstruction: coffee benchmark October 2025, publicly dated FX December 1 2025.
    historic=history.loc[pd.Timestamp('2025-10-01')]
    historical=replace(base,arabica_usd_kg=float(historic.arabica_usd_kg),robusta_usd_kg=float(historic.robusta_usd_kg),usd_irr=1190750.)
    he=economics(historical)
    report['historical_reconstruction']={'reference_day':'2025-12-01','coffee_benchmark_month':'2025-10-01','coffee_prices':historic.iloc[:2].to_dict(),
        'fx_irr_per_usd':1190750,'fx_source':'https://t.me/s/tgjunews?before=703103','fx_source_time':'1404/09/10 18:31',
        'local_green_listing_source':'https://eridocoffee.com/raw-coffee-beans-purchase/','local_listing_date':'1404/09/10',
        'local_prices_toman_kg':{'brazil_santos':960000,'vietnam_robusta_screen18':685000},
        'computed_blend_green_cost_toman_kg':he['cost_irr_kg']/10,
        'scope':'Retrospective reconstruction, different origins/grades from IMF Other Mild Arabica; no claim of matched invoice or point-in-time vintage backtest. Costs remain illustrative.'}
    # A real historical forecast example already evaluated above, no retrospective registration.
    example=compare(history,usd,train=24,confidence=.95,growth_policy='zero_log')
    target=str(example.target.iloc[-1]); report['last_observed_historical_target']=json.loads(example[example.target==target].to_json(orient='records'))
    # Current forecast uses latest known reference levels. FX risk excluded from history-based forecast.
    # User FX is a fixed conversion for readability, not fabricated historical FX.
    d=replace(base,fx_unfixed=0.)
    current={}
    for method in ('gbm','historical','block','ewma_block','student_t'):
        sample,_=forecast_sample(history,d,method,n=20000,growth_policy='zero_log',logistics_cv=0.)
        current[method]=risk(sample['total_irr'],economics(d)['total_irr'],.95)
    payload={'target_month':str((pd.Timestamp.now().to_period('M')+3).to_timestamp().date()),
             'model_version':'1.1.0','deal':asdict(d),'sources':sources,'history_end':str(history.index[-1].date()),
             'growth_policy':'zero_log','paths':20000,'seed':42,'logistics_cv':0.,'block_months':3,'ewma_decay':.94,'student_df':5,'cost_unit':'IRR','forecast':current,
             'code_sha256':{name:hashlib.sha256((Path(__file__).parent/'coffee_risk'/name).read_bytes()).hexdigest() for name in ('model.py','alternatives.py')},
             'assumptions':'Current cost benchmark plus user FX held fixed; not a joint Iranian FX risk forecast; horizon approximate monthly; publication lag retained.',
             'outcome':'not observed yet'}
    registered=register(Path(__file__).parent/'private'/'forecast-registry',payload)
    report['forecast_registration']={'record_id':registered['record_id'],'registered_at':registered['registered_at'],'target_month':payload['target_month'],'status':'unsettled'}
    report['current_risk_fixed_fx']=current
    report['status']='success'
except Exception as exc:
    report['error']=f'{type(exc).__name__}: {exc}'
    raise
finally:
    (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
