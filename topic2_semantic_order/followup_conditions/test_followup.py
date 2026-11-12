"""CPU tests for data-policy rejection, scheduler semantics, and paired inference."""
from pathlib import Path
import copy
import unittest

import numpy as np

from analyze_new import CONTRASTS, contrast
from common import *
from coverage import validate as coverage_validate
from prepare import configpath, validate_config
from regression import A


class Contracts(unittest.TestCase):
    def test_linear_constant_preserve_actual_warmup_and_nominal_sum(self):
        c=config(configpath("C",SEEDS[0]))
        r=hf_rates(c)
        q=hf_rates(config(source("A",SEEDS[0])))
        self.assertEqual(len(r),1984)
        self.assertEqual((r[0],q[0],q[1]),(0,0,.0002))
        np.testing.assert_allclose(r[1:],CONST,rtol=0,atol=1e-18)
        self.assertAlmostEqual(sum(r),sum(q),places=14)

    def test_v4_order_guards(self):
        records=input_records()
        a,_=actual_order("A",SEEDS[0],records)
        b,_=actual_order("B",SEEDS[0],records)
        self.assertNotEqual(a,b)
        self.assertGreater(check_seq(a,records)[1],0)
        self.assertEqual(check_seq(b,records,within=True)[1],0)
        with self.assertRaises(ValueError):
            check_seq(b[:-1]+b[:1],records,within=True)

    def test_training_rejects_eval_input_and_optimizer_changes(self):
        c=config(configpath("D",SEEDS[0]))
        validate_config(c,"D",SEEDS[0])
        for section,key,value in (("data","train",A.HDEV),("data","valid",A.CT),
                                  ("training","optim","sgd"),("chat_template_kwargs","enable_thinking",False)):
            changed=copy.deepcopy(c)
            changed[section][key]=value
            with self.assertRaises(ValueError):
                validate_config(changed,"D",SEEDS[0])

    def test_coverage_without_approval_is_closed(self):
        with self.assertRaisesRegex(ValueError,"explicit, task-specific data approval"):
            coverage_validate.validate(Path("/does-not-exist"),None)

    def test_interaction_preserves_cluster_and_seed_pairing(self):
        ids=list(range(8))
        groups={i:"g" for i in ids}
        tab=A.Tab(ids,groups,{i:i//2 for i in ids},1)
        first=np.array([0,1,0,1,0,1,0,1])
        full=np.ones(8)
        base=full
        # Every template contains equal A/C and B/D contrasts. The 0.5
        # interaction must survive every shared draw, irrespective of seed.
        by={"A":[np.roll(first,i) for i in range(5)],
            "B":[np.roll(first,i) for i in range(5)],
            "C":[np.roll(first,i) for i in range(5)],
            "D":[full for i in range(5)]}
        r=next(x for x in contrast(tab,by,base,CONTRASTS["interaction"],{},200,11)
               if x["metric"]=="overall")
        self.assertEqual([r[k] for k in ("point","ci95_low","ci95_high")],[.5,.5,.5])
        for a in by:
            by[a].pop()
        with self.assertRaisesRegex(ValueError,"All five"):
            contrast(tab,by,base,CONTRASTS["interaction"],{},10,11)


if __name__=="__main__":
    unittest.main()
