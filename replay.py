"""Recompute audit runs; monetary internals are always IRR."""
import json,sys
import pandas as pd
from coffee_risk.model import Deal,economics,simulate,risk
from coffee_risk.alternatives import forecast_sample
with open(sys.argv[1],encoding='utf-8-sig') as stream:run=json.load(stream)
p=run['risk_parameters'];deal=Deal(**run['deal']);engine=p.get('engine','gbm')
if engine=='gbm' and p.get('method')=='Manual assumptions' or 'engine' not in p:
    sample,_=simulate(deal,p['volatility'],p['drift'],p['correlation'],p['paths'],p['seed'],p['logistics_cv'])
else:
    data=json.loads(p['history_levels']);frame=pd.DataFrame(data['data'],columns=data['columns'])
    date_column=frame.columns[0];frame[date_column]=pd.to_datetime(frame[date_column]);frame=frame.set_index(date_column)
    sample,_=forecast_sample(frame,deal,engine,p['paths'],p['seed'],p['logistics_cv'],p.get('growth_policy','native'))
print(json.dumps(risk(sample['total_irr'],economics(deal)['total_irr'],p['confidence']),indent=2))
