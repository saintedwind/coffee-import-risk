"""Local append-only records, with digest verification. Not trusted timestamping."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def register(folder,payload):
    now=datetime.now(timezone.utc)
    target=pd.Timestamp(payload['target_month'])
    if target.to_period('M').end_time.date()<=now.date(): raise ValueError('Cannot register a forecast for a completed target month')
    item={'schema':'coffee-forecast-1','registered_at':now.isoformat(),'payload':payload}
    digest=hashlib.sha256(canonical(item)).hexdigest();item['record_id']=digest
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(digest+'.json')
    with path.open('xb') as stream:stream.write(canonical(item))
    return item

def verify(item):
    body={k:v for k,v in item.items() if k!='record_id'}
    if hashlib.sha256(canonical(body)).hexdigest()!=item.get('record_id'):raise ValueError('Forecast record digest mismatch')
    return item

def settle(folder,item,actual_loss,actual_metadata):
    import math
    verify(item)
    if not math.isfinite(actual_loss):raise ValueError('Finite actual result required')
    target=pd.Timestamp(item['payload']['target_month']).to_period('M')
    if target.end_time.date()>=datetime.now(timezone.utc).date():raise ValueError('Target month has not fully closed')
    if not actual_metadata.get('source') or not actual_metadata.get('retrieved_at'):raise ValueError('Actual result provenance required')
    forecasts=item['payload'].get('forecast',{})
    if 'var_irr' in forecasts:forecasts={'selected_engine':forecasts}
    assessment={name:{'breach':bool(actual_loss>metrics['var_irr']),'excess_over_var_irr':float(actual_loss-metrics['var_irr'])} for name,metrics in forecasts.items()}
    result={'assessment':assessment,'forecast_id':item['record_id'],'settled_at':datetime.now(timezone.utc).isoformat(),'actual_loss':actual_loss,'actual_metadata':actual_metadata}
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with (folder/(item['record_id']+'.settlement.json')).open('xb') as stream:stream.write(canonical(result))
    return result
