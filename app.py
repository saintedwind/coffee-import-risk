"""Coffee import workbench. All defaults are illustrative."""
import json, os, hashlib
from dataclasses import asdict,replace
from datetime import datetime, timezone
from pathlib import Path
from coffee_risk.money import from_irr,to_irr,cost_breakdown,required_price,diagnostics
from coffee_risk.evidence import manifest_from_deal,validate_manifest,apply_manifest,store_document
from coffee_risk.alternatives import forecast_sample
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from coffee_risk.model import Deal, economics, blend, simulate, risk
from coffee_risk.data import fetch_coffee, fetch_fx, fetch_joint_history, fetch_coffee_history
from coffee_risk.history import validate_history, calibrate, backtest, summarize_backtest, COLS

load_dotenv()
if 'pending_deal' in st.session_state:
    pending=st.session_state.pop('pending_deal')
    for key in list(st.session_state):
        if key not in ('pending_manifest','deal_defaults'): del st.session_state[key]
    st.session_state['deal_defaults']=pending
if 'pending_manifest' in st.session_state:
    st.session_state['active_manifest']=st.session_state.pop('pending_manifest')
    st.session_state['evidence_docs']=st.session_state['active_manifest'].get('documents',[])
D=Deal(**st.session_state.get('deal_defaults',{}))
st.set_page_config(page_title="Coffee Risk | ریسک قهوه", page_icon="☕", layout="wide")
st.title("☕ Coffee import risk workbench")
st.caption("قیمت‌گذاری و ریسک واردات قهوه • Three-month planning • USD and Iranian rial")
st.warning("ILLUSTRATIVE defaults — replace with your contract and settlement inputs. No trained AI or live trading quotes are claimed.")
display_unit=st.sidebar.selectbox("Money input and display unit",['IRR','toman'],key='display_unit')
previous_unit=st.session_state.get('previous_display_unit',display_unit)
if previous_unit!=display_unit:
    pairs=[('manual_usd_irr','manual_usd_irr_toman'),('sale_IRR','sale_toman'),('local_IRR','local_toman'),('roast_cost_IRR','roast_cost_toman'),('pack_IRR','pack_toman'),('selling_IRR','selling_toman'),('listing_IRR','listing_toman')]
    for irr_key,toman_key in pairs:
        old_key=irr_key if previous_unit=='IRR' else toman_key
        new_key=irr_key if display_unit=='IRR' else toman_key
        if old_key in st.session_state:st.session_state[new_key]=from_irr(to_irr(st.session_state[old_key],previous_unit),display_unit)
st.session_state['previous_display_unit']=display_unit
unit_label='تومان' if display_unit=='toman' else 'ریال'
amount=lambda value: f"{from_irr(value,display_unit):,.0f} {unit_label}"
st.sidebar.caption("Internal calculation is IRR. 1 toman = 10 IRR. Total shipment and per-kg values are labelled separately.")
if st.sidebar.button("Load user FX: 271,000 toman/USD",key='user_fx_preset'):
    for unit in ('IRR','toman'):
        key='manual_usd_irr' if unit=='IRR' else 'manual_usd_irr_toman'
        st.session_state[key]=2710000. if unit=='IRR' else 271000.
    st.session_state['source_usd_irr']='User-reported 271,000 toman/USD; not verified executable quote'
    st.session_state['mode_usd_irr']='Illustrative / manual'
snapshot_path=Path(__file__).parent/'reports'/'2026-10-27-release'/'results.json'
if snapshot_path.exists() and st.sidebar.button("Load reviewed benchmark snapshot · 2026-10-27",key='load_reviewed_snapshot'):
    snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
    for key in COLS[:2]:
        st.session_state['manual_'+key]=float(snapshot['sources'][key]['value'])
        st.session_state['source_'+key]='FRED monthly benchmark snapshot; '+snapshot['sources'][key]['observation_date']
        st.session_state['mode_'+key]='Illustrative / manual'
        st.session_state['date_'+key]=datetime.fromisoformat(snapshot['sources'][key]['observation_date']).date()
    st.session_state['manual_usd_irr']=2710000.
    st.session_state['manual_usd_irr_toman']=271000.
    st.session_state['source_usd_irr']='User-reported FX scenario on 2026-10-27; not executable quote'
    st.session_state['mode_usd_irr']='Illustrative / manual'
    st.session_state['sale_IRR']=30000000.
    st.session_state['sale_toman']=3000000.
    st.sidebar.info('Dated monthly benchmark, current user FX scenario, other costs still illustrative. This does not fetch today’s prices.')
st.session_state.setdefault('quotes', {})
st.session_state.setdefault('series', {})
st.session_state.setdefault('fetch_errors', {})
tabs=st.tabs(["1 · Inputs & sources", "2 · Pricing", "3 · Risk & scenarios", "4 · History & validation", "5 · Audit & export", "6 · Shipment evidence"])

