import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace
import numpy as np
import pandas as pd
from coffee_risk.model import Deal,economics,risk
from coffee_risk.money import to_irr,from_irr,cost_breakdown,required_price,diagnostics,compare_market
from coffee_risk.evidence import manifest_from_deal,apply_manifest,validate_manifest,store_document
from coffee_risk.registry import register,verify,settle
from coffee_risk.alternatives import forecast_sample,forecast,compare
from coffee_risk.diagnostics import attribution,paired_loss_sensitivity,explain_failures

class OperationalTests(unittest.TestCase):
    def history(self):
        rng=np.random.default_rng(34)
        return pd.DataFrame(np.exp(np.cumsum(rng.normal(0,.03,(60,3)),axis=0))*[6,4,42000],index=pd.date_range('2015-01-01',periods=60,freq='MS'))
    def test_user_fx_unit_roundtrip(self):
        self.assertEqual(to_irr(271000,'toman'),2710000)
        self.assertEqual(from_irr(2710000,'toman'),271000)
        with self.assertRaises(ValueError):to_irr(float('nan'),'IRR')
    def test_breakdown_conservation(self):
        d=replace(Deal(),roast_yield=.84,roast_cost_irr_input_kg=100000,packaging_irr_output_kg=200000,selling_cost_irr_output_kg=50000)
        b=economics(d);rows=cost_breakdown(b,'IRR')
        self.assertAlmostEqual(sum(x['total'] for x in rows),b['total_irr'],delta=.001)
        self.assertAlmostEqual(sum(x['per_sellable_kg'] for x in rows),b['cost_irr_kg'])
    def test_roast_yield_and_net_revenue(self):
        d=replace(Deal(),quantity_kg=100,shrinkage=.1,roast_yield=.8,discount_rate=.1,sold_fraction=.25,selling_cost_irr_output_kg=100)
        b=economics(d)
        self.assertEqual(b['sellable_kg'],72)
        self.assertEqual(b['sold_kg'],18)
        self.assertAlmostEqual(b['recognized_revenue_irr'],18*d.sale_irr_kg*.9)
        self.assertAlmostEqual(b['allocated_cost_sold_irr']+b['inventory_cost_irr']+b['unincurred_selling_irr'],b['total_irr'])
    def test_required_price_margin_discount(self):
        price=required_price(100,.2,.1)
        self.assertAlmostEqual((price*.9-100)/(price*.9),.2)
        with self.assertRaises(ValueError):required_price(100,1)
    def test_small_shipment_fixed_cost_warning(self):
        d=replace(Deal(),quantity_kg=1)
        self.assertTrue(any('Freight' in x for x in diagnostics(d,economics(d))))
    def test_quote_scope_not_forced_to_fit(self):
        result=compare_market(100,200,'IRR','green','roasted','retail',False)
        self.assertFalse(result['comparable']);self.assertEqual(result['gap_pct'],-50)
    def test_manifest_roundtrip_and_explicit_missing(self):
        m=manifest_from_deal(Deal(),{})
        self.assertEqual(apply_manifest(m),Deal())
        m['fields'][0]['status']='missing'
        with self.assertRaisesRegex(ValueError,'Incomplete'):apply_manifest(m)
    def test_mismatched_evidence_unit(self):
        m=manifest_from_deal(Deal(),{});m['fields'][0]['unit']='toman'
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_document_no_verification_without_link(self):
        m=manifest_from_deal(Deal(),{});m['fields'][0]['status']='documented'
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_document_hash_safe_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            record=store_document(tmp,'../../fixture.txt',b'SYNTHETIC document-storage fixture only')
            self.assertEqual(record['name'],'fixture.txt');self.assertTrue((Path(tmp)/record['stored_file']).exists())
            with self.assertRaises(ValueError):store_document(tmp,'bad.exe',b'No executable accepted')
    def test_forecast_digest_and_completed_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=str((pd.Timestamp.now().to_period('M')+3).to_timestamp().date())
            item=register(tmp,{'target_month':target,'fixture':'SYNTHETIC test only'})
            self.assertEqual(verify(item),item)
            item['payload']['fixture']='tampered'
            with self.assertRaises(ValueError):verify(item)
            with self.assertRaises(ValueError):register(tmp,{'target_month':'2020-01-01'})
    def test_unsettled_forecast_cannot_get_early_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=str((pd.Timestamp.now().to_period('M')+3).to_timestamp().date())
            item=register(tmp,{'target_month':target})
            with self.assertRaises(ValueError):settle(tmp,item,1.,{'source':'fixture','retrieved_at':'fixture'})
    def test_all_five_operational_methods_and_zero_log_policy(self):
        for method in ('gbm','historical','block','ewma_block','student_t'):
            s,f=forecast_sample(self.history(),Deal(),method,n=1000,logistics_cv=.1,growth_policy='zero_log')
            self.assertEqual(f.shape,(1000,3));self.assertEqual(len(s['total_irr']),1000)
            np.testing.assert_allclose(np.log(f).mean(axis=0),0,atol=1e-12)
    def test_shapley_conserves_nonlinear_cost(self):
        d=Deal();f=[1.2,1.1,1.3]
        a=attribution(d,f)
        self.assertAlmostEqual(sum(a.values()),economics(d,f)['total_irr']-economics(d)['total_irr'],delta=.001)
    def test_paired_loss_sensitivity_and_failure_rows(self):
        frame=compare(self.history(),Deal(),n=500,growth_policy='zero_log')
        paired=paired_loss_sensitivity(frame,repeats=40)
        self.assertEqual(set(paired),{'historical','block','ewma_block','student_t'})
        rows=explain_failures(self.history(),Deal(),frame)
        self.assertEqual(len(rows),int(frame.breach.sum()))

    def test_sensitivity_respects_selected_engine_and_growth(self):
        from coffee_risk.alternatives import parameter_sensitivity
        result=parameter_sensitivity(self.history(),Deal(),repeats=3,n=200,method='student_t',growth_policy='zero_log')
        self.assertEqual(result['method'],'student_t')
        self.assertEqual(result['growth_policy'],'zero_log')
        self.assertEqual(len(result['var_p05_p50_p95']),3)

    def test_editor_float_months_are_normalized_and_fraction_rejected(self):
        m=manifest_from_deal(Deal(),{})
        row=next(r for r in m['fields'] if r['field']=='months');row['value']=3.
        self.assertIsInstance(apply_manifest(m).months,int)
        row['value']=3.5
        with self.assertRaises(ValueError):apply_manifest(m)
