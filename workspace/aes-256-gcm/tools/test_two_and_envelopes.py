"""Exhaustive small controls for complete quotient enumeration."""
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_sbox_stage_splice import Span, combine, all_forms
import enumerate_two_and_envelopes as envelope


class EnvelopeTests(unittest.TestCase):
    def test_image_fibers_against_exhaustive_maps(self):
        cases = 0
        for dimension in range(4):
            for columns in itertools.product(range(4),repeat=2*dimension):
                images = [(1<<i,columns[2*i],columns[2*i+1]) for i in range(dimension)]
                expected = set()
                for mask in range(1<<dimension):
                    a = c = 0
                    for i,(k,b,d) in enumerate(images):
                        if mask>>i&1:
                            a ^= b
                            c ^= d
                    if a and c:
                        expected.add(a)
                witnesses, info = envelope.enumerate_images(images)
                self.assertTrue(info['enumerated'])
                self.assertEqual({a for mask,a,c in witnesses},expected)
                self.assertEqual(len(witnesses),info['feasible_envelope_count'])
                for mask,a,c in witnesses:
                    self.assertEqual(combine([b for k,b,d in images],mask),a)
                    self.assertEqual(combine([d for k,b,d in images],mask),c)
                    self.assertNotEqual(a,0)
                    self.assertNotEqual(c,0)
                cases += 1
        self.assertEqual(cases,4369)

    def test_fixed_factors_against_all_affine_operands(self):
        W = [255,170,204,240]
        B = Span(W)
        forms = all_forms(W)
        directions = sorted({B.reduce(v)[0] for v in range(256)}-{0})
        systems = feasible = 0
        for target in directions:
            problem = envelope.Problem(W,[target])
            for fm,hm,alpha,beta in itertools.product(range(2,16,2),range(2,16,2),(0,1),(0,1)):
                f,h = combine(W,fm),combine(W,hm)
                expected = set()
                for g in forms:
                    q = f&g
                    a = problem.T.reduce(q)[0]
                    if not a:
                        continue
                    for v in forms:
                        r = (h&(v^(q if alpha else 0)))^(q if beta else 0)
                        if not problem.T.reduce(r)[0] and B.reduce(r)[0]:
                            expected.add(a)
                witnesses,info = envelope.fixed(problem,fm,hm,alpha,beta)
                self.assertEqual({int(w['auxiliary_mod_T_hex'],16) for w in witnesses},expected)
                self.assertEqual(info is not None,bool(expected))
                for witness in witnesses:
                    current = list(W)
                    for left,right in witness['gates']:
                        current.append(combine(current,left)&combine(current,right))
                    self.assertEqual(current[-2:],[int(witness[k],16) for k in ('q_hex','p_hex')])
                systems += 1
                feasible += bool(expected)
        self.assertEqual((systems,feasible),(2940,966))

    def test_rank_limit_is_not_a_negative_result(self):
        vectors, info = envelope.enumerate_images([(1,1,1),(2,2,2)],1)
        self.assertEqual(vectors,[])
        self.assertFalse(info['enumerated'])
        self.assertEqual(info['feasible_envelope_count'],3)
        data = {'W_hex':['0xff','0xaa','0xcc','0xf0'],
                'targets_hex':['0x72'],'first_pool_masks':[2],
                'second_pool_masks':[2,4,6,8,10,12,14]}
        result = envelope.search(data,0)
        self.assertFalse(result['complete'])
        self.assertGreater(result['feasible_factor_cases'],0)
        self.assertEqual(result['envelopes'],[])
        self.assertEqual(result['fixed_factor_cases'],28)

    def test_validation_and_cli_evidence_guard(self):
        data = {'W_hex':['0xff','0xaa','0xcc','0xf0'],
                'targets_hex':['0x72'],'pool_masks':[2,4,6,8,10,12,14]}
        with self.assertRaisesRegex(ValueError,'nonnegative'):
            envelope.search(data,-1)
        with self.assertRaisesRegex(ValueError,'constant-free'):
            envelope.search({**data,'first_pool_masks':[1]})
        with self.assertRaisesRegex(ValueError,'independent'):
            envelope.search({**data,'W_hex':['0xff','0xaa','0xaa','0xf0']})
        for key in ('W_hex','targets_hex'):
            for malformed in ('ff',{'ff':0},[255]):
                with self.assertRaisesRegex(ValueError,'array of hexadecimal'):
                    envelope.search({**data,key:malformed})
        for malformed in ([2,2.0],[2.0,2],[False,2],{2:0},'24'):
            with self.assertRaisesRegex(ValueError,'constant-free'):
                envelope.search({**data,'pool_masks':malformed})
        with self.assertRaisesRegex(ValueError,'JSON object'):
            envelope.search([])
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source,output = folder/'input.json',folder/'output.json'
            source.write_text(json.dumps(data))
            argv = [sys.executable,envelope.__file__,'--input',str(source),'--output',str(output)]
            proc = subprocess.run(argv,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            before = output.read_bytes()
            proc = subprocess.run(argv,capture_output=True,text=True)
            self.assertEqual(proc.returncode,2)
            self.assertIn('output must be new',proc.stderr)
            self.assertEqual(output.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
