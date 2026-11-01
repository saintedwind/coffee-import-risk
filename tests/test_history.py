import unittest
import numpy as np
import pandas as pd
from coffee_risk.history import validate_history,calibrate,backtest,COLS
from coffee_risk.model import Deal
def fixture(n=60):
    rng=np.random.default_rng(1)
    values=np.exp(np.cumsum(rng.normal(0,.05,(n,3)),axis=0))*[6,4,800000]
    f=pd.DataFrame(values,columns=COLS)
    f['date']=pd.date_range('2018-01-01',periods=n,freq='MS')
    return f
class HistoryTests(unittest.TestCase):
    def test_no_fill_missing_months(self):
        with self.assertRaises(ValueError): validate_history(fixture().drop(3))
    def test_duplicate(self):
        f=fixture()
        with self.assertRaises(ValueError): validate_history(pd.concat([f,f.iloc[:1]]))
    def test_short_calibration(self):
        with self.assertRaises(ValueError): calibrate(validate_history(fixture(6)))
    def test_no_lookahead(self):
        f=fixture()
        first=backtest(validate_history(f),Deal()).iloc[0]
        f.loc[27:,COLS]*=2
        altered=backtest(validate_history(f),Deal()).iloc[0]
        self.assertEqual(first.var_irr,altered.var_irr)
        self.assertEqual(first.realized_loss_irr,altered.realized_loss_irr)
    def test_nonoverlap_and_minimum(self):
        bt=backtest(validate_history(fixture(30)),Deal())
        self.assertEqual(len(bt),2)
        self.assertLess(bt.iloc[0].origin,bt.iloc[0].target)
    def test_constant_series(self):
        f=fixture()
        f['usd_irr']=42000
        vol,corr=calibrate(validate_history(f))
        self.assertEqual(vol[2],0)
        self.assertEqual(corr[2,2],1)


    def test_incomplete_current_month(self):
        f=fixture(13)
        f.loc[12,'date']=pd.Timestamp.now().to_period('M').to_timestamp()
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            validate_history(f)

    def test_baseline_no_lookahead(self):
        f=fixture()
        first=backtest(validate_history(f),Deal()).iloc[0]
        f.loc[24:,COLS]*=4
        altered=backtest(validate_history(f),Deal()).iloc[0]
        self.assertEqual(first.var_irr,altered.var_irr)
        self.assertEqual(first.historical_var_irr,altered.historical_var_irr)
        self.assertNotEqual(first.realized_loss_irr,altered.realized_loss_irr)

    def test_invalid_backtest_parameters(self):
        for train,confidence in [(12,.95),(24,.5),(24,1.)]:
            with self.assertRaises(ValueError):
                backtest(validate_history(fixture()),Deal(),train=train,confidence=confidence)

    def test_summary_perfect_coverage(self):
        from coffee_risk.history import summarize_backtest
        bt=pd.DataFrame({'breach':[False]*10,'historical_breach':[True]*10,
                         'quantile_loss_irr':[2.]*10,'historical_quantile_loss_irr':[3.]*10})
        summary=summarize_backtest(bt)
        self.assertEqual(summary['models']['gbm']['breaches'],0)
        self.assertAlmostEqual(summary['models']['historical']['breach_rate'],1.)
        self.assertGreater(summary['models']['gbm']['wilson_95'][1],0)
        self.assertEqual(summary['models']['gbm']['mean_quantile_loss_irr'],2.)

    def test_pinball_loss_hand_calculation(self):
        bt=backtest(validate_history(fixture()),Deal())
        for row in bt.itertuples():
            error=row.realized_loss_irr-row.var_irr
            expected=.95*error if error>=0 else -.05*error
            self.assertAlmostEqual(row.quantile_loss_irr,expected,delta=max(1e-5,abs(expected)*1e-12))