with tabs[0]:
    st.subheader("Market inputs")
    st.info("FRED/IMF coffee data are monthly averages. Frankfurter FX is a reference rate, not a verified Iranian free-market quote. Fetch does not silently overwrite your entries.")
    cols=st.columns(3)
    active={}
    audit={}
    for col,key,label,default in zip(cols,COLS,['Arabica · USD/kg','Robusta · USD/kg','USD/IRR · rial per dollar'],[D.arabica_usd_kg,D.robusta_usd_kg,D.usd_irr]):
        with col:
            st.markdown("**"+label+"**")
            if st.button("Fetch latest available",key='fetch_'+key):
                try:
                    frame,meta=fetch_fx() if key=='usd_irr' else fetch_coffee(key)
                    st.session_state.quotes[key]=meta
                    st.session_state.series[key]=frame
                    st.session_state.fetch_errors.pop(key,None)
                except Exception as exc:
                    st.session_state.fetch_errors[key]=str(exc)
            if key in st.session_state.fetch_errors:
                st.error("Fetch failed: "+st.session_state.fetch_errors[key]+". Previous successful data, if any, retain their original timestamp.")
            quote=st.session_state.quotes.get(key)
            if quote:
                st.json(quote,expanded=False)
                age=(pd.Timestamp.now(tz='UTC').date()-pd.Timestamp(quote['observation_date']).date()).days
                if age > (75 if key!='usd_irr' else 7):
                    st.warning(f"Stale observation: {age} days old.")
            mode=st.selectbox("Use value from",["Illustrative / manual","Fetched reference"],key='mode_'+key)
            entered_label=label if key!='usd_irr' else 'USD FX · '+unit_label+' per dollar'
            input_default=from_irr(default,display_unit) if key=='usd_irr' else default
            input_key='manual_'+key+('_toman' if key=='usd_irr' and display_unit=='toman' else '')
            manual=st.number_input(entered_label,min_value=.0001,value=float(input_default),format="%.4f",key=input_key)
            if key=='usd_irr': manual=to_irr(manual,display_unit)
            source=st.text_input("Manual source / quote reference",key='source_'+key)
            observed=st.date_input("Manual observation date",key='date_'+key)
            if mode=="Fetched reference":
                if quote:
                    active[key]=quote['value']
                    audit[key]={**quote,'active_mode':'provider'}
                else:
                    active[key]=None
                    st.error("Fetch a valid observation or choose manual input.")
            else:
                active[key]=manual
                audit[key]=dict(active_mode='manual' if source.strip() else 'illustrative',
                                source=source or 'Illustrative default / unverified input',
                                observation_date=str(observed),value=manual,
                                entered_at=datetime.now(timezone.utc).isoformat(),
                                original_provider=quote)
    st.caption('Money entries follow the selected unit; provider FX is normalized to IRR internally. Do not multiply by 10 yourself in toman mode.')
    st.subheader("Shipment, blend and contract")
    c1,c2,c3=st.columns(3)
    weight=c1.slider("Arabica weight %",0,100,int(D.arabica_weight*100),key='blend_weight')/100
    c2.metric("Robusta weight",f"{(1-weight)*100:.0f}%")
    sizing=c3.selectbox("Size shipment by",["Quantity (kg)","Coffee purchase value (USD)"],key="sizing")
    quantity=c1.number_input("Quantity · kg",min_value=1.,value=float(D.quantity_kg))
    budget=c2.number_input("Coffee purchase value · USD (excludes logistics)",min_value=1.,value=100000.)
    sale=to_irr(c3.number_input("Selling price before discount · "+unit_label+"/kg",min_value=1.,value=from_irr(D.sale_irr_kg,display_unit),key="sale_"+display_unit),display_unit)
    st.caption("Price inputs should include origin/quality premiums when using manual supplier quotes.")
    a_premium=c1.number_input("Arabica supplier premium · USD/kg",value=0.)
    r_premium=c2.number_input("Robusta supplier premium · USD/kg",value=0.)
    coffee_unfixed=c1.slider("Coffee price still unfixed %",0,100,int(D.coffee_unfixed*100))/100
    fx_unfixed=c2.slider("FX still unconverted / unhedged %",0,100,int(D.fx_unfixed*100))/100
    c3.metric("Horizon","3 months")
    st.caption("Set coffee unfixed to 0 for a fixed USD invoice. Set FX unfixed to 0 only when the modeled USD outflows are already converted or fully hedged.")
    st.subheader("Logistics and commercial assumptions")
    c1,c2,c3=st.columns(3)
    freight=c1.number_input("Freight and foreign fees · USD",min_value=0.,value=float(D.freight_usd))
    insurance=c2.number_input("Insurance % of goods + freight",0.,100.,D.insurance_rate*100)/100
    duty=c3.number_input("Duty % of CIF",0.,100.,D.duty_rate*100)/100
    local=to_irr(c1.number_input("Local fixed fees · "+unit_label+" / shipment",min_value=0.,value=from_irr(D.local_cost_irr,display_unit),key="local_"+display_unit),display_unit)
    finance=c2.number_input("Annual simple financing rate %",0.,500.,D.finance_rate*100)/100
    shrink=c3.number_input("Weight loss %",0.,99.,D.shrinkage*100)/100
    st.caption("Duty/tax defaults are illustrative, not Iranian legal rates. Enter recoverable VAT separately outside economic cost; model does not calculate VAT cash-flow timing.")

