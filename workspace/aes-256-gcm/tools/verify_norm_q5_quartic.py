"""Complete symbolic product inventory for the new specified quartic prefix family."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'workspace/aes-256-gcm/tools'))
from verify_norm_family import add, low_basis, multiply, nullspace, truth
from verify_norm_rankone_family import packed_polar, packed_rank, reduce


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,help='Optional fresh JSON file for the complete inventory.')
    args=parser.parse_args()
    start=time.monotonic()
    P=[1<<(1<<i) for i in range(8)]
    factors=[[1,2],[8,260],[32,784],[128,832],[168,768]]
    for left,right in factors:
        P.append(multiply(add(P,left),add(P,right)))
    Q=add(P,7424)
    expected=add([multiply(P[2*i],P[2*i+1]) for i in range(4)],15)
    assert Q==expected and packed_rank(packed_polar(Q))==8
    assert [max(m.bit_count() for m in range(256) if form>>m&1)
            for form in P[8:]]==[2,3,4,4,4]
    high=sum(1<<m for m in range(256) if m.bit_count()>2)
    rows={}
    for form in P[8:]:
        h=form&high
        while h:
            pivot=(h&-h).bit_length()-1
            if pivot not in rows:
                rows[pivot]=h,form
                break
            old,full=rows[pivot]
            h^=old;form^=full
    assert len(rows)==3
    selectors=[s for s in range(32) if not (add(P[8:],s)&high)]
    assert selectors==[0,1,28,29]
    K=[packed_polar(add(P[8:],s)) for s in selectors]
    Kbasis=low_basis(K)
    assert len(Kbasis)==2
    q=packed_polar(Q)
    assert q in K and not any(packed_rank(k)==packed_rank(k^q)==8 for k in K)
    products=[[multiply(a,b) for b in P] for a in P]
    ts=list(map(truth,P))
    assert all(truth(products[i][j])==(ts[i]&ts[j]) for i,j in itertools.product(range(13),repeat=2))
    a,b,c,d,e,f,g,h=P[:8]
    positive=multiply(a^c,f^h)^multiply(e^g,b^d)^multiply(a,b)^multiply(e,f)
    assert packed_rank(packed_polar(positive))==packed_rank(packed_polar(positive^Q))==8
    eligible=0;cosets={};histogram={}
    columns=[0]*13;previous=0
    for left in range(1,8192):
        changed=previous^left
        for i in range(13):
            if changed>>i&1:
                columns=[x^y for x,y in zip(columns,products[i])]
        previous=left
        quotient=[]
        for value in columns:
            value&=high
            for bit in sorted(rows):
                if value>>bit&1:
                    value^=rows[bit][0]
            quotient.append(value)
        kernel=nullspace(quotient)
        histogram[len(kernel)]=histogram.get(len(kernel),0)+1
        rights=[0]
        for vector in kernel:
            rights += [old^vector for old in rights]
        for right in rights[1:]:
            if right<left:
                continue
            eligible+=1
            residue=add(columns,right)
            for bit in sorted(rows):
                if residue>>bit&1:
                    residue^=rows[bit][1]
            assert not residue&high
            key=reduce(packed_polar(residue),Kbasis)
            if key not in cosets:
                ranks={offset:packed_rank(key^offset) for offset in K}
                escapes=[offset for offset in K if ranks[offset]==ranks[offset^q]==8]
                cosets[key]={'K_corrected_polar_ranks':[ranks[k] for k in K],
                             'bent_pair_offsets':escapes}
    assert 0 in cosets
    escaped=[key for key,value in cosets.items() if value['bent_pair_offsets']]
    inventory=sorted(cosets.items())
    result={'status':'complete','nonzero_left_forms':8191,
        'eligible_unordered_pairs':eligible,'quadratic_polar_cosets':len(cosets),
        'cosets_admitting_rank8_pair':len(escaped),'zero_coset_checked':True,
        'factor_masks':factors,'scalar_decoder':7424,'higher_degree_rank':3,
        'K_dimension':2,'K_gate_selectors':selectors,'K_packed_polars':K,
        'right_kernel_dimension_histogram':histogram,
        'minimum_corrected_rank_histogram':{str(r):sum(min(value['K_corrected_polar_ranks'])==r
            for value in cosets.values()) for r in range(0,9,2)},
        'coset_inventory_sha256':hashlib.sha256(json.dumps(inventory,separators=(',',':')).encode()).hexdigest(),
        'coset_inventory':inventory,'algorithm_seconds':time.monotonic()-start,
        'scope':'Specified five-gate quartic prefix and all invertible affine input images jointly transporting Q and the field target. Not all degree4 or scalar-first-at-five prefixes.',
        'unrestricted_eight_AND_excluded':False,'world_first_established':False}
    assert eligible==48976 and len(cosets)==11359 and not escaped
    if args.inventory is not None:
        with args.inventory.open('x') as handle:
            json.dump(result,handle,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='coset_inventory'}),flush=True)


if __name__=='__main__':
    main()
