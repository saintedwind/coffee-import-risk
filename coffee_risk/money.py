"""Currency boundaries and explicit accounting explanations. Internal money is IRR."""
import numpy as np

def to_irr(value,unit):
    value=float(value)
    if not np.isfinite(value) or value<0: raise ValueError('Money must be finite and nonnegative')
    if unit not in ('IRR','toman'): raise ValueError('Unit must be IRR or toman')
    return value*(10 if unit=='toman' else 1)

def from_irr(value,unit):
    if unit not in ('IRR','toman'): raise ValueError('Unit must be IRR or toman')
    value=float(value)
    if not np.isfinite(value): raise ValueError('Money must be finite')
    return value/(10 if unit=='toman' else 1)

COMPONENTS=('purchase_irr','freight_irr','insurance_irr','duty_irr','local_irr','finance_irr','roasting_irr','packaging_irr','selling_irr')
def cost_breakdown(result,unit='toman'):
    return [{'component':key,'total':from_irr(result[key],unit),
             'per_sellable_kg':from_irr(result[key]/result['sellable_kg'],unit),'currency':unit}
            for key in COMPONENTS]

def required_price(cost_per_kg,margin,discount=0):
    if not np.isfinite([cost_per_kg,margin,discount]).all() or cost_per_kg<0 or not 0<=margin<1 or not 0<=discount<1:
        raise ValueError('Invalid cost, margin or discount')
    return cost_per_kg/((1-margin)*(1-discount))

def diagnostics(deal,result):
    warnings=[]
    foreign=deal.quantity_kg*(deal.arabica_weight*deal.arabica_usd_kg+(1-deal.arabica_weight)*deal.robusta_usd_kg)
    if deal.freight_usd>foreign*.25:
        warnings.append('Freight exceeds 25% of coffee invoice: check shipment size and whether freight is per shipment. Heuristic, not an error proof.')
    if result['local_irr']>result['purchase_irr']*.25:
        warnings.append('Local fixed fees exceed 25% of coffee value: check total/per-kg units. Heuristic only.')
    if result['margin']<0: warnings.append('Selected selling price is below modeled cost; no input has been adjusted to force a positive margin.')
    return warnings

def compare_market(cost_irr_kg,listed,unit,model_stage,quote_stage,channel,available,quality_match=False):
    if model_stage not in ('green','roasted') or quote_stage not in ('green','roasted') or channel not in ('retail','wholesale','supplier'):
        raise ValueError('Explicit product stage and channel required')
    if not isinstance(available,bool) or not isinstance(quality_match,bool):raise ValueError('Availability and quality match must be explicit booleans')
    price=to_irr(listed,unit)
    if price<=0: raise ValueError('Positive quote required')
    return {'listed_irr_kg':price,'model_cost_irr_kg':float(cost_irr_kg),'gap_pct':float((cost_irr_kg/price-1)*100),
            'comparable':model_stage==quote_stage and bool(quality_match) and bool(available) and channel=='supplier',
            'interpretation':'Cost vs listing is a scope diagnostic, not prediction accuracy or proof of achievable supplier price.'}