with tabs[0]:
    st.subheader("Product stage, processing and sales")
    stage=st.selectbox("Output product",['green','roasted'],index=0 if D.roast_yield==1 else 1,key='product_stage')
    input_stage=st.selectbox("Purchase price product stage",['green','roasted'],key='input_stage')
    pc1,pc2,pc3=st.columns(3)
    roast_yield=pc1.number_input("Roasting yield %",1.,100.,float(D.roast_yield*100 if D.roast_yield<1 else 84.),key='roast_yield')/100 if stage=='roasted' and input_stage=='green' else 1.
    roast_cost=to_irr(pc2.number_input("Roasting cost / input kg · "+unit_label,0.,value=from_irr(D.roast_cost_irr_input_kg,display_unit),key='roast_cost_'+display_unit),display_unit) if stage=='roasted' and input_stage=='green' else 0.
    if input_stage=='roasted' and stage=='green':
        st.error("Cannot turn purchased roasted coffee into green coffee.");st.stop()
    packaging=to_irr(pc3.number_input("Packaging / output kg · "+unit_label,0.,value=from_irr(D.packaging_irr_output_kg,display_unit),key='pack_'+display_unit),display_unit)
    selling_cost=to_irr(pc1.number_input("Distribution cost / output kg · "+unit_label,0.,value=from_irr(D.selling_cost_irr_output_kg,display_unit),key='selling_'+display_unit),display_unit)
    discount=pc2.number_input("Sales discount %",0.,99.,float(D.discount_rate*100),key='discount')/100
    sold=pc3.number_input("Sold share %",0.,100.,float(D.sold_fraction*100),key='sold')/100
    st.caption("Roast yield 84% is illustrative, not measured. Set from actual input/output weigh tickets. Unsold inventory is allocated at modeled cost; this is not a realized or collected profit statement.")

# Historical data can calibrate risk before the risk tab is rendered.
monthly=None
history_meta=None
with tabs[3]:
    st.subheader("Historical validation")
    st.write("Upload aligned observations: date, arabica_usd_kg, robusta_usd_kg, usd_irr. Daily data are averaged into calendar months; missing months are rejected.")
    uploaded=st.file_uploader("History CSV",type=['csv'])
    history_source=st.text_input("History source and FX market definition",placeholder="Supplier export / licensed feed; settlement or free-market FX")
    history_kind=st.selectbox("History classification",["Unverified user upload","Illustrative / synthetic","Provider-sourced, user verified"])
    history_mode=st.radio("Historical dataset",["Uploaded CSV","Fetched reference history","Coffee benchmarks only (FX fixed)"],horizontal=True,key="history_mode")
    years=st.selectbox("Years of reference history",[2,3,5,10],index=2)
    if st.button("Fetch coffee-only history (no FX feed)",key='fetch_coffee_only'):
        try:
            hist,meta=fetch_coffee_history(years)
            st.session_state['coffee_only_history']=(hist,meta)
        except Exception as exc:st.error("Coffee history fetch failed: "+str(exc))
    if history_mode=="Coffee benchmarks only (FX fixed)":
        saved=st.session_state.get('coffee_only_history')
        if saved:
            monthly,meta=saved
            history_meta=dict(source='FRED/IMF coffee only',classification='Actual monthly coffee; FX excluded, identity 1 is not a rate',providers=meta,fx_mode='excluded')
            st.line_chart(monthly.iloc[:,:2]/monthly.iloc[0,:2]*100)
            st.dataframe(monthly.iloc[:,:2].tail(6),width='stretch')
            st.warning("FX history is excluded. Set FX unfixed to 0 for operational forecasts. Retrospective tests here are USD-only. An assumed/current FX conversion is not historical settlement validation.")
        else:st.info("Fetch coffee-only history first.")
    if st.button("Fetch aligned coffee + reference FX history"):
        try:
            with st.spinner("Fetching actual provider history; no interpolation"):
                hist,meta=fetch_joint_history(years)
            st.session_state['fetched_history']=(hist,meta)
        except Exception as exc:
            st.error("History fetch failed: "+str(exc))
    if history_mode=="Fetched reference history":
        saved=st.session_state.get('fetched_history')
        if saved:
            monthly,meta=saved
            history_meta=dict(source='FRED/IMF + Frankfurter reference FX',classification='Provider retrieved; reference FX only',providers=meta)
            st.line_chart(monthly/monthly.iloc[0]*100)
            st.dataframe(monthly.tail(6),width="stretch")
            st.json(meta,expanded=False)
            st.download_button("Download aligned reference history",monthly.to_csv(),"reference_history.csv","text/csv")
        else:
            st.info("Fetch reference history first.")
    if uploaded and history_mode=="Uploaded CSV":
        try:
            raw=uploaded.getvalue()
            if len(raw)>5_000_000: raise ValueError("CSV limit: 5 MB")
            monthly=validate_history(pd.read_csv(uploaded))
            history_meta=dict(source=history_source or 'Unspecified user upload',classification=history_kind,
                              sha256=hashlib.sha256(raw).hexdigest())
            st.line_chart(monthly/monthly.iloc[0]*100)
            st.dataframe(monthly.tail(6),width="stretch")
            st.caption(f"{len(monthly)} aligned months. Last six available months displayed; dates may not be recent.")
        except Exception as exc:
            st.error(str(exc))
    if all(k in st.session_state.series for k in COLS[:2]):
        a=st.session_state.series[COLS[0]].rename(columns={'value':COLS[0]})
        r=st.session_state.series[COLS[1]].rename(columns={'value':COLS[1]})
        coffee=a.merge(r,on='date')
        st.write("Fetched coffee history — most recent six available months")
        st.dataframe(coffee.tail(6),width="stretch")
        st.download_button("Download coffee history; add matching FX history",coffee.to_csv(index=False),"coffee_history.csv","text/csv")
    st.info("Six monthly points are insufficient for reliable covariance or three-month backtesting. Calibration requires 13+ aligned months; backtesting requires 27+, and preferably many years. Reference FX history can be fetched automatically; it does not represent verified settlement FX.")

