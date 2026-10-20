"""Ordered raw-input kernel classes, with shifted-product wire preservation."""
import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import random
import sys
import time

HERE=None
GL2=list(itertools.permutations((1,2,3),2))


def combine(rows,mask):
    result=0
    for i,value in enumerate(rows):
        if mask>>i&1:
            result^=value
    return result


def rank(rows):
    basis={}
    for value in rows:
        while value:
            p=value.bit_length()-1
            if p not in basis:
                basis[p]=value;break
            value^=basis[p]
    return len(basis)


def inverse2(M):
    return next(N for N in GL2 if tuple(combine(M,row) for row in N)==(1,2))


LOCAL={(a,b):min((combine(M,a),combine(M,b)) for M in GL2)
       for a,b in itertools.product(range(4),repeat=2)}
TYPES=sorted(set(LOCAL.values()))
assert len(TYPES)==5
TYPE_INDEX={pair:i for i,pair in enumerate(TYPES)}
TYPE_SIZES=Counter(TYPE_INDEX[value] for value in LOCAL.values())


def type_word(x,y):
    return tuple(TYPE_INDEX[LOCAL[((x>>(2*i))&3,(y>>(2*i))&3)]] for i in range(5))


def canonical(x,y):
    return min(type_word(combine([x,y],M[0]),combine([x,y],M[1])) for M in GL2)


def relation_rows(word):
    return tuple(sum(TYPES[kind][j]<<(2*i) for i,kind in enumerate(word)) for j in range(2))


def quotient_rows(x,y):
    pivots={}
    for value in (x,y):
        while value:
            p=(value&-value).bit_length()-1
            if p not in pivots:
                pivots[p]=value;break
            value^=pivots[p]
    assert len(pivots)==2
    free=[i for i in range(10) if i not in pivots]
    rows=[]
    for i in range(10):
        value=1<<i
        for p in sorted(pivots):
            if value>>p&1:
                value^=pivots[p]
        rows.append(sum(((value>>bit)&1)<<j for j,bit in enumerate(free)))
    assert rank(rows)==8 and combine(rows,x)==combine(rows,y)==0
    return rows


