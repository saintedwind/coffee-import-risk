import unittest
from unittest.mock import patch
import json
from coffee_risk.data import fetch_coffee,fetch_fx
class DataTests(unittest.TestCase):
    @patch('coffee_risk.data.read_url')
    def test_fred_units_and_missing(self,get):
        get.return_value=b'observation_date,PCOFFOTMUSDM\n2024-01-01,100\n2024-02-01,.\n'
        df,m=fetch_coffee('arabica_usd_kg')
        self.assertAlmostEqual(df.value.iloc[0],1/.45359237)
        self.assertEqual(m['observation_date'],'2024-01-01')
        self.assertEqual(len(m['sha256']),64)
    @patch('coffee_risk.data.read_url')
    def test_network_failure_no_fallback(self,get):
        get.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError): fetch_coffee('robusta_usd_kg')
    @patch('coffee_risk.data.read_url')
    def test_fx_pair_and_metadata(self,get):
        get.return_value=json.dumps([dict(date='2024-01-01',base='USD',quote='IRR',rate=42000,providers=['test'])]).encode()
        df,m=fetch_fx()
        self.assertEqual(m['unit'],'IRR/USD')
        self.assertEqual(df.value.iloc[0],42000)
    @patch('coffee_risk.data.read_url')
    def test_wrong_fx_rejected(self,get):
        get.return_value=b'[{"date":"2024-01-01","base":"EUR","quote":"IRR","rate":1}]'
        with self.assertRaises(ValueError): fetch_fx()
    @patch('coffee_risk.data.read_url')
    def test_empty_fx_rejected(self,get):
        get.return_value=b'[]'
        with self.assertRaises(ValueError): fetch_fx()
    @patch('coffee_risk.data.read_url')
    def test_negative_rejected(self,get):
        get.return_value=b'observation_date,PCOFFROBUSDM\n2024-01-01,-10\n'
        with self.assertRaises(ValueError): fetch_coffee('robusta_usd_kg')


    @patch('coffee_risk.data.fetch_coffee')
    @patch('coffee_risk.data.read_url')
    def test_joint_history_has_common_months(self,get,coffee):
        import pandas as pd
        from coffee_risk.data import fetch_joint_history
        now=pd.Timestamp.now()
        end=now.replace(day=1)-pd.Timedelta(days=1)
        dates=pd.date_range(end.to_period('M').to_timestamp()-pd.DateOffset(months=23),periods=24,freq='MS')
        get.return_value=json.dumps([dict(date=str(d.date()),base='USD',quote='IRR',rate=42000) for d in dates]).encode()
        coffee.return_value=(pd.DataFrame({'date':dates,'value':[5.]*24}),{'source':'test fixture'})
        frame,meta=fetch_joint_history(2)
        self.assertEqual(frame.shape,(24,3))
        self.assertEqual(frame.usd_irr.iloc[-1],42000)