if any(v is None for v in active.values()):
    st.info("Complete the selected market inputs to calculate.")
    st.stop()
try:
    a=active[COLS[0]]+a_premium
    r=active[COLS[1]]+r_premium
    if min(a,r)<=0: raise ValueError("Supplier-adjusted coffee prices must be positive")
    if sizing=="Coffee purchase value (USD)":
        quantity=budget/(weight*a+(1-weight)*r)
    deal=Deal(quantity_kg=quantity,arabica_weight=weight,arabica_usd_kg=a,robusta_usd_kg=r,
              usd_irr=active['usd_irr'],freight_usd=freight,insurance_rate=insurance,duty_rate=duty,
              local_cost_irr=local,finance_rate=finance,shrinkage=shrink,sale_irr_kg=sale,
              coffee_unfixed=coffee_unfixed,fx_unfixed=fx_unfixed,
              roast_yield=roast_yield,roast_cost_irr_input_kg=roast_cost,packaging_irr_output_kg=packaging,
              selling_cost_irr_output_kg=selling_cost,discount_rate=discount,sold_fraction=sold)
    if input_stage=='roasted' and any(audit.get(key,{}).get('active_mode')=='provider' or 'FRED' in audit.get(key,{}).get('source','') for key in COLS[:2]):
        raise ValueError('FRED benchmarks are green coffee. Purchased roasted product requires actual manual roasted supplier prices, not green benchmark inputs.')
    base=economics(deal)
except ValueError as exc:
    st.error(str(exc)); st.stop()

with tabs[1]:
    st.subheader("Landed economics")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Coffee purchase · USD",f"{base['purchase_usd']:,.0f}")
    c2.metric("Cost per sellable kg",amount(base['cost_irr_kg']))
    c3.metric("Potential contribution · entire shipment",amount(base['profit_irr']))
    c4.metric("Gross contribution margin",f"{base['margin']:.1%}")
    shares=blend(deal)
    table=pd.DataFrame({'Coffee':['Arabica','Robusta'],'Weight share':[weight,1-weight],
                        'Value share':shares,'kg':[quantity*weight,quantity*(1-weight)]})
    st.dataframe(table,width="stretch",hide_index=True)
    st.plotly_chart(px.pie(table,names='Coffee',values='Value share',hole=.6,title='Purchase value share'),use_container_width=True)
    target=st.slider("Target margin % of revenue",0,80,20)/100
    st.metric("Required net selling price / sellable kg",amount(required_price(base['cost_irr_kg'],target)))
    st.metric("Required list price before discount / sellable kg",amount(required_price(base['cost_irr_kg'],target,discount)))
    with st.expander("این عدد چگونه محاسبه شد؟ / Cost explanation",expanded=True):
        st.dataframe(pd.DataFrame(cost_breakdown(base,display_unit)),hide_index=True,width='stretch')
        st.write(f"Imported {deal.quantity_kg:,.2f} kg → after transit loss {deal.quantity_kg*(1-deal.shrinkage):,.2f} kg → sellable {base['sellable_kg']:,.2f} kg.")
        st.write("Net required price = cost per sellable kg / (1 − target margin). List price also divides by (1 − discount).")
        st.write(f"Sold allocation: {base['sold_kg']:,.2f} kg; contribution on sold allocation: {amount(base['contribution_sold_irr'])}; unsold stock cost: {amount(base['inventory_cost_irr'])}.")
        for warning in diagnostics(deal,base):st.warning(warning)
    st.caption("Margin = profit / revenue; not markup. Revenue and sale price stay fixed across risk scenarios.")