def classify():
    start=time.monotonic()
    direct=Counter()
    for x in range(1,1024):
        for y in range(x+1,1024):
            if (x^y)<y:
                continue
            direct[canonical(x,y)]+=1
    assert sum(direct.values())==174251
    # A separate weighted ordered-block calculation, not a second plane traversal.
    block_counts={}
    unordered=set()
    for word in itertools.product(range(5),repeat=5):
        x,y=relation_rows(word)
        if not x or not y or x==y:
            continue
        images={type_word(combine([x,y],M[0]),combine([x,y],M[1])) for M in GL2}
        key=min(images)
        weight=sum(math.prod(TYPE_SIZES[t] for t in image) for image in images)
        assert weight%6==0
        if key in block_counts:
            assert block_counts[key]==weight//6
        block_counts[key]=weight//6
        unordered.add(min(tuple(sorted(image)) for image in images))
    assert direct==block_counts and len(direct)==621 and len(unordered)==35
    classes=[]
    for i,(word,count) in enumerate(sorted(direct.items())):
        x,y=relation_rows(word)
        classes.append({'index':i,'ordered_block_types':list(word),'relation_basis':[x,y],
                        'raw_linear_forms':quotient_rows(x,y),'relation_planes_in_class':count})
    result={'status':'pass','all_dimension2_relation_planes':sum(direct.values()),
        'ordered_block_classes':len(classes),'gate_permutation_diagnostic_classes':len(unordered),
        'diagnostic_35_not_used_as_ordered_coverage':True,
        'local_types':[{'representative':list(pair),'ordered_pair_count':TYPE_SIZES[i]} for i,pair in enumerate(TYPES)],
        'classes':classes,'two_counting_methods_agree':True,
        'algorithm_seconds':time.monotonic()-start,
        'scope':'Rank8 lists of ten raw linear forms grouped into five ordered pairs, up to input GL8 and local GL2. Shifted-product corrections still required for circuit coverage.',
        'unrestricted_eight_AND_excluded':False,'world_first_established':False}
    save(HERE/'classification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('classes','local_types')}),flush=True)


def kernel(rows):
    basis={};relations=[]
    for i,value in enumerate(rows):
        selector=1<<i
        while value:
            p=value.bit_length()-1
            if p not in basis:
                basis[p]=(value,selector);break
            old,mask=basis[p];value^=old;selector^=mask
        if not value:
            relations.append(selector)
    assert len(relations)==2
    return relations


def coordinate_map(left,right):
    # Solve left_i*y=right_i*x, obtaining each new coordinate y_j as a form of x.
    pivots={}
    for a,b in zip(left,right):
        while a:
            p=(a&-a).bit_length()-1
            if p not in pivots:
                pivots[p]=(a,b);break
            old,oldb=pivots[p];a^=old;b^=oldb
        if not a:
            assert not b
    assert len(pivots)==8
    for p in range(7,-1,-1):
        a,b=pivots[p]
        for j in range(p):
            x,y=pivots[j]
            if x>>p&1:
                pivots[j]=(x^a,y^b)
    assert [pivots[j][0] for j in range(8)]==[1<<j for j in range(8)]
    mapping=[pivots[j][1] for j in range(8)]
    assert rank(mapping)==8
    assert all(combine(mapping,a)==b for a,b in zip(left,right))
    return mapping


def normalize(factors,classes):
    raw=[side&255 for pair in factors for side in pair]
    assert rank(raw)==8
    relations=kernel(raw)
    key=canonical(*relations)
    chosen=next(M for M in GL2 if type_word(combine(relations,M[0]),combine(relations,M[1]))==key)
    x,y=combine(relations,chosen[0]),combine(relations,chosen[1])
    transformed=[];dependencies=[];shifts=[];matrices=[]
    for i in range(5):
        oldx,oldy=(x>>(2*i))&3,(y>>(2*i))&3
        desired=TYPES[key[i]]
        M=next(M for M in GL2 if (combine(inverse2(M),oldx),combine(inverse2(M),oldy))==desired)
        N=inverse2(M)
        matrices.append(list(M))
        transformed += [combine(raw[2*i:2*i+2],row) for row in M]
        dependencies.append([combine([side>>8 for side in factors[i]],row) for row in M])
        shifts.append([int(bool(N[0]&1) and bool(N[1]&1)),int(bool(N[0]&2) and bool(N[1]&2))])
        assert sum(shifts[-1])<=1
    entry=classes[key]
    canonical_raw=entry['raw_linear_forms']
    mapping=coordinate_map(canonical_raw,transformed)
    inverse=coordinate_map(mapping,[1<<i for i in range(8)])
    normalized=[[canonical_raw[2*i+j]|(dependencies[i][j]<<8) for j in range(2)] for i in range(5)]
    return {'class_index':entry['index'],'factor_masks':normalized,'output_operand_shifts':shifts,
            'new_coordinates_as_old_forms':mapping,'old_coordinates_as_new_forms':inverse,
            'local_GL2_matrices':matrices,'original_relation_basis':relations}


RAW=[sum(((p>>i)&1)<<p for p in range(256)) for i in range(8)]


def evaluate(factors,shifts=None):
    values=RAW[:]
    for i,(left,right) in enumerate(factors):
        U,V=combine(values,left),combine(values,right)
        value=U&V
        if shifts is not None:
            value^=combine([U,V],shifts[i][0]|(shifts[i][1]<<1))
        values.append(value)
    return values


def controls():
    start=time.monotonic()
    classification=json.loads((HERE/'classification.json').read_text())
    classes={tuple(row['ordered_block_types']):row for row in classification['classes']}
    local_checks=0
    for M in GL2:
        N=inverse2(M)
        sigma=(N[0]&1)*(N[1]&1)
        tau=((N[0]>>1)&1)*((N[1]>>1)&1)
        for a,b in itertools.product(range(2),repeat=2):
            u=combine([a,b],M[0]);v=combine([a,b],M[1])
            assert a*b==(u*v)^(sigma*u)^(tau*v)
            local_checks+=1
    rng=random.Random(20261020)
    examples=[[[1,2],[8,260],[32,784],[128,832],[168,768]],
              [[1,2],[8,260],[32,272],[128,320],[168,256]]]
    while len(examples)<1026:
        rows=[rng.randrange(256) for _ in range(10)]
        if rank(rows)==8:
            examples.append([[rows[2*i+j]|(rng.randrange(1<<i)<<8) for j in range(2)] for i in range(5)])
    saved=[];naive_failure=None;rows_checked=0
    for index,factors in enumerate(examples):
        normal=normalize(factors,classes)
        old=evaluate(factors)
        new=evaluate(normal['factor_masks'],normal['output_operand_shifts'])
        mapping=normal['new_coordinates_as_old_forms']
        points=[sum(((row&p).bit_count()%2)<<i for i,row in enumerate(mapping)) for p in range(256)]
        assert len(set(points))==256
        transported=[sum(((value>>points[p])&1)<<p for p in range(256)) for value in new[8:]]
        assert transported==old[8:]
        output=rng.randrange(1<<13)
        newraw=combine(normal['old_coordinates_as_new_forms'],output&255)
        newoutput=(output&~255)|newraw
        actual=combine(new,newoutput)
        assert combine(old,output)==sum(((actual>>points[p])&1)<<p for p in range(256))
        rows_checked+=256
        if naive_failure is None:
            naive=evaluate(normal['factor_masks'])
            moved=[sum(((value>>points[p])&1)<<p for p in range(256)) for value in naive[8:]]
            for prefix in range(1,6):
                expected_rank=rank([*RAW,*old[8:8+prefix]])
                joint=rank([*RAW,*old[8:8+prefix],*moved[:prefix]])
                if joint>expected_rank:
                    naive_failure={'original_factors':factors,'normalized':normal,'first_changed_prefix':prefix,
                        'old_space_dimension':expected_rank,'joint_with_naive_space_dimension':joint}
                    break
        if index<2:
            saved.append({'original_factors':factors,**normal,'all256_gate_rows_equal':True})
    assert naive_failure is not None
    result={'status':'pass','local_operand_basis_identities':local_checks,
        'rank8_circuits_normalized':len(examples),'all256_scalar_rows_per_circuit':True,
        'scalar_rows_checked':rows_checked,'all_five_gate_truths_preserved_after_input_change':True,
        'affine_output_decoders_transport_exactly':True,'saved_known_examples':saved,
        'omitting_operand_shifts_changes_prefix_space':naive_failure,
        'algorithm_seconds':time.monotonic()-start,
        'scope':'Exact wire-preserving normalization and finite controls, not a search result or novelty claim.',
        'unrestricted_eight_AND_excluded':False,'world_first_established':False}
    save(HERE/'normalization-controls.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('saved_known_examples','omitting_operand_shifts_changes_prefix_space')}),flush=True)


def save(path,value):
    with path.open('x') as handle:
        json.dump(value,handle,indent=2)
        handle.write('\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['classify','controls'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    HERE=args.output.resolve()
    if args.mode=='classify':
        HERE.mkdir(parents=True,exist_ok=False)
    {'classify':classify,'controls':controls}[args.mode]()
