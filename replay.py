"""Recompute a downloaded audit JSON without Streamlit."""
import json, sys
from coffee_risk.model import Deal, economics, simulate, risk
with open(sys.argv[1],encoding='utf-8-sig') as f: run=json.load(f)
p=run['risk_parameters']
deal=Deal(**run['deal'])
sample,_=simulate(deal,p['volatility'],p['drift'],p['correlation'],
                  p['paths'],p['seed'],p['logistics_cv'])
print(json.dumps(risk(sample['total_irr'],economics(deal)['total_irr'],p['confidence']),indent=2))