with tabs[2]:
    st.subheader("Correlated Monte Carlo")
    engine=st.selectbox("Scenario engine",['gbm','historical','block','ewma_block','student_t'],key='scenario_engine')
    growth_policy=st.selectbox("Growth assumption for history-based engines",['native','zero_log'],key='growth_policy')
    st.caption("zero_log centers simulated terminal log factors in every engine; equal log-growth is not equal expected arithmetic growth. Every history-based forecast re-estimates parameters and ignores manual volatility/drift/correlation below. GBM with manual assumptions uses those inputs. No engine is automatically promoted as more accurate.")
    method=st.radio("Risk parameters",["Manual assumptions","Estimate volatility and correlation from uploaded history"],horizontal=True,key="risk_method")
    c1,c2,c3=st.columns(3)
    vol=np.array([c1.number_input("Arabica annual volatility %",0.,300.,30.),
                  c2.number_input("Robusta annual volatility %",0.,300.,35.),
                  c3.number_input("FX annual volatility %",0.,300.,40.)])/100
    drift=np.array([c1.number_input("Arabica annual expected return %",-90.,300.,0.),
                    c2.number_input("Robusta annual expected return %",-90.,300.,0.),
                    c3.number_input("FX annual expected return %",-90.,300.,0.)])/100
    ar=c1.slider("Correlation · Arabica / Robusta",-1.,1.,.65,.05)
    af=c2.slider("Correlation · Arabica / FX",-1.,1.,0.,.05)
    rf=c3.slider("Correlation · Robusta / FX",-1.,1.,0.,.05)
    corr=np.array([[1,ar,af],[ar,1,rf],[af,rf,1]])
    if method.startswith("Estimate"):
        try:
            if monthly is None: raise ValueError("Upload valid history first")
            vol,corr=calibrate(monthly)
            st.write("Estimated annual volatilities",dict(zip(COLS,vol)))
            st.dataframe(pd.DataFrame(corr,index=COLS,columns=COLS))
            st.caption("Historical volatility/correlation estimated; drift remains your explicit assumption. This is statistical calibration, not trained AI.")
        except ValueError as exc:
            st.error(str(exc)); st.stop()
    n=c1.select_slider("Simulation paths",[5000,20000,50000,100000],value=20000)
    confidence=c2.selectbox("VaR confidence",[.90,.95,.99],index=1)
    seed=int(c3.number_input("Random seed",0,999999,int(os.getenv('COFFEE_SEED','42'))))
    logistics_cv=st.slider("Logistics cost uncertainty · coefficient of variation %",0,100,15)/100
    try:
        if engine=='gbm' and method=='Manual assumptions':
            if growth_policy=='zero_log':
                raise ValueError('zero_log policy requires history-based parameters; select historical calibration')
            sample,factors=simulate(deal,vol,drift,corr,n,seed,logistics_cv)
        else:
            if monthly is None:raise ValueError('This engine requires valid, relevant three-factor history; no synthetic fallback')
            if history_meta and history_meta.get('fx_mode')=='excluded' and deal.fx_unfixed!=0:
                raise ValueError('Coffee-only history cannot model FX exposure: set FX unfixed to 0 or provide actual relevant FX history')
            sample,factors=forecast_sample(monthly,deal,engine,n,seed,logistics_cv,growth_policy)
        rr=risk(sample['total_irr'],base['total_irr'],confidence)
    except ValueError as exc:
        st.error(str(exc)); st.stop()
    c1,c2,c3=st.columns(3)
    c1.metric("Cost-overrun VaR · entire shipment",amount(rr['var_irr']))
    c2.metric("Cost-overrun CVaR · entire shipment",amount(rr['cvar_irr']))
    loss_prob=float(np.mean(sample['profit_irr']<0))
    c3.metric("Probability of negative margin",f"{loss_prob:.1%}")
    st.caption("Loss = future total cost minus today's modeled total cost. VaR may be negative. CVaR averages the worst tail. These are cost-overrun risks, not loss of inventory market value.")
    st.plotly_chart(px.histogram(x=sample['profit_irr']/(10 if display_unit=='toman' else 1),nbins=80,
                                labels={'x':'Potential shipment contribution · '+unit_label},title='Three-month profit distribution'),use_container_width=True)
    intervals=np.quantile(sample['cost_irr_kg'],[.05,.5,.95])
    st.write({name:amount(value) for name,value in zip(['5th percentile cost/kg','Median cost/kg','95th percentile cost/kg'],intervals)})
    st.metric(f"Selling price for {confidence:.0%} modeled cost coverage and target margin",
              amount(required_price(np.quantile(sample['cost_irr_kg'],confidence),target)))
    se=np.sqrt(loss_prob*(1-loss_prob)/n)
    st.caption(f"Monte Carlo sampling error for loss probability: approximately ±{1.96*se:.2%} (95%, normal approximation). This excludes parameter and model uncertainty.")
    # Independent batches expose simulation noise without claiming parameter confidence.
    batch_vars=[risk(x,base['total_irr'],confidence)['var_irr'] for x in np.array_split(sample['total_irr'],10)]
    st.caption(f"VaR across 10 batches: {amount(min(batch_vars))} to {amount(max(batch_vars))}; sampling stability only, not parameter confidence.")
    st.subheader("Explicit stress scenarios")
    edits=st.data_editor(pd.DataFrame({'Scenario':['Favorable','Base','Adverse'],
                                      'Arabica %':[-15.,0.,20.],'Robusta %':[-10.,0.,25.],
                                      'FX %':[-10.,0.,35.]}),hide_index=True,num_rows='dynamic')
    scenario_rows=[]
    for _,row in edits.iterrows():
        try:
            f=1+np.array([row['Arabica %'],row['Robusta %'],row['FX %']],float)/100
            result=economics(deal,f)
            scenario_rows.append({'Scenario':row['Scenario'],**{k:float(v) for k,v in result.items()}})
        except (ValueError,TypeError):
            st.error("Scenario changes must be finite and greater than -100%.")
    st.dataframe(pd.DataFrame(scenario_rows),width="stretch")
    grid=np.linspace(-.4,.6,11)
    margins=[[economics(deal,[1+p,1+p,1+fx])['margin'] for fx in grid] for p in grid]
    st.plotly_chart(px.imshow(margins,x=np.round(grid*100),y=np.round(grid*100),
                             labels={'x':'FX change %','y':'Both coffee prices change %','color':'Margin'},
                             color_continuous_scale='RdYlGn',title='Margin sensitivity'),use_container_width=True)
    st.warning("Model uncertainty: lognormal returns omit jumps, sanctions/payment failures and regime breaks. Logistics uncertainty is independent. Monthly averages smooth volatility; six-month samples cannot establish reliable tails.")

