import sys,json,hashlib,urllib.request
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from coffee_risk import data
from coffee_risk.history import backtest,summarize_backtest,calibrate
from coffee_risk.model import Deal

def main():
    import argparse
    parser=argparse.ArgumentParser(description='Fetch real reference data and compare retrospective risk models.')
    parser.add_argument('--output',type=Path,default=Path('reports/live-validation'))
    parser.add_argument('--direct',action='store_true',help='Explicitly bypass environment proxies for public provider requests.')
    parser.add_argument('--years',type=int,choices=(2,3,5,10),default=10)
    parser.add_argument('--coffee-usd',action='store_true',help='Evaluate actual coffee benchmarks in USD only; excludes FX risk entirely.')
    parser.add_argument('--advanced',action='store_true',help='Run fixed alternative models and parameter-resampling sensitivity.')
    args=parser.parse_args()
    out=args.output; out.mkdir(parents=True,exist_ok=True)
    receipts=[]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})) if args.direct else urllib.request.build_opener()
    def recorded(url):
        req=urllib.request.Request(url,headers={'User-Agent':'CoffeeRisk/1.1'})
        with opener.open(req,timeout=45) as response: raw=response.read(10000001)
        if len(raw)>10000000: raise ValueError('Provider response too large')
        receipts.append({'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        return raw
    data.read_url=recorded
    report={'started_at':datetime.now(timezone.utc).isoformat(),'status':'failed','receipts':receipts,'evaluations':{}}
    try:
        deal=Deal()
        unit='IRR'
        if args.coffee_usd:
            import pandas as pd
            from coffee_risk.history import validate_history
            frames=[]; meta={}
            for key in data.SERIES:
                frame,meta[key]=data.fetch_coffee(key)
                frames.append(frame.rename(columns={'value':key}).set_index('date'))
            combined=frames[0].join(frames[1],how='inner').tail(args.years*12)
            combined['usd_irr']=1.0  # Unit conversion identity: costs are USD, not a fabricated FX series.
            monthly=validate_history(combined.reset_index())
            deal=Deal(usd_irr=1.,fx_unfixed=0.,freight_usd=0.,insurance_rate=0.,duty_rate=0.,local_cost_irr=0.,finance_rate=0.,shrinkage=0.,sale_irr_kg=1.)
            unit='USD'
        else:
            monthly,meta=data.fetch_joint_history(args.years)
        report['cost_unit']=unit
        report['scope']='Coffee purchase benchmark only; 20,000 kg, 60/40 blend; no FX or logistics' if args.coffee_usd else 'Reference market-cost risk with illustrative deal terms'
        report.update(months=len(monthly),first=str(monthly.index[0].date()),last=str(monthly.index[-1].date()),sources=meta)
        report['annual_volatility']=calibrate(monthly)[0].tolist()
        for train in (24,36):
            for confidence in (.90,.95,.99):
                bt=backtest(monthly,deal,train=train,confidence=confidence,seed=42)
                key=f'train{train}_q{confidence}'
                summary=summarize_backtest(bt,confidence)
                if args.coffee_usd:
                    for stats in summary['models'].values(): stats['mean_quantile_loss_usd']=stats.pop('mean_quantile_loss_irr')
                    bt=bt.rename(columns={c:c.replace('_irr','_usd') for c in bt.columns})
                report['evaluations'][key]=summary
                bt.to_csv(out/(key+'.csv'),index=False)
        if args.advanced:
            from coffee_risk.alternatives import compare,comparison_summary,parameter_sensitivity
            from dataclasses import replace
            report['protocol']={'block_months':3,'ewma_decay':.94,'student_df':5,'paths':5000,'seed':42,
                'selection':'No model selection or hyperparameter tuning performed.',
                'evaluation':'Retrospective chronological partitions; dates overlap previous analysis. Not an untouched holdout or prospective test.'}
            report['advanced']={}
            split=monthly.index[int(len(monthly)*.7)]
            report['protocol']['late_partition_start']=str(split.date())
            for train in (24,36,60):
                for q in (.90,.95,.99):
                    frame=compare(monthly,deal,train=train,confidence=q)
                    key=f'train{train}_q{q}'
                    report['advanced'][key]={'all':comparison_summary(frame),
                        'early':comparison_summary(frame[frame.target<str(split.date())]),
                        'late':comparison_summary(frame[frame.target>=str(split.date())])}
                    if args.coffee_usd: frame=frame.rename(columns={c:c.replace('_irr','_usd') for c in frame.columns})
                    frame.to_csv(out/(key+'_advanced.csv'),index=False)
            latest=monthly.iloc[-1].to_numpy()
            current=replace(deal,arabica_usd_kg=latest[0],robusta_usd_kg=latest[1],usd_irr=latest[2])
            report['parameter_sensitivity']=parameter_sensitivity(monthly.tail(36),current)
        report['status']='success'
        report['caveats']=['USD-only mode omits FX risk; reference mode is not Iranian settlement FX.','Revised monthly averages, not publication-time vintages.','Deal quantity, fees and selling price are illustrative, not verified transactions.','Rolling training windows share observations; Wilson intervals are descriptive.','Historical baseline uses overlapping training changes; small tail samples limit conclusions.','No raw provider history redistributed.']
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
if __name__=='__main__': main()
