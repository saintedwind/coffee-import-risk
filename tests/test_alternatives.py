import unittest
import numpy as np
import pandas as pd
from coffee_risk.alternatives import forecast,compare,comparison_summary,parameter_sensitivity,block_draw,ewma_residuals,METHODS
from coffee_risk.model import Deal,economics

class AlternativeTests(unittest.TestCase):
    def fixture(self,n=72):
        rng=np.random.default_rng(12)
        x=np.exp(np.cumsum(rng.normal(0,.04,(n,3)),axis=0))*[5,3,42000]
        return pd.DataFrame(x,index=pd.date_range('2015-01-01',periods=n,freq='MS'))
    def test_all_methods_constant_and_repeatable(self):
        frame=self.fixture()*0+[5,3,42000]
        for name in METHODS:
            costs=forecast(frame,Deal(),name,n=1000)
            np.testing.assert_allclose(costs,economics(Deal())['total_irr'])
            np.testing.assert_array_equal(costs,forecast(frame,Deal(),name,n=1000))
    def test_blocks_keep_joint_rows_and_contiguous_order(self):
        rows=np.column_stack([np.arange(12)]*3)
        paths=block_draw(rows,200,3,np.random.default_rng(1))
        np.testing.assert_array_equal(paths[:,:,0],paths[:,:,1])
        np.testing.assert_array_equal(np.diff(paths[:,:,0],axis=1),np.ones((200,2)))
    def test_ewma_manual_recursion(self):
        ret=np.ones((12,3))*.1;ret[-1]=.2
        residual,scale=ewma_residuals(ret,.9)
        np.testing.assert_allclose(scale,np.sqrt(.9*.01+.1*.04))
        np.testing.assert_allclose(residual[-1],[2]*3)
    def test_positive_finite_seeded(self):
        for name in METHODS:
            first=forecast(self.fixture(),Deal(),name,n=1000)
            self.assertTrue(np.isfinite(first).all() and (first>0).all())
            np.testing.assert_array_equal(first,forecast(self.fixture(),Deal(),name,n=1000))
    def test_no_future_training_all_models(self):
        frame=self.fixture(30)
        first=compare(frame,Deal(),n=1000)
        frame.iloc[24:]*=3
        second=compare(frame,Deal(),n=1000)
        np.testing.assert_array_equal(first.iloc[:5].var_irr,second.iloc[:5].var_irr)
        self.assertFalse(np.array_equal(first.iloc[:5].realized_loss,second.iloc[:5].realized_loss))
    def test_hand_pinball_and_summary(self):
        results=compare(self.fixture(30),Deal(),n=1000)
        for row in results.itertuples():
            error=row.realized_loss-row.var_irr
            self.assertAlmostEqual(row.quantile_loss, .95*error if error>=0 else -.05*error,delta=max(1e-5,abs(error)*1e-12))
        self.assertEqual(set(comparison_summary(results)),set(METHODS)|{'historical'})
    def test_invalid_parameters(self):
        for kwargs in [{'method':'bad'},{'method':'student_t','df':2},{'method':'block','block':0},{'method':'ewma_block','decay':1}]:
            with self.assertRaises(ValueError): forecast(self.fixture(),Deal(),**kwargs)
    def test_parameter_ranges_constant(self):
        frame=self.fixture()*0+[5,3,42000]
        result=parameter_sensitivity(frame,Deal(),repeats=3,n=200)
        np.testing.assert_allclose(result['var_p05_p50_p95'],0,atol=.001)