with tabs[3]:
    if st.button("Run rolling three-month backtest",key="backtest"):
        try:
            if monthly is None: raise ValueError("Upload valid history first")
            bt=backtest(monthly,replace(deal,fx_unfixed=0.) if history_meta and history_meta.get('fx_mode')=='excluded' else deal,confidence=confidence,seed=seed)
            st.caption('Backtest monetary unit: USD (FX excluded)' if history_meta and history_meta.get('fx_mode')=='excluded' else 'Backtest monetary unit: IRR from historical dataset')
            st.dataframe(bt,width="stretch")
            st.json(summarize_backtest(bt,confidence),expanded=True)
            st.caption("GBM vs observed historical three-month changes. Lower mean quantile loss is better. Rolling windows share observations; coverage intervals are descriptive. Historical tail samples are small.")
            hits=int(bt.breach.sum()); count=len(bt); p=hits/count; z=1.96
            center=(p+z*z/(2*count))/(1+z*z/count)
            half=z*np.sqrt(p*(1-p)/count+z*z/(4*count*count))/(1+z*z/count)
            st.write(f"Breaches: {hits}/{count} ({p:.1%}); nominal {(1-confidence):.1%}. Wilson 95% interval: {max(0,center-half):.1%}–{min(1,center+half):.1%}.")
            st.download_button("Download backtest",bt.to_csv(index=False),"backtest.csv","text/csv")
            st.warning("Retrospective test uses revised observations, not publication-time vintages. Rolling 24-month training, non-overlapping three-month targets, zero drift, fixed logistics. It validates market-cost risk only; it does not validate delivery or profit forecasts.")
        except ValueError as exc: st.error(str(exc))

with tabs[3]:
    if st.button("Compare alternative risk models",key="advanced_backtest"):
        try:
            if monthly is None: raise ValueError("Upload or fetch valid history first")
            from coffee_risk.alternatives import compare,comparison_summary,parameter_sensitivity
            from dataclasses import replace
            with st.spinner("Running fixed retrospective models"):
                comparison=compare(monthly,replace(deal,fx_unfixed=0.) if history_meta and history_meta.get('fx_mode')=='excluded' else deal,confidence=confidence,seed=seed,growth_policy=growth_policy)
                summary=comparison_summary(comparison)
                last=monthly.iloc[-1].to_numpy()
                historical_deal=replace(deal,arabica_usd_kg=last[0],robusta_usd_kg=last[1],usd_irr=last[2])
                uncertainty=parameter_sensitivity(monthly.tail(36),historical_deal,confidence,method=engine,growth_policy=growth_policy)
            st.dataframe(pd.DataFrame(summary).T,width="stretch")
            st.json(uncertainty)
            st.download_button("Download model comparison",comparison.to_csv(index=False),"model-comparison.csv","text/csv")
            st.caption('Comparison monetary unit: USD (FX excluded)' if history_meta and history_meta.get('fx_mode')=='excluded' else 'Comparison monetary unit: IRR')
            st.warning("Research comparison: fixed block length 3, EWMA decay 0.94, Student df 5. Student simple returns are conditioned positive; nominal moments change after conditioning. Bootstrap ranges are sensitivity diagnostics, not confidence intervals. This revised-history test is not independent prospective validation. Costs follow the retrospective unit label above; input assumptions remain explicit.")
        except ValueError as exc: st.error(str(exc))

