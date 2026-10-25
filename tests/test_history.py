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

