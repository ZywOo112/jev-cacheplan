"""Meaningful M3 guards: full record preservation and out-of-order restoration."""
import json,unittest
import numpy as np
from evaluation.solo_reproduction import build_inputs,restore_outputs

class ReproductionTests(unittest.TestCase):
    def test_author_field_order_and_content(self):
        rows=[{'record_id':'unique-b','request':'refund','shared':'共同政策'} ,
              {'record_id':'unique-a','request':'replacement','shared':'共同政策'}]
        for method in ['original','solo']:
            table,plan,states=build_inputs(rows,method)
            for i,text in zip(plan.row_order,states):self.assertEqual(json.loads(text),rows[int(i)])
            if method=='original':self.assertEqual(plan.ordered_columns,tuple(rows[0]))
            else:self.assertEqual(plan.ordered_columns[0],'shared')
    def test_restore_label_probability_and_identity(self):
        rows=[{'record_id':'b','group':'z'},{'record_id':'a','group':'a'},{'record_id':'c','group':'z'}]
        _,plan,_=build_inputs(rows,'solo');ids=[r['record_id'] for r in rows]
        original=np.array([[.2,.8],[.7,.3],[.9,.1]])
        responses=[{'request_id':'request-'+str(int(i))} for i in plan.row_order]
        matrix,returned,lat=restore_outputs(plan,ids,original[plan.row_order],responses,np.array([1.,2.,3.])[plan.row_order])
        np.testing.assert_array_equal(matrix,original);np.testing.assert_array_equal(lat,[1.,2.,3.])
        self.assertEqual([r['request_id'] for r in returned],['request-0','request-1','request-2'])
    def test_invalid_response_or_id_is_rejected(self):
        rows=[{'record_id':'a','group':'a'},{'record_id':'b','group':'a'}]
        _,plan,_=build_inputs(rows,'solo')
        with self.assertRaises(ValueError):build_inputs([rows[0],rows[0]],'solo')
        for responses in [[None,{'request_id':'x'}],[{'request_id':'x'},{'request_id':'x'}]]:
            with self.assertRaises(ValueError):restore_outputs(plan,['a','b'],[[.5,.5],[.5,.5]],responses,[1.,2.])
        with self.assertRaises(ValueError):restore_outputs(plan,['a','b'],[[1.,-1.],[.5,.5]],[{'request_id':'x'},{'request_id':'y'}],[1.,2.])

if __name__=='__main__':unittest.main()