with tabs[4]:
    st.subheader("Reproducible run")
    report=dict(version='1.1.0',display_unit=display_unit,product_stage=stage,purchase_stage=input_stage,generated_at=datetime.now(timezone.utc).isoformat(),
                deal=asdict(deal),sources=audit,history=history_meta,
                risk_parameters=dict(engine=engine,growth_policy=growth_policy,method=method,history_fx_mode=history_meta.get('fx_mode') if history_meta else None,volatility=vol.tolist(),drift=drift.tolist(),
                                     correlation=corr.tolist(),history_levels=json.dumps({'columns':['date']+list(monthly.columns),'data':[[idx.isoformat()]+[float(v) for v in row] for idx,row in monthly.iterrows()]},allow_nan=False) if monthly is not None else None,paths=n,seed=seed,confidence=confidence,
                                     logistics_cv=logistics_cv,target_margin=target),
                baseline={k:float(v) for k,v in base.items()},risk=rr,
                loss_probability=loss_prob,scenarios=scenario_rows,evidence_manifest=st.session_state.get('active_manifest'),
                caveat='Statistical scenario engine; no trained AI. Defaults are illustrative.')
    st.json(report,expanded=False)
    st.download_button("Download full audit JSON",json.dumps(report,indent=2,ensure_ascii=False),
                       "coffee-risk-run.json","application/json")
    result_frame=pd.DataFrame({'arabica_factor':factors[:,0],'robusta_factor':factors[:,1],
                               'fx_factor':factors[:,2],'total_cost_irr':sample['total_irr'],
                               'profit_irr':sample['profit_irr'],'margin':sample['margin']})
    st.download_button("Download simulation CSV",result_frame.to_csv(index=False),"simulation.csv","text/csv")
    st.markdown("Sources: [FRED Arabica](https://fred.stlouisfed.org/series/PCOFFOTMUSDM) · [FRED Robusta](https://fred.stlouisfed.org/series/PCOFFROBUSDM) · [Frankfurter documentation](https://frankfurter.dev/)")
    st.write("Automatic assistance retrieves and validates data, estimates risk parameters and computes scenarios. Contract terms, settlement FX, fees and selling price require your business inputs.")



with tabs[1]:
    st.subheader("Market listing comparison")
    st.caption("Enter a dated listing for the same product and channel. A retail listing is not an executed supplier quote. No automatic price fitting occurs.")
    q1,q2,q3=st.columns(3)
    listing=q1.number_input("Listing per kg · "+unit_label,min_value=1.,value=from_irr(30000000.,display_unit),key='listing_'+display_unit)
    listing_stage=q2.selectbox("Listing product stage",['green','roasted'],key='listing_stage')
    listing_channel=q3.selectbox("Listing channel",['retail','wholesale','supplier'],key='listing_channel')
    listing_source=q1.text_input("Listing URL or quote document",key='listing_source')
    listing_date=q2.date_input("Listing observation date",key='listing_date')
    listing_available=q3.checkbox("Listing currently available",key='listing_available')
    quality_match=q3.checkbox("Origin, grade and contract conditions match",key='quality_match')
    if listing_source:
        from coffee_risk.money import compare_market
        comparison=compare_market(base['cost_irr_kg'],listing,display_unit,stage,listing_stage,listing_channel,listing_available,quality_match)
        st.json({**comparison,'source':listing_source,'observed_date':str(listing_date)})
        if not comparison['comparable']: st.warning("Scope mismatch or unverified availability: this is a price-gap diagnostic, not validation against a real purchase.")

