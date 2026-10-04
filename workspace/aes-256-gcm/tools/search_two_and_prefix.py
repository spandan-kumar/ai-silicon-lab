#!/usr/bin/env python3
"""Find realizable two-AND prefixes for a finite pool of fixed factors.

For q=f*g and p=h*(v+alpha*q), fixing f,h,alpha,beta makes
p+beta*q=h*v+(alpha*h+beta)*f*g linear in the coefficients of g,v.
Require q outside T=span(W,targets), and p+beta*q in T but outside W.
A returned prefix alone does not implement the target outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from analyze_sbox_stage_splice import Span, combine


def kernel(columns):
    rows, generators = {}, []
    for index, value in enumerate(columns):
        mask = 1 << index
        while value:
            pivot = value.bit_length()-1
            if pivot not in rows:
                rows[pivot] = value, mask
                break
            row, coefficients = rows[pivot]
            value ^= row
            mask ^= coefficients
        if not value:
            generators.append(mask)
    return generators


class Problem:
    def __init__(self, W, targets):
        self.W = W
        self.B = Span(W)
        self.T = Span(W+targets)
        if self.B.rank() != len(W):
            raise ValueError('W must be linearly independent')
        if self.T.rank() == len(W):
            raise ValueError('targets must add a direction outside W')
        self.n = len(W)-1

    def solve(self, fmask, hmask, alpha, beta):
        W, n = self.W, self.n
        f, h = combine(W, fmask), combine(W, hmask)
        qcolumns = [f & w for w in W[1:]]
        multiplier = (h if alpha else 0) ^ (W[0] if beta else 0)
        rcolumns = [multiplier & q for q in qcolumns] + [h & w for w in W[1:]]
        generators = kernel([self.T.reduce(r)[0] for r in rcolumns])

        def tags(mask):
            q = combine(qcolumns, mask & ((1<<n)-1))
            r = combine(rcolumns, mask)
            return self.T.reduce(q)[0], self.B.reduce(r)[0]

        images = [tags(mask) for mask in generators]
        qa = next((k for k,(a,b) in zip(generators,images) if a), None)
        rb = next((k for k,(a,b) in zip(generators,images) if b), None)
        if qa is None or rb is None:
            return [], len(generators)
        # Nonzero maps need not be nonzero on the same kernel generator.
        candidates = [qa, rb, qa^rb, *generators]
        candidates += [a^b for a,b in itertools.combinations(generators,2)]
        witnesses = []
        for mask in dict.fromkeys(candidates):
            outside, target = tags(mask)
            if not outside or not target:
                continue
            gmask = (mask & ((1<<n)-1)) << 1
            vmask = (mask >> n) << 1
            q = f & combine(W,gmask)
            p = h & (combine(W,vmask) ^ (q if alpha else 0))
            r = p ^ (q if beta else 0)
            assert self.T.reduce(q)[0] == outside
            assert not self.T.reduce(r)[0] and self.B.reduce(r)[0] == target
            assert Span(W+[q]).reduce(p)[0]
            witnesses.append({'gates':[[fmask,gmask],[hmask,vmask | (alpha<<len(W))]],
                'alpha':alpha,'beta':beta,'q_hex':hex(q),'p_hex':hex(p),
                'auxiliary_mod_T_hex':hex(outside),'target_mod_W_hex':hex(target)})
        assert witnesses
        return witnesses, len(generators)


def search(data):
    W = [int(v,16) for v in data['W_hex']]
    targets = [int(v,16) for v in data['targets_hex']]
    if not W or W[0] <= 0 or W[0] & (W[0]+1):
        raise ValueError('W[0] must be the all-one truth vector')
    if any(v<0 or v>W[0] for v in W+targets):
        raise ValueError('truth vectors must fit the declared all-one vector')
    pool = sorted(set(data['pool_masks']))
    if not pool or any(type(v) is not int or v<=0 or v>=1<<len(W) or v&1 for v in pool):
        raise ValueError('pool_masks must be nonzero constant-free coefficient masks in W')
    problem = Problem(W,targets)
    envelopes, dimensions = {}, {}
    feasible = 0
    started = time.monotonic()
    for f,h in itertools.product(pool,repeat=2):
        for alpha,beta in itertools.product((0,1),repeat=2):
            witnesses,dim = problem.solve(f,h,alpha,beta)
            dimensions[str(dim)] = dimensions.get(str(dim),0)+1
            feasible += bool(witnesses)
            for witness in witnesses:
                envelopes.setdefault(witness['auxiliary_mod_T_hex'],witness)
    return {'complete':True,'W_hex':data['W_hex'],'targets_hex':data['targets_hex'],
        'pool_masks':pool,'fixed_factor_cases':4*len(pool)**2,'feasible_factor_cases':feasible,
        'kernel_dimensions':dimensions,'envelopes':list(envelopes.values()),
        'wall_seconds':time.monotonic()-started,
        'scope':'Exact feasibility for the supplied fixed-factor pool. Witness sampling uses kernel generators and their pair sums; it does not enumerate every envelope. A two-AND prefix is not a complete target circuit.',
        'correct_27_AND_AES_found':False,'world_first_established':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new; existing evidence is preserved')
    try:
        raw = args.input.read_bytes()
        result = search(json.loads(raw))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    result['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['span_module_sha256'] = hashlib.sha256(Path(__file__).with_name('analyze_sbox_stage_splice.py').read_bytes()).hexdigest()
    with args.output.open('x') as output:
        output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'pass','systems':result['fixed_factor_cases'],'envelopes':len(result['envelopes'])}))


if __name__ == '__main__':
    main()
