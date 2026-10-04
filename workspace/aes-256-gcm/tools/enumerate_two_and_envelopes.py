#!/usr/bin/env python3
"""Enumerate attainable auxiliary quotients for finite two-AND factor pools.

For q=f*g and r=h*(v+alpha*q)+beta*q, fixing f,h,alpha,beta makes
r linear in g,v. On K=ker(r mod T), enumerate the nonzero images of
A=q mod T that have a lift with C=r mod W nonzero. This enumerates
envelopes T+q, not all prefixes inside an envelope or complete AES circuits.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from analyze_sbox_stage_splice import Span, combine
from search_two_and_prefix import Problem, kernel


def image_lifts(images):
    """Return an A-image basis with lifts, plus a nonzero C lift in ker(A)."""
    rows, correction = {}, None
    for mask, a, c in images:
        while a:
            pivot = a.bit_length()-1
            if pivot not in rows:
                rows[pivot] = mask, a, c
                break
            other, b, d = rows[pivot]
            mask ^= other
            a ^= b
            c ^= d
        if not a and c and correction is None:
            correction = mask, c
    return list(rows.values()), correction


def enumerate_images(images, rank_limit=18):
    rows, correction = image_lifts(images)
    rank = len(rows)
    c_rank = Span([c for mask, a, c in rows]).rank()
    count = (1<<rank)-1 if correction else (1<<rank)-(1<<(rank-c_rank))
    info = {'A_rank':rank, 'C_on_kernel_A_nonzero':correction is not None,
            'C_lift_image_rank':c_rank, 'feasible_envelope_count':count,
            'enumerated':rank<=rank_limit}
    if rank > rank_limit:
        return [], info
    witnesses, last = [], 0
    mask = a = c = 0
    for index in range(1, 1<<rank):
        gray = index^(index>>1)
        changed = (gray^last).bit_length()-1
        last = gray
        k, b, d = rows[changed]
        mask ^= k
        a ^= b
        c ^= d
        selected, target = mask, c
        if not target and correction:
            selected ^= correction[0]
            target = correction[1]
        if target:
            witnesses.append((selected, a, target))
    assert len(witnesses) == count
    return witnesses, info


def fixed(problem, fmask, hmask, alpha, beta, rank_limit=18):
    W, n = problem.W, problem.n
    f, h = combine(W,fmask), combine(W,hmask)
    qcolumns = [f&w for w in W[1:]]
    qfull = qcolumns+[0]*n
    multiplier = (h if alpha else 0)^(W[0] if beta else 0)
    rcolumns = [multiplier&q for q in qcolumns]+[h&w for w in W[1:]]
    generators = kernel([problem.T.reduce(r)[0] for r in rcolumns])
    images = [(k, problem.T.reduce(combine(qfull,k))[0],
               problem.B.reduce(combine(rcolumns,k))[0]) for k in generators]
    if not any(a for k,a,c in images) or not any(c for k,a,c in images):
        return [], None
    vectors, info = enumerate_images(images,rank_limit)
    witnesses = []
    for mask, a, c in vectors:
        gmask = (mask&((1<<n)-1))<<1
        vmask = (mask>>n)<<1
        q = f&combine(W,gmask)
        p = h&(combine(W,vmask)^(q if alpha else 0))
        r = p^(q if beta else 0)
        assert problem.T.reduce(q)[0] == a and not problem.T.reduce(r)[0]
        assert problem.B.reduce(r)[0] == c and Span(W+[q]).reduce(p)[0]
        witnesses.append({'gates':[[fmask,gmask],[hmask,vmask|(alpha<<len(W))]],
            'alpha':alpha, 'beta':beta, 'q_hex':hex(q), 'p_hex':hex(p),
            'auxiliary_mod_T_hex':hex(a), 'target_mod_W_hex':hex(c)})
    return witnesses, info


def search(data, rank_limit=18):
    if type(rank_limit) is not int or rank_limit < 0:
        raise ValueError('rank_limit must be a nonnegative integer')
    if not isinstance(data,dict):
        raise ValueError('input must be a JSON object')
    for key in ('W_hex','targets_hex'):
        if not isinstance(data[key],list) or not all(isinstance(v,str) for v in data[key]):
            raise ValueError(f'{key} must be an array of hexadecimal strings')
    W = [int(v,16) for v in data['W_hex']]
    targets = [int(v,16) for v in data['targets_hex']]
    if not W or W[0]<=0 or W[0]&(W[0]+1):
        raise ValueError('W[0] must be the all-one truth vector')
    if any(v<0 or v>W[0] for v in W+targets):
        raise ValueError('truth vectors must fit the declared all-one vector')
    pools = []
    for key in ('first_pool_masks','second_pool_masks'):
        raw_pool = data.get(key,data.get('pool_masks',[]))
        if not isinstance(raw_pool,list) or not raw_pool or any(type(v) is not int or v<=0 or v>=1<<len(W) or v&1 for v in raw_pool):
            raise ValueError(f'{key} must be nonzero constant-free coefficient masks in W')
        pools.append(sorted(set(raw_pool)))
    problem = Problem(W,targets)
    cases, envelopes = [], {}
    started = time.monotonic()
    for f,h in itertools.product(*pools):
        for alpha,beta in itertools.product((0,1),repeat=2):
            witnesses, info = fixed(problem,f,h,alpha,beta,rank_limit)
            if info:
                cases.append({'fmask':f,'hmask':h,'alpha':alpha,'beta':beta,**info})
            for witness in witnesses:
                envelopes.setdefault(witness['auxiliary_mod_T_hex'],witness)
    result = {'complete':all(c['enumerated'] for c in cases),
        'W_hex':data['W_hex'],'targets_hex':data['targets_hex'],
        'first_pool_masks':pools[0],'second_pool_masks':pools[1],
        'fixed_factor_cases':4*len(pools[0])*len(pools[1]),
        'feasible_factor_cases':len(cases),'cases':cases,
        'image_rank_limit':rank_limit,'envelopes':list(envelopes.values()),
        'wall_seconds':time.monotonic()-started,
        'scope':'Complete attainable auxiliary quotients within the supplied finite fixed-factor pools only when complete=true. Arbitrary g/v in W are covered; constant coefficients are removed by affine normalization. One witness per envelope, not all prefix spans or a complete target circuit.',
        'correct_27_AND_AES_found':False,'world_first_established':False}
    for key in ('source','source_sha256'):
        if key in data:
            result[key] = data[key]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image-rank-limit',type=int,default=18)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new; existing evidence is preserved')
    try:
        raw = args.input.read_bytes()
        result = search(json.loads(raw),args.image_rank_limit)
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.error(str(error))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    result['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['dependency_sha256'] = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('analyze_sbox_stage_splice.py','search_two_and_prefix.py')}
    with args.output.open('x') as output:
        output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'complete' if result['complete'] else 'rank-limit-incomplete',
        'systems':result['fixed_factor_cases'],'envelopes':len(result['envelopes'])}))


if __name__ == '__main__':
    main()
