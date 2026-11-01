import unittest
from pathlib import Path
try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest=None

@unittest.skipIf(AppTest is None,'Streamlit is not installed')
class AppTests(unittest.TestCase):
    def test_default_dashboard(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        self.assertEqual(len(app.exception),0)
        self.assertGreaterEqual(len(app.metric),10)
        app.slider(key='blend_weight').set_value(100).run()
        self.assertEqual(len(app.exception),0)
    def test_missing_fetch_is_not_demo_fallback(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.selectbox(key='mode_usd_irr').set_value('Fetched reference').run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Fetch a valid' in e.value for e in app.error))


    def test_calibration_and_backtest(self):
        import pandas as pd
        from coffee_risk.history import validate_history
        path=Path(__file__).parents[1]
        history=validate_history(pd.read_csv(path/'examples/ILLUSTRATIVE_history.csv'))
        app=AppTest.from_file(str(path/'app.py'),default_timeout=30)
        app.session_state['fetched_history']=(history,{'source':'SYNTHETIC test fixture'})
        app.run()
        app.radio(key='history_mode').set_value('Fetched reference history').run()
        app.radio(key='risk_method').set_value('Estimate volatility and correlation from uploaded history').run()
        app.button(key='backtest').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(list(app.error))
        self.assertTrue(any('Breaches:' in m.value for m in app.markdown))
    def test_manual_override_preserves_provider(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30)
        app.session_state['quotes']={'usd_irr':dict(value=42000,observation_date='2024-01-01',source='TEST ONLY')}
        app.run()
        app.selectbox(key='mode_usd_irr').set_value('Fetched reference').run()
        self.assertEqual(len(app.exception),0)
        app.selectbox(key='mode_usd_irr').set_value('Illustrative / manual').run()
        self.assertEqual(app.number_input(key='manual_usd_irr').value,800000)
        self.assertEqual(app.session_state['quotes']['usd_irr']['value'],42000)
    def test_budget_sizing(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.selectbox(key='sizing').set_value('Coffee purchase value (USD)').run()
        self.assertEqual(len(app.exception),0)
        invoice=[m for m in app.metric if m.label=='Coffee purchase · USD'][0]
        self.assertEqual(invoice.value,'100,000')


    def test_alternative_comparison_interface(self):
        import pandas as pd
        from coffee_risk.history import validate_history
        path=Path(__file__).parents[1]
        history=validate_history(pd.read_csv(path/'examples/ILLUSTRATIVE_history.csv'))
        app=AppTest.from_file(str(path/'app.py'),default_timeout=30)
        app.session_state['fetched_history']=(history,{'source':'SYNTHETIC interface test fixture'})
        app.run()
        app.radio(key='history_mode').set_value('Fetched reference history').run()
        app.button(key='advanced_backtest').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(list(app.error))
        self.assertTrue(any('Research comparison' in w.value for w in app.warning))

    def test_toman_fx_and_price_explanation(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.selectbox(key='display_unit').set_value('toman').run()
        app.button(key='user_fx_preset').click().run()
        self.assertEqual(app.number_input(key='manual_usd_irr_toman').value,271000)
        self.assertEqual(len(app.exception),0)
        costs=[m for m in app.metric if m.label=='Cost per sellable kg'][0]
        self.assertIn('تومان',costs.value)
        self.assertTrue(any('cost per sellable' in x.value for x in app.markdown))

    def test_five_operational_engines_with_fixture(self):
        import pandas as pd
        from coffee_risk.history import validate_history
        path=Path(__file__).parents[1]
        history=validate_history(pd.read_csv(path/'examples/ILLUSTRATIVE_history.csv'))
        app=AppTest.from_file(str(path/'app.py'),default_timeout=30)
        app.session_state['fetched_history']=(history,{'source':'SYNTHETIC interface fixture'})
        app.run();app.radio(key='history_mode').set_value('Fetched reference history').run()
        app.radio(key='risk_method').set_value('Estimate volatility and correlation from uploaded history').run()
        for name in ('gbm','historical','block','ewma_block','student_t'):
            app.selectbox(key='scenario_engine').set_value(name).run()
            self.assertEqual(len(app.exception),0,name)
            self.assertFalse(list(app.error),name)

    def test_roasted_stage_and_evidence_panel(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.selectbox(key='product_stage').set_value('roasted').run()
        app.number_input(key='roast_yield').set_value(80.).run()
        app.number_input(key='sold').set_value(50.).run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('shipment evidence' in h.value.lower() for h in app.subheader))

    def test_money_unit_switch_preserves_custom_inputs(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.number_input(key='manual_usd_irr').set_value(2710000.).run()
        app.number_input(key='sale_IRR').set_value(30000000.).run()
        before=next(m.value for m in app.metric if m.label=='Gross contribution margin')
        app.selectbox(key='display_unit').set_value('toman').run()
        self.assertEqual(app.number_input(key='manual_usd_irr_toman').value,271000)
        self.assertEqual(app.number_input(key='sale_toman').value,3000000)
        self.assertEqual(before,next(m.value for m in app.metric if m.label=='Gross contribution margin'))

    def test_coffee_only_requires_no_fx_exposure(self):
        import pandas as pd
        from coffee_risk.history import validate_history
        path=Path(__file__).parents[1]
        history=validate_history(pd.read_csv(path/'examples/ILLUSTRATIVE_history.csv'))
        history['usd_irr']=1.
        app=AppTest.from_file(str(path/'app.py'),default_timeout=30)
        app.session_state['coffee_only_history']=(history,{'source':'SYNTHETIC fixture; USD identity'})
        app.run();app.radio(key='history_mode').set_value('Coffee benchmarks only (FX fixed)').run()
        app.selectbox(key='scenario_engine').set_value('historical').run()
        self.assertTrue(any('cannot model FX' in x.value for x in app.error))
        next(x for x in app.slider if x.label=='FX still unconverted / unhedged %').set_value(0).run()
        self.assertEqual(len(app.exception),0);self.assertFalse(list(app.error))

    def test_completed_manifest_applies_all_deal_values(self):
        from coffee_risk.model import Deal
        from coffee_risk.evidence import manifest_from_deal
        from dataclasses import asdict
        d=Deal(quantity_kg=1000,usd_irr=2710000,sale_irr_kg=30000000,roast_yield=.84,packaging_irr_output_kg=500000)
        m=manifest_from_deal(d,{})
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30)
        app.session_state['pending_deal']=asdict(d)
        app.session_state['pending_manifest']=m
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(app.session_state['active_manifest'],m)
        self.assertEqual(app.number_input(key='manual_usd_irr').value,2710000)
        self.assertEqual(app.selectbox(key='product_stage').value,'roasted')

    def test_green_benchmark_cannot_be_claimed_roasted_purchase(self):
        app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
        app.button(key='load_reviewed_snapshot').click().run()
        app.selectbox(key='product_stage').set_value('roasted').run()
        app.selectbox(key='input_stage').set_value('roasted').run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('FRED benchmarks are green' in x.value for x in app.error))
