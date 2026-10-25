import unittest
from dataclasses import replace
import numpy as np
from coffee_risk.model import Deal,economics,blend,simulate,risk,validate_correlation

class ModelTests(unittest.TestCase):
    def test_hand_calculated_invoice(self):
        d=Deal(quantity_kg=100,arabica_weight=.5,arabica_usd_kg=6,robusta_usd_kg=4,
               usd_irr=100,freight_usd=10,insurance_rate=.1,duty_rate=.2,
               local_cost_irr=100,finance_rate=.12,shrinkage=.1,sale_irr_kg=1000)
        self.assertAlmostEqual(economics(d)['purchase_usd'],500)
        self.assertAlmostEqual(economics(d)['total_irr'],(510*1.1*100*1.2+100)*1.03)
        self.assertAlmostEqual(economics(d)['cost_irr_kg'],economics(d)['total_irr']/90)
    def test_value_share_is_not_weight(self):
        self.assertAlmostEqual(blend(Deal())[0],3.6/5.2)
    def test_fixed_invoice_ignores_coffee_shock(self):
        d=replace(Deal(),coffee_unfixed=0)
        self.assertEqual(economics(d)['total_irr'],economics(d,[2,3,1])['total_irr'])
    def test_fixed_fx_ignores_fx_shock(self):
        d=replace(Deal(),fx_unfixed=0)
        self.assertEqual(economics(d)['total_irr'],economics(d,[1,1,2])['total_irr'])
    def test_zero_vol_is_deterministic(self):
        d=Deal()
        s,_=simulate(d,[0]*3,[0]*3,np.eye(3))
        np.testing.assert_allclose(s['total_irr'],economics(d)['total_irr'])
        self.assertEqual(risk(s['total_irr'],economics(d)['total_irr'])['var_irr'],0)
    def test_seed_and_correlation(self):
        corr=np.array([[1,.7,.2],[.7,1,.1],[.2,.1,1]])
        _,a=simulate(Deal(),[.3]*3,[0]*3,corr,n=50000)
        _,b=simulate(Deal(),[.3]*3,[0]*3,corr,n=50000)
        np.testing.assert_array_equal(a,b)
        np.testing.assert_allclose(np.corrcoef(np.log(a).T),corr,atol=.02)
    def test_lognormal_expected_return(self):
        _,f=simulate(Deal(),[.2]*3,[.1]*3,np.eye(3),n=100000)
        np.testing.assert_allclose(f.mean(axis=0),np.exp(.1*.25),atol=.003)
    def test_invalid_correlation(self):
        with self.assertRaises(ValueError): validate_correlation([[1,.9,.9],[.9,1,-.9],[.9,-.9,1]])
    def test_perfect_correlation_allowed(self):
        _,f=simulate(Deal(),[.3]*3,[0]*3,np.ones((3,3)))
        np.testing.assert_allclose(f[:,0],f[:,1],atol=1e-7)
    def test_tail_risk(self):
        r=risk(np.arange(1.,101.),0,.95)
        self.assertAlmostEqual(r['var_irr'],95.05)
        self.assertAlmostEqual(r['cvar_irr'],98)
    def test_bad_inputs(self):
        for d in [replace(Deal(),usd_irr=-1),replace(Deal(),shrinkage=1),replace(Deal(),arabica_weight=2),replace(Deal(),quantity_kg=float('nan'))]:
            with self.assertRaises(ValueError): economics(d)
    def test_single_coffee(self):
        self.assertEqual(blend(replace(Deal(),arabica_weight=0))[0],0)
        self.assertEqual(blend(replace(Deal(),arabica_weight=1))[0],1)

