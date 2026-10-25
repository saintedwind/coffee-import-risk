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

