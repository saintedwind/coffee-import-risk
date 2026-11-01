"""Retrospective diagnostics. Attribution explains modeled changes, not causal effects."""
from dataclasses import replace
from itertools import permutations
import numpy as np
import pandas as pd
from .model import economics

def attribution(deal,factors):
    f=np.asarray(factors,float)
    if f.shape!=(3,): raise ValueError('Expected three factors')
    contributions=np.zeros(3)
    for order in permutations(range(3)):
        running=np.ones(3);before=economics(deal,running)['total_irr']
        for i in order:
            running[i]=f[i];after=economics(deal,running)['total_irr']
            contributions[i]+=(after-before)/6;before=after
    return dict(zip(('arabica','robusta','fx'),map(float,contributions)))

def explain_failures(monthly,deal,frame):
    rows=[]
    for record in frame.itertuples():
        if not record.breach: continue
        origin=pd.Timestamp(record.origin);target=pd.Timestamp(record.target)
        base=monthly.loc[origin].to_numpy()
        d=replace(deal,arabica_usd_kg=base[0],robusta_usd_kg=base[1],usd_irr=base[2])
        factors=monthly.loc[target].to_numpy()/base
        contributions=attribution(d,factors)
        rows.append({'method':record.method,'origin':record.origin,'target':record.target,
                     'realized_loss':record.realized_loss,'var':record.var_irr,'cvar':record.cvar_irr,
                     'excess_over_var':record.excess_over_var,**contributions,
                     'largest_positive_contributor':max(contributions,key=contributions.get)})
    return rows

def paired_loss_sensitivity(frame,baseline='gbm',repeats=1000,seed=81):
    if repeats<10: raise ValueError('Need at least 10 repeats')
    wide=frame.pivot(index='origin',columns='method',values='quantile_loss').sort_index()
    rng=np.random.default_rng(seed);results={}
    for name in wide:
        if name==baseline: continue
        delta=(wide[name]-wide[baseline]).dropna().to_numpy();n=len(delta)
        if n<2: continue
        # Two-origin blocks retain short-range dependence; ranges are exploratory.
        starts=rng.integers(0,n-1,size=(repeats,(n+1)//2))
        ids=(starts[...,None]+np.arange(2)).reshape(repeats,-1)[:,:n]
        means=delta[ids].mean(axis=1)
        results[name]={'mean_loss_difference':float(delta.mean()),'resampled_p025_p975':np.quantile(means,[.025,.975]).tolist(),
                       'origins':n,'interpretation':'Positive means worse than GBM. Exploratory block-resampling range, not independent holdout evidence.'}
    return results
