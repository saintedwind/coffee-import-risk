"""Coffee import workbench. All defaults are illustrative."""
import json, os, hashlib
from dataclasses import asdict
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from coffee_risk.model import Deal, economics, blend, simulate, risk
from coffee_risk.data import fetch_coffee, fetch_fx, fetch_joint_history
from coffee_risk.history import validate_history, calibrate, backtest, COLS

load_dotenv()
st.set_page_config(page_title="Coffee Risk | ریسک قهوه", page_icon="☕", layout="wide")
st.title("☕ Coffee import risk workbench")
st.caption("قیمت‌گذاری و ریسک واردات قهوه • Three-month planning • USD and Iranian rial")
st.warning("ILLUSTRATIVE defaults — replace with your contract and settlement inputs. No trained AI or live trading quotes are claimed.")
st.session_state.setdefault('quotes', {})
st.session_state.setdefault('series', {})
st.session_state.setdefault('fetch_errors', {})
tabs=st.tabs(["1 · Inputs & sources", "2 · Pricing", "3 · Risk & scenarios", "4 · History & validation", "5 · Audit & export"])

with tabs[0]:
    st.subheader("Market inputs")
    st.info("FRED/IMF coffee data are monthly averages. Frankfurter FX is a reference rate, not a verified Iranian free-market quote. Fetch does not silently overwrite your entries.")
    cols=st.columns(3)
    active={}
    audit={}
    for col,key,label,default in zip(cols,COLS,['Arabica · USD/kg','Robusta · USD/kg','USD/IRR · rial per dollar'],[6.,4.,800000.]):
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
            manual=st.number_input(label,min_value=.0001,value=default,format="%.4f",key='manual_'+key)
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
    st.caption("All FX values use IRR. If your quote is in toman, multiply by 10 before entry.")
    st.subheader("Shipment, blend and contract")
    c1,c2,c3=st.columns(3)
    weight=c1.slider("Arabica weight %",0,100,60,key='blend_weight')/100
    c2.metric("Robusta weight",f"{(1-weight)*100:.0f}%")
    sizing=c3.selectbox("Size shipment by",["Quantity (kg)","Coffee purchase value (USD)"],key="sizing")
    quantity=c1.number_input("Quantity · kg",min_value=1.,value=20000.)
    budget=c2.number_input("Coffee purchase value · USD (excludes logistics)",min_value=1.,value=100000.)
    sale=c3.number_input("Net selling price · IRR/kg",min_value=1.,value=6000000.)
    st.caption("Price inputs should include origin/quality premiums when using manual supplier quotes.")
    a_premium=c1.number_input("Arabica supplier premium · USD/kg",value=0.)
    r_premium=c2.number_input("Robusta supplier premium · USD/kg",value=0.)
    coffee_unfixed=c1.slider("Coffee price still unfixed %",0,100,100)/100
    fx_unfixed=c2.slider("FX still unconverted / unhedged %",0,100,100)/100
    c3.metric("Horizon","3 months")
    st.caption("Set coffee unfixed to 0 for a fixed USD invoice. Set FX unfixed to 0 only when the modeled USD outflows are already converted or fully hedged.")
    st.subheader("Logistics and commercial assumptions")
    c1,c2,c3=st.columns(3)
    freight=c1.number_input("Freight and foreign fees · USD",min_value=0.,value=4000.)
    insurance=c2.number_input("Insurance % of goods + freight",0.,100.,1.)/100
    duty=c3.number_input("Duty % of CIF",0.,100.,5.)/100
    local=c1.number_input("Local fees / storage / nonrecoverable tax · IRR",min_value=0.,value=200000000.)
    finance=c2.number_input("Annual simple financing rate %",0.,500.,24.)/100
    shrink=c3.number_input("Weight loss %",0.,99.,2.)/100
    st.caption("Duty/tax defaults are illustrative, not Iranian legal rates. Enter recoverable VAT separately outside economic cost; model does not calculate VAT cash-flow timing.")

# Historical data can calibrate risk before the risk tab is rendered.
monthly=None
history_meta=None
with tabs[3]:
    st.subheader("Historical validation")
    st.write("Upload aligned observations: date, arabica_usd_kg, robusta_usd_kg, usd_irr. Daily data are averaged into calendar months; missing months are rejected.")
    uploaded=st.file_uploader("History CSV",type=['csv'])
    history_source=st.text_input("History source and FX market definition",placeholder="Supplier export / licensed feed; settlement or free-market FX")
    history_kind=st.selectbox("History classification",["Unverified user upload","Illustrative / synthetic","Provider-sourced, user verified"])
    history_mode=st.radio("Historical dataset",["Uploaded CSV","Fetched reference history"],horizontal=True,key="history_mode")
    years=st.selectbox("Years of reference history",[2,3,5,10],index=2)
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
              coffee_unfixed=coffee_unfixed,fx_unfixed=fx_unfixed)
    base=economics(deal)
except ValueError as exc:
    st.error(str(exc)); st.stop()

