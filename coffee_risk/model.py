from dataclasses import dataclass, asdict
import numpy as np

@dataclass(frozen=True)
class Deal:
    quantity_kg: float = 20000
    arabica_weight: float = .6
    arabica_usd_kg: float = 6.
    robusta_usd_kg: float = 4.
    usd_irr: float = 800000.
    freight_usd: float = 4000.
    insurance_rate: float = .01
    duty_rate: float = .05
    local_cost_irr: float = 200000000.
    finance_rate: float = .24
    shrinkage: float = .02
    sale_irr_kg: float = 6000000.
    months: int = 3
    coffee_unfixed: float = 1.
    fx_unfixed: float = 1.

    def validate(self):
        if not all(np.isfinite(v) for v in asdict(self).values()):
            raise ValueError('All inputs must be finite')
        for k in ('quantity_kg','arabica_usd_kg','robusta_usd_kg','usd_irr','sale_irr_kg'):
            if getattr(self,k) <= 0: raise ValueError(k+' must be positive')
        for k in ('arabica_weight','insurance_rate','duty_rate','coffee_unfixed','fx_unfixed'):
            if not 0 <= getattr(self,k) <= 1: raise ValueError(k+' must be in [0,1]')
        if not 0 <= self.shrinkage < 1 or not 1 <= self.months <= 24:
            raise ValueError('Invalid shrinkage or horizon')
        if min(self.freight_usd,self.local_cost_irr,self.finance_rate) < 0:
            raise ValueError('Costs cannot be negative')

def economics(d, factors=(1.,1.,1.), logistics_factor=1.):
    d.validate()
    f = np.asarray(factors,float)
    if f.ndim == 0 or f.shape[-1] != 3 or not np.isfinite(f).all() or np.any(f<=0):
        raise ValueError('Three positive factors required')
    if not np.isfinite(logistics_factor).all() or np.any(np.asarray(logistics_factor)<0):
        raise ValueError('Invalid logistics multiplier')
    a = d.arabica_usd_kg*(1+d.coffee_unfixed*(f[...,0]-1))
    r = d.robusta_usd_kg*(1+d.coffee_unfixed*(f[...,1]-1))
    fx = d.usd_irr*(1+d.fx_unfixed*(f[...,2]-1))
    purchase = d.quantity_kg*(d.arabica_weight*a+(1-d.arabica_weight)*r)
    cif = (purchase+d.freight_usd*logistics_factor)*(1+d.insurance_rate)
    landed = cif*fx*(1+d.duty_rate)+d.local_cost_irr*logistics_factor
    finance = landed*d.finance_rate*d.months/12
    total = landed+finance
    sellable = d.quantity_kg*(1-d.shrinkage)
    revenue = sellable*d.sale_irr_kg
    return dict(purchase_usd=purchase,total_irr=total,finance_irr=finance,
                cost_irr_kg=total/sellable,profit_irr=revenue-total,
                margin=(revenue-total)/revenue,revenue_irr=revenue)

def blend(d):
    d.validate()
    v=np.array([d.arabica_weight*d.arabica_usd_kg,(1-d.arabica_weight)*d.robusta_usd_kg])
    return v/v.sum()

def validate_correlation(corr):
    c=np.asarray(corr,float)
    if c.shape!=(3,3) or not np.isfinite(c).all(): raise ValueError('Expected finite 3x3 matrix')
    if not np.allclose(c,c.T) or not np.allclose(np.diag(c),1) or np.any(abs(c)>1):
        raise ValueError('Correlation must be symmetric with unit diagonal')
    if np.linalg.eigvalsh(c).min() < -1e-10: raise ValueError('Correlation is not positive semidefinite')
    return c

def simulate(d,volatility,drift,corr,n=20000,seed=42,logistics_cv=0.):
    d.validate()
    vol,mu=np.asarray(volatility,float),np.asarray(drift,float)
    if vol.shape!=(3,) or mu.shape!=(3,) or not np.isfinite([vol,mu]).all():
        raise ValueError('Three finite annual volatility and drift inputs required')
    if np.any(vol<0) or not 100<=n<=200000 or not 0<=logistics_cv<=2:
        raise ValueError('Invalid volatility, sample count or logistics uncertainty')
    c=validate_correlation(corr)
    rng=np.random.default_rng(seed)
    eig,basis=np.linalg.eigh(c)
    z=rng.standard_normal((n,3))@(basis*np.sqrt(np.maximum(eig,0))).T
    t=d.months/12
    factors=np.exp((mu-vol**2/2)*t+vol*np.sqrt(t)*z)
    s=np.sqrt(np.log1p(logistics_cv**2))
    logistics=np.exp(-s*s/2+s*rng.standard_normal(n))
    return economics(d,factors,logistics),factors

def risk(costs,baseline,confidence=.95):
    x=np.asarray(costs,float)-baseline
    if x.ndim!=1 or not len(x) or not np.isfinite(x).all() or not .5<confidence<1:
        raise ValueError('Invalid sample or confidence')
    var=float(np.quantile(x,confidence))
    mass=(1-confidence)*len(x)
    ordered=np.sort(x)[::-1]
    full=int(np.floor(mass))
    tail=ordered[:full].sum()+(mass-full)*ordered[full]
    return dict(var_irr=var,cvar_irr=float(tail/mass))

