"""Exhaustive controls for fixed-factor prefix feasibility and evidence guards."""
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_sbox_stage_splice import Span, combine, all_forms
import search_two_and_prefix as prefix


class PrefixTests(unittest.TestCase):
    def test_kernel_generators_span_all_null_vectors(self):
        for columns in ([1,2,3], [0,0,1], [3,5,6,8], [1,2,4]):
            generators = prefix.kernel(columns)
            expected = {mask for mask in range(1<<len(columns)) if combine(columns,mask)==0}
            self.assertEqual(set(all_forms(generators)), expected)

    def test_fixed_factors_against_affine_bruteforce(self):
        W = [255,170,204,240]
        B = Span(W)
        forms = all_forms(W)
        directions = sorted({B.reduce(v)[0] for v in range(256)}-{0})
        positives = negatives = 0
        for target in directions:
            problem = prefix.Problem(W,[target])
            for fm,hm,alpha,beta in itertools.product(range(2,16,2),range(2,16,2),(0,1),(0,1)):
                f,h = combine(W,fm),combine(W,hm)
                expected = False
                for g in forms:
                    q = f & g
                    if not problem.T.reduce(q)[0]:
                        continue
                    for v in forms:
                        r = (h & (v ^ (q if alpha else 0))) ^ (q if beta else 0)
                        if not problem.T.reduce(r)[0] and B.reduce(r)[0]:
                            expected = True
                            break
                    if expected:
                        break
                witnesses,_ = problem.solve(fm,hm,alpha,beta)
                self.assertEqual(bool(witnesses),expected)
                positives += expected
                negatives += not expected
                for witness in witnesses:
                    current = list(W)
                    for left,right in witness['gates']:
                        current.append(combine(current,left)&combine(current,right))
                    self.assertEqual(current[-2:], [int(witness[k],16) for k in ('q_hex','p_hex')])
        self.assertEqual((positives,negatives),(966,1974))

    def test_invalid_factor_masks_and_dependent_base(self):
        data={'W_hex':['0xff','0xaa','0xcc'],'targets_hex':['0xf0'],'pool_masks':[1]}
        with self.assertRaisesRegex(ValueError,'constant-free'):
            prefix.search(data)
        with self.assertRaisesRegex(ValueError,'independent'):
            prefix.Problem([255,170,170],[204])

    def test_cli_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'input.json';output=folder/'output.json'
            source.write_text(json.dumps({'W_hex':['0xff','0xaa','0xcc','0xf0'],
                'targets_hex':['0x72'],'pool_masks':[2,4,6,8,10,12,14]}))
            argv=[sys.executable,prefix.__file__,'--input',str(source),'--output',str(output)]
            result=subprocess.run(argv,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            evidence=output.read_bytes()
            result=subprocess.run(argv,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('output must be new',result.stderr)
            self.assertEqual(output.read_bytes(),evidence)


if __name__ == '__main__':
    unittest.main()