with tabs[1]:
    st.subheader("Landed economics")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Coffee purchase · USD",f"{base['purchase_usd']:,.0f}")
    c2.metric("Cost per sellable kg · IRR",f"{base['cost_irr_kg']:,.0f}")
    c3.metric("Profit · billion IRR",f"{base['profit_irr']/1e9:,.2f}")
    c4.metric("Gross contribution margin",f"{base['margin']:.1%}")
    shares=blend(deal)
    table=pd.DataFrame({'Coffee':['Arabica','Robusta'],'Weight share':[weight,1-weight],
                        'Value share':shares,'kg':[quantity*weight,quantity*(1-weight)]})
    st.dataframe(table,width="stretch",hide_index=True)
    st.plotly_chart(px.pie(table,names='Coffee',values='Value share',hole=.6,title='Purchase value share'),use_container_width=True)
    target=st.slider("Target margin % of revenue",0,80,20)/100
    st.metric("Required net selling price · IRR/kg",f"{base['cost_irr_kg']/(1-target):,.0f}")
    st.caption("Margin = profit / revenue; not markup. Revenue and sale price stay fixed across risk scenarios.")

with tabs[2]:
    st.subheader("Correlated Monte Carlo")
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
        sample,factors=simulate(deal,vol,drift,corr,n,seed,logistics_cv)
        rr=risk(sample['total_irr'],base['total_irr'],confidence)
    except ValueError as exc:
        st.error(str(exc)); st.stop()
    c1,c2,c3=st.columns(3)
    c1.metric("Cost-overrun VaR · billion IRR",f"{rr['var_irr']/1e9:.2f}")
    c2.metric("Cost-overrun CVaR · billion IRR",f"{rr['cvar_irr']/1e9:.2f}")
    loss_prob=float(np.mean(sample['profit_irr']<0))
    c3.metric("Probability of negative margin",f"{loss_prob:.1%}")
    st.caption("Loss = future total cost minus today's modeled total cost. VaR may be negative. CVaR averages the worst tail. These are cost-overrun risks, not loss of inventory market value.")
    st.plotly_chart(px.histogram(x=sample['profit_irr']/1e9,nbins=80,
                                labels={'x':'Profit · billion IRR'},title='Three-month profit distribution'),use_container_width=True)
    intervals=np.quantile(sample['cost_irr_kg'],[.05,.5,.95])
    st.write(dict(zip(['5th percentile cost/kg','Median cost/kg','95th percentile cost/kg'],intervals)))
    st.metric(f"Selling price for {confidence:.0%} modeled cost coverage and target margin",
              f"{np.quantile(sample['cost_irr_kg'],confidence)/(1-target):,.0f} IRR/kg")
    se=np.sqrt(loss_prob*(1-loss_prob)/n)
    st.caption(f"Monte Carlo sampling error for loss probability: approximately ±{1.96*se:.2%} (95%, normal approximation). This excludes parameter and model uncertainty.")
    # Independent batches expose simulation noise without claiming parameter confidence.
    batch_vars=[risk(x,base['total_irr'],confidence)['var_irr'] for x in np.array_split(sample['total_irr'],10)]
    st.caption(f"VaR across 10 simulation batches: {min(batch_vars)/1e9:.2f}–{max(batch_vars)/1e9:.2f} billion IRR; a stability diagnostic, not a confidence interval.")
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
            bt=backtest(monthly,deal,confidence=confidence,seed=seed)
            st.dataframe(bt,width="stretch")
            hits=int(bt.breach.sum()); count=len(bt); p=hits/count; z=1.96
            center=(p+z*z/(2*count))/(1+z*z/count)
            half=z*np.sqrt(p*(1-p)/count+z*z/(4*count*count))/(1+z*z/count)
            st.write(f"Breaches: {hits}/{count} ({p:.1%}); nominal {(1-confidence):.1%}. Wilson 95% interval: {max(0,center-half):.1%}–{min(1,center+half):.1%}.")
            st.download_button("Download backtest",bt.to_csv(index=False),"backtest.csv","text/csv")
            st.warning("Retrospective test uses revised observations, not publication-time vintages. Rolling 24-month training, non-overlapping three-month targets, zero drift, fixed logistics. It validates market-cost risk only; it does not validate delivery or profit forecasts.")
        except ValueError as exc: st.error(str(exc))

with tabs[4]:
    st.subheader("Reproducible run")
    report=dict(version='1.0.0',generated_at=datetime.now(timezone.utc).isoformat(),
                deal=asdict(deal),sources=audit,history=history_meta,
                risk_parameters=dict(method=method,volatility=vol.tolist(),drift=drift.tolist(),
                                     correlation=corr.tolist(),paths=n,seed=seed,confidence=confidence,
                                     logistics_cv=logistics_cv,target_margin=target),
                baseline={k:float(v) for k,v in base.items()},risk=rr,
                loss_probability=loss_prob,scenarios=scenario_rows,
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

