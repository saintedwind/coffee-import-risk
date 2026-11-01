"""Explicit monthly scenario alternatives; no automatic model selection."""
import numpy as np
import pandas as pd
from dataclasses import replace
from .model import economics, risk, simulate
from .history import calibrate

METHODS=('gbm','block','ewma_block','student_t')

def returns_of(monthly):
    x=monthly.to_numpy(dtype=float)
    if x.ndim!=2 or x.shape[1]!=3 or len(x)<13 or not np.isfinite(x).all() or (x<=0).any():
        raise ValueError('Need at least 13 finite positive three-factor monthly levels')
    return np.diff(np.log(x),axis=0)

def block_draw(rows,n,horizon,rng,block=3):
    if not isinstance(block,int) or not 1<=block<=len(rows): raise ValueError('Invalid block length')
    starts=rng.integers(0,len(rows)-block+1,size=(n,(horizon+block-1)//block))
    indices=(starts[...,None]+np.arange(block)).reshape(n,-1)[:,:horizon]
    return rows[indices]

def ewma_residuals(ret,decay=.94):
    if not 0<decay<1: raise ValueError('EWMA decay must be in (0,1)')
    # Warm-up uses only the first six returns; subsequent residuals use lagged scale.
    variance=np.mean(ret[:6]**2,axis=0)
    residual=[]
    for row in ret[6:]:
        scale=np.sqrt(variance)
        residual.append(np.divide(row,scale,out=np.zeros(3),where=scale>1e-12))
        variance=decay*variance+(1-decay)*row**2
    return np.asarray(residual),np.sqrt(variance)

def forecast(monthly,deal,method,n=5000,seed=42,block=3,decay=.94,df=5,growth_policy='native',return_factors=False):
    if growth_policy not in ('native','zero_log'): raise ValueError('Invalid growth policy')
    if method not in (*METHODS,'historical'): raise ValueError('Unknown method')
    if not isinstance(n,int) or not 100<=n<=200000: raise ValueError('Invalid sample count')
    deal.validate(); ret=returns_of(monthly); rng=np.random.default_rng(seed)
    if method=='gbm':
        vol,corr=calibrate(monthly)
        terminal=simulate(deal,vol,[0.]*3,corr,n=n,seed=seed)[1]
    elif method=='historical':
        if deal.months!=3: raise ValueError('Historical method requires three-month horizon')
        observed=(monthly/monthly.shift(3)).dropna().to_numpy()
        terminal=observed[rng.integers(0,len(observed),n)]
    elif method=='block':
        paths=block_draw(ret,n,deal.months,rng,block)
        terminal=np.exp(paths.sum(axis=1))
    elif method=='ewma_block':
        residual,scale=ewma_residuals(ret,decay)
        paths=block_draw(residual,n,deal.months,rng,block)*scale
        terminal=np.exp(paths.sum(axis=1))
    else:
        if not np.isfinite(df) or df<=2: raise ValueError('Student degrees of freedom must exceed 2')
        # Student shocks in SIMPLE returns, conditioned on all monthly gross returns > 0.
        # This avoids the undefined exponential moment of log-Student-t returns.
        simple=np.expm1(ret)
        covariance=np.cov(simple,rowvar=False,ddof=1)
        eig,basis=np.linalg.eigh(covariance)
        root=basis*np.sqrt(np.maximum(eig,0))
        gross=np.empty((n*deal.months,3)); pending=np.arange(len(gross))
        for attempt in range(100):
            z=rng.standard_normal((len(pending),3))@root.T
            shocks=z*np.sqrt((df-2)/rng.chisquare(df,len(pending)))[:,None]
            accepted=(shocks>-1).all(axis=1)
            gross[pending[accepted]]=1+shocks[accepted]
            pending=pending[~accepted]
            if not len(pending): break
        if len(pending): raise ValueError('Student positive-return conditioning did not converge')
        terminal=gross.reshape(n,deal.months,3).prod(axis=1)
    if growth_policy=='zero_log':
        terminal=np.exp(np.log(terminal)-np.log(terminal).mean(axis=0))
    if return_factors: return terminal
    return economics(deal,terminal)['total_irr']

def compare(monthly,deal,train=24,confidence=.95,seed=42,n=5000,block=3,decay=.94,df=5,growth_policy='native'):
    if deal.months!=3 or not isinstance(train,int) or train<13 or len(monthly)<train+3:
        raise ValueError('Need three-month deal and sufficient training history')
    if not .5<confidence<1: raise ValueError('Invalid confidence')
    rows=[]
    for end in range(train-1,len(monthly)-3,3):
        window=monthly.iloc[end-train+1:end+1]; base=monthly.iloc[end].to_numpy()
        d=replace(deal,arabica_usd_kg=base[0],robusta_usd_kg=base[1],usd_irr=base[2])
        baseline=economics(d)['total_irr']
        actual=float(economics(d,monthly.iloc[end+3].to_numpy()/base)['total_irr']-baseline)
        for method in (*METHODS,'historical'):
            costs=(economics(d,(window/window.shift(3)).dropna().to_numpy())['total_irr'] if method=='historical' and growth_policy=='native'
                   else forecast(window,d,method,n,seed+end,block,decay,df,growth_policy))
            metrics=risk(costs,baseline,confidence); error=actual-metrics['var_irr']
            rows.append(dict(origin=str(window.index[-1].date()),target=str(monthly.index[end+3].date()),
                             method=method,realized_loss=actual,**metrics,breach=bool(error>0),
                             quantile_loss=float((confidence-(error<0))*error),
                             excess_over_var=max(0.,float(error)),
                             loss_minus_cvar=float(actual-metrics['cvar_irr']),growth_policy=growth_policy))
    return pd.DataFrame(rows)

def comparison_summary(frame):
    result={}
    for name,group in frame.groupby('method'):
        hit=group.breach.to_numpy(dtype=bool); consecutive=int(np.sum(hit[1:]&hit[:-1]))
        result[name]={'origins':len(group),'breaches':int(hit.sum()),'breach_rate':float(hit.mean()),
                      'consecutive_breach_pairs':consecutive,'mean_quantile_loss':float(group.quantile_loss.mean())}
    return result

def parameter_sensitivity(monthly,deal,confidence=.95,repeats=40,n=2000,seed=912,method='ewma_block',growth_policy='native'):
    if not 2<=repeats<=200: raise ValueError('Invalid bootstrap repeat count')
    ret=returns_of(monthly); rng=np.random.default_rng(seed); values=[]
    baseline=economics(deal)['total_irr']
    for i in range(repeats):
        sampled=block_draw(ret,1,len(ret),rng)[0]
        # Artificial histories are labelled bootstrap parameter perturbations, never market observations.
        levels=np.vstack([np.ones(3),np.exp(np.cumsum(sampled,axis=0))])
        costs=forecast(pd.DataFrame(levels),deal,method,n,seed+i,growth_policy=growth_policy)
        values.append(risk(costs,baseline,confidence)['var_irr'])
    return {'method':method,'growth_policy':growth_policy,'bootstrap_repeats':repeats,'paths_per_repeat':n,'var_p05_p50_p95':np.quantile(values,[.05,.5,.95]).tolist(),
            'interpretation':'Parameter-resampling sensitivity, NOT a calibrated confidence interval; not fresh observed data.'}


def forecast_sample(monthly,deal,method,n=20000,seed=42,logistics_cv=0.,growth_policy='native'):
    if not np.isfinite(logistics_cv) or not 0<=logistics_cv<=2: raise ValueError('Invalid logistics CV')
    factors=forecast(monthly,deal,method,n,seed,growth_policy=growth_policy,return_factors=True)
    # Separate reproducible RNG stream for identical logistics assumptions in each method.
    rng=np.random.default_rng(np.random.SeedSequence([seed,719]))
    sigma=np.sqrt(np.log1p(logistics_cv**2))
    logistics=np.exp(-sigma*sigma/2+sigma*rng.standard_normal(n))
    return economics(deal,factors,logistics),factors
