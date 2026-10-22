"""Integrity/witness controls for the generic pair-scan comparison helper."""
import copy
import unittest

import compare_norm_frontier_pair_scans as compare
import verify_norm_frontier_pairs as symbolic


class PairComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = symbolic.RAW
        old = [symbolic.multiply(raw[2*i], raw[2*i+1]) for i in range(4)]
        old.append(symbolic.multiply(raw[0] ^ raw[2], raw[5] ^ raw[7]))
        q = symbolic.polar(symbolic.combine(old, 15))
        cls.state = {'nonlinear_rref_hex': list(map(hex, old)),
                     'marked_Q_polars': [q], 'first_source': {'code': 0, 'polar_coset': 0}}
        case = symbolic.audit(cls.state, 0)
        w = case['witnesses'][0]
        cls.producer = {
            'state_id': 0, 'source_code': 0, 'source_polar_coset': 0,
            'complete': False, 'left_forms': case['left_forms_checked'],
            'right_kernel_dimension_histogram': [case['right_kernel_dimension_histogram'].get(i, 0) for i in range(14)],
            'K_dimension': 5, 'high_rank': 0,
            'K_polars': [symbolic.polar(p) for p in old],
            'K_gate_selectors': [1 << i for i in range(5)],
            'witness_truth_rows': 256,
            'marks': [{'Q_polar': q, 'Q_old_gate_selector': w['marked_Q_old_decoder'],
                       'status': 'positive', 'left_mask': w['left'], 'right_mask': w['right'],
                       'old_gate_selector': w['old_cancel'], 't_anf_hex': w['candidate_anf_hex'],
                       't_polar': w['candidate_polar'], 't_plus_Q_polar': w['candidate_polar'] ^ q}]}
        cls.independent = copy.deepcopy(cls.producer)
        cls.independent['K_all_selectors'] = list(range(32))
        cls.independent['K_all_polars'] = [symbolic.polar(symbolic.combine(old, s)) for s in range(32)]

    def test_actual_positive_witness_in_both_schemas(self):
        self.assertEqual(compare.check(self.state, self.producer), (['positive'], 1))
        self.assertEqual(compare.check(self.state, self.independent, True), (['positive'], 1))

    def test_reject_corrupted_records(self):
        mutations = [
            lambda r: r.update(complete=True),
            lambda r: r.update(left_forms=0),
            lambda r: r.update(high_rank=1),
            lambda r: r['K_polars'].__setitem__(0, 0),
            lambda r: r['right_kernel_dimension_histogram'].__setitem__(0, 1),
            lambda r: r['marks'][0].update(status='unknown'),
            lambda r: r['marks'][0].update(Q_old_gate_selector=0),
            lambda r: r['marks'][0].update(left_mask=0),
            lambda r: r['marks'][0].update(old_gate_selector=0),
            lambda r: r['marks'][0].update(t_anf_hex='0x0'),
            lambda r: r['marks'][0].update(t_plus_Q_polar=0),
            lambda r: r.update(witness_truth_rows=0),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                record = copy.deepcopy(self.producer)
                mutate(record)
                with self.assertRaises(AssertionError):
                    compare.check(self.state, record)


if __name__ == '__main__':
    unittest.main()