with tabs[5]:
    st.subheader("Private shipment evidence")
    st.info("Files remain in this project's private/ folder and are excluded from Git. Documents are not parsed or automatically treated as verified. Enter checked values and link the correct document ID. No invoices have been supplied for this demonstration.")
    evidence_file=st.file_uploader("Attach invoice / payment / transport / weigh ticket",type=['pdf','png','jpg','jpeg','xlsx','csv','txt'],key='evidence_file')
    if evidence_file and st.button("Store private evidence",key='store_evidence'):
        try:
            doc=store_document(Path(__file__).parent/'private'/'documents',evidence_file.name,evidence_file.getvalue())
            docs=st.session_state.setdefault('evidence_docs',[])
            if doc['document_id'] not in {d['document_id'] for d in docs}:docs.append(doc)
        except ValueError as exc:st.error(str(exc))
    documents=st.session_state.get('evidence_docs',[])
    if documents:st.dataframe(pd.DataFrame(documents),hide_index=True)
    source_map={}
    prior=st.session_state.get('active_manifest',{})
    for row in prior.get('fields',[]):
        if row.get('value')==asdict(deal).get(row['field']):source_map[row['field']]=row
    for key in COLS:
        if key not in source_map:source_map[key]={'status':'user_reported' if audit.get(key,{}).get('active_mode')=='manual' else 'public_listing' if audit.get(key,{}).get('active_mode')=='provider' else 'assumption','source':audit.get(key,{}).get('source','Unverified input'),'observed_date':audit.get(key,{}).get('observation_date',str(datetime.now().date()))}
    generated=manifest_from_deal(deal,source_map,documents)
    edited=st.data_editor(pd.DataFrame(generated['fields']),hide_index=True,key='evidence_editor',disabled=['field','value','unit'])
    if st.button("Validate and save manifest privately",key='save_manifest'):
        try:
            rows=json.loads(edited.to_json(orient='records'))
            manifest=validate_manifest({**generated,'fields':rows})
            destination=Path(__file__).parent/'private'/'manifests';destination.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
            (destination/(digest+'.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            st.session_state['active_manifest']=manifest
            st.success('Manifest stored locally. Linked documents establish traceability, not independent verification.')
        except (ValueError,TypeError) as exc:st.error(str(exc))
    st.download_button("Download editable evidence manifest",json.dumps(generated,ensure_ascii=False,indent=2),'shipment-evidence.json','application/json')
    imported=st.file_uploader("Load completed evidence manifest",type=['json'],key='manifest_import')
    if imported and st.button("Apply manifest values to shipment",key='apply_manifest'):
        try:
            if len(imported.getvalue())>200000:raise ValueError('Manifest limit 200 KB')
            manifest=validate_manifest(json.loads(imported.getvalue()))
            imported_deal=apply_manifest(manifest)
            st.session_state['pending_deal']=asdict(imported_deal)
            st.session_state['pending_manifest']=manifest
            st.rerun()
        except (ValueError,KeyError,TypeError) as exc:st.error(str(exc))
    st.caption("For actual reconciliation use measured final weights, paid FX and invoices. Cost allocations on sold stock are provisional, not proof of cash collection or audited accounts.")

with tabs[4]:
    st.subheader("Register a forecast before the outcome")
    st.caption("Local digest-checked records cannot be overwritten through this workflow. They are not trusted timestamps or externally certified immutability. No future performance claim is possible before the target closes.")
    if st.button("Register current forecast locally",key='register_forecast'):
        try:
            from coffee_risk.registry import register
            target_month=(pd.Timestamp.now().to_period('M')+deal.months).to_timestamp()
            payload={'target_month':str(target_month.date()),'registered_from':'current UI inputs',
                     'cost_unit':'IRR','report':report,'forecast':{'var_irr':rr['var_irr'],'cvar_irr':rr['cvar_irr']},
                     'status':'unsettled; no observed target result yet'}
            item=register(Path(__file__).parent/'private'/'forecast-registry',payload)
            st.success('Forecast recorded: '+item['record_id'])
            st.json(item)
        except ValueError as exc:st.error(str(exc))

    registry_folder=Path(__file__).parent/'private'/'forecast-registry'
    records=sorted(path.name for path in registry_folder.glob('*.json') if not path.name.endswith('.settlement.json')) if registry_folder.exists() else []
    if records:
        with st.expander("Settle a registered forecast after its target month"):
            chosen=st.selectbox("Local forecast record",records,key='settlement_record')
            observed_loss=st.number_input("Observed total cost overrun · "+unit_label,value=0.,key='settlement_loss_'+display_unit)
            outcome_source=st.text_input("Actual outcome source / linked document ID",key='settlement_source')
            st.caption("Enter increase in TOTAL cost versus that record's baseline, not unit selling price. Negative overrun is allowed. The target month must be closed. This manual entry is not independently audited.")
            if st.button("Record observed outcome",key='settle_forecast'):
                try:
                    from coffee_risk.registry import settle
                    item=json.loads((registry_folder/chosen).read_text(encoding='utf-8'))
                    signed_loss=float(observed_loss)*(10 if display_unit=='toman' else 1)
                    result=settle(registry_folder,item,signed_loss,{'source':outcome_source,'retrieved_at':datetime.now(timezone.utc).isoformat(),'classification':'User-reported outcome; not independently verified'})
                    st.json(result)
                except (ValueError,FileExistsError) as exc:st.error(str(exc))
