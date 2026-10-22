// Independent first-seven-rank replay: symbolic Boolean polynomials, joint
// high-degree equations in (ell[7], old-gate-cancellation[4]), low-pivot rank.
// No truth-table Mobius transform or producer high-column quotient is used.
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using M = uint16_t;
struct P {
    std::array<uint64_t,2> w{};
    P operator^(const P& b) const { return {{w[0]^b.w[0],w[1]^b.w[1]}}; }
    P& operator^=(const P& b) { w[0]^=b.w[0]; w[1]^=b.w[1]; return *this; }
    bool operator==(const P&) const = default;
    bool bit(int m) const { return (w[m/64]>>(m%64))&1; }
    void toggle(int m) { w[m/64]^=uint64_t(1)<<(m%64); }
};
template<class F> void terms(const P& a,F f) {
    for(int word=0;word<2;++word) {
        auto bits=a.w[word];
        while(bits) { int b=std::countr_zero(bits); f(64*word+b); bits&=bits-1; }
    }
}
P multiply(const P& a,const P& b) {
    P p;
    terms(a,[&](int x) { terms(b,[&](int y) { p.toggle(x|y); }); });
    return p;
}
P monomial(int m) { P p; p.toggle(m); return p; }
int degree(const P& p) {
    int d=0; terms(p,[&](int m) { d=std::max(d,std::popcount(unsigned(m))); });
    return d;
}
bool evaluate(const P& p,int x) {
    bool v=false; terms(p,[&](int m) { if((x&m)==m) v=!v; }); return v;
}
uint32_t polar(const P& p) {
    uint32_t r=0; int k=0;
    for(int i=0;i<7;++i) for(int j=i+1;j<7;++j,++k)
        if(p.bit((1<<i)|(1<<j))) r|=1u<<k;
    return r;
}
std::array<unsigned,8> polar_rows(uint32_t p,M ell) {
    std::array<unsigned,8> r{}; int k=0;
    for(int i=0;i<7;++i) for(int j=i+1;j<7;++j,++k) if((p>>k)&1) {
        r[i]|=1u<<j; r[j]|=1u<<i;
    }
    for(int i=0;i<7;++i) if((ell>>i)&1) { r[i]|=128; r[7]|=1u<<i; }
    return r;
}
int rank8(uint32_t p,M ell) {
    auto r=polar_rows(p,ell); int rank=0;
    // Ordinary row reduction with leftmost columns, not high-pivot span insert.
    for(int col=0;col<8;++col) {
        int found=rank;
        while(found<8&&!((r[found]>>col)&1)) ++found;
        if(found==8) continue;
        std::swap(r[rank],r[found]);
        for(int j=rank+1;j<8;++j) if((r[j]>>col)&1) r[j]^=r[rank];
        ++rank;
    }
    return rank;
}
bool pfaffian(const std::array<unsigned,8>& r,unsigned remaining) {
    if(!remaining) return true;
    int i=std::countr_zero(remaining); unsigned rest=remaining^(1u<<i);
    bool result=false;
    for(unsigned partners=r[i]&rest;partners;partners&=partners-1) {
        int j=std::countr_zero(partners);
        result^=pfaffian(r,rest^(1u<<j));
    }
    return result;
}
std::array<M,8> quotient(int relation) {
    int pivot=std::bit_width(unsigned(relation))-1,next=0;
    std::array<M,8> q{};
    for(int j=0;j<8;++j) if(j!=pivot) q[j]=1<<next++;
    for(int j=0;j<8;++j) if(j!=pivot&&((relation>>j)&1)) q[pivot]^=q[j];
    return q;
}
using Factors=std::array<std::array<M,2>,4>;
Factors factors(const std::array<M,8>& q,int code) {
    Factors f{}; int b=0;
    for(int g=0;g<4;++g) for(int side=0;side<2;++side) {
        f[g][side]=q[2*g+side];
        for(int j=0;j<g;++j,++b) if((code>>b)&1) f[g][side]^=1<<(7+j);
    }
    assert(b==12); return f;
}
P combine(const std::vector<P>& v,M selector) {
    P p;
    while(selector) { int j=std::countr_zero(selector); p^=v[j]; selector&=selector-1; }
    return p;
}
std::vector<P> polynomials(const Factors& f) {
    std::vector<P> v;
    for(int j=0;j<7;++j) v.push_back(monomial(1<<j));
    for(auto pair:f) v.push_back(multiply(combine(v,pair[0]),combine(v,pair[1])));
    return v;
}
std::vector<M> nullspace(const std::array<M,128>& equations,int variables) {
    std::array<M,11> rows{};
    for(M row:equations) while(row) {
        int col=std::countr_zero(row);
        if(rows[col]) row^=rows[col]; else { rows[col]=row; break; }
    }
    std::vector<M> basis;
    for(int free=0;free<variables;++free) if(!rows[free]) {
        M v=1<<free;
        for(int col=variables-1;col>=0;--col)
            if(rows[col]&&(std::popcount(unsigned(rows[col]&v))&1)) v^=1<<col;
        basis.push_back(v);
    }
    return basis;
}
struct Projection { std::vector<M> lifted,zero; };
Projection project(const std::vector<M>& joint) {
    std::array<M,7> lifted{}; Projection result;
    for(M v:joint) {
        M ell=v&127;
        while(ell) {
            int col=std::countr_zero(ell);
            if(lifted[col]) { v^=lifted[col]; ell=v&127; }
            else { lifted[col]=v; break; }
        }
        if(!ell) result.zero.push_back(v);
    }
    for(M v:lifted) if(v) result.lifted.push_back(v);
    return result;
}
struct Counts {
    uint64_t prefixes=0,quintic_prefixes=0,B_cases=0,eligible_nonzero_ell=0,rank_tests=0,rank8_results=0;
    std::array<uint64_t,6> g4_degree_histogram{};
    std::array<uint64_t,4> high_rank_histogram{};
    std::array<uint64_t,8> kernel_dimension_histogram{};
    std::array<uint64_t,9> scalar_polar_rank_histogram{};
    void add(const Counts& c) {
        prefixes+=c.prefixes; quintic_prefixes+=c.quintic_prefixes; B_cases+=c.B_cases;
        eligible_nonzero_ell+=c.eligible_nonzero_ell; rank_tests+=c.rank_tests; rank8_results+=c.rank8_results;
        for(int j=0;j<6;++j) g4_degree_histogram[j]+=c.g4_degree_histogram[j];
        for(int j=0;j<4;++j) high_rank_histogram[j]+=c.high_rank_histogram[j];
        for(int j=0;j<8;++j) kernel_dimension_histogram[j]+=c.kernel_dimension_histogram[j];
        for(int j=0;j<9;++j) scalar_polar_rank_histogram[j]+=c.scalar_polar_rank_histogram[j];
    }
};
struct Witness { int B; M ell,decode; };
void replay(const Factors& f,const Witness& w) {
    auto polys=polynomials(f); P B;
    for(int g=0;g<4;++g) if((w.B>>g)&1) B^=polys[7+g];
    P q=multiply(combine(polys,w.ell),B);
    for(int g=0;g<4;++g) if((w.decode>>g)&1) q^=polys[7+g];
    assert(degree(q)<=2&&rank8(polar(q),w.ell)==8);
    assert(pfaffian(polar_rows(polar(q),w.ell),255));
    // Evaluate the original gate DAG on all 256 assignments, then compare with
    // the symbolic degree-two expression, including the fresh-input cross term.
    for(int x=0;x<256;++x) {
        unsigned wires=x&127;
        for(int g=0;g<4;++g) {
            bool l=std::popcount(unsigned(wires&f[g][0]))&1;
            bool r=std::popcount(unsigned(wires&f[g][1]))&1;
            if(l&&r) wires|=1u<<(7+g);
            assert(bool((wires>>(7+g))&1)==evaluate(polys[7+g],x&127));
        }
        bool ell=std::popcount(unsigned(wires&w.ell))&1;
        bool b=std::popcount(unsigned((wires>>7)&w.B))&1;
        bool decoded=ell*bool(((x>>7)&1)^b);
        decoded^=std::popcount(unsigned((wires>>7)&w.decode))&1;
        assert(decoded==(evaluate(q,x&127)^(ell*bool(x>>7))));
    }
}
std::vector<Witness> scan(const std::vector<P>& v,Counts& c,bool retain) {
    std::array<M,128> base{};
    for(int g=0;g<4;++g) terms(v[7+g],[&](int m) {
        if(std::popcount(unsigned(m))>2) base[m]^=1<<(7+g);
    });
    std::array<M,128> oldeq{};
    for(int m=0;m<128;++m) oldeq[m]=base[m]>>7;
    int kdim=nullspace(oldeq,4).size();
    ++c.high_rank_histogram[4-kdim];
    std::array<std::array<P,4>,7> products{};
    for(int j=0;j<7;++j) for(int g=0;g<4;++g)
        terms(v[7+g],[&](int m) { products[j][g].toggle(m|(1<<j)); });
    std::vector<Witness> witnesses;
    for(int b=0;b<16;++b) {
        ++c.B_cases; std::array<P,11> columns{};
        auto eq=base;
        for(int j=0;j<7;++j) {
            for(int g=0;g<4;++g) if((b>>g)&1) columns[j]^=products[j][g];
            terms(columns[j],[&](int m) {
                if(std::popcount(unsigned(m))>2) eq[m]^=1<<j;
            });
        }
        for(int g=0;g<4;++g) columns[7+g]=v[7+g];
        auto joint=nullspace(eq,11); auto projected=project(joint);
        assert(int(projected.zero.size())==kdim);
        int edim=projected.lifted.size(); ++c.kernel_dimension_histogram[edim];
        auto residue=[&](M sol) {
            P q; for(int j=0;j<11;++j) if((sol>>j)&1) q^=columns[j];
            assert(degree(q)<=2); return polar(q);
        };
        std::array<uint32_t,7> ep{}; std::array<uint32_t,4> kp{};
        for(int j=0;j<edim;++j) ep[j]=residue(projected.lifted[j]);
        for(int j=0;j<kdim;++j) kp[j]=residue(projected.zero[j]);
        std::array<uint32_t,16> offsets{}; std::array<M,16> ksol{};
        for(int s=1;s<(1<<kdim);++s) {
            int bit=std::countr_zero(unsigned(s)); int prev=s^(1<<bit);
            offsets[s]=offsets[prev]^kp[bit]; ksol[s]=ksol[prev]^projected.zero[bit];
        }
        uint32_t p=0; M sol=0;
        for(int index=1;index<(1<<edim);++index) {
            int bit=std::countr_zero(unsigned(index));
            p^=ep[bit]; sol^=projected.lifted[bit]; M ell=sol&127;
            assert(ell); ++c.eligible_nonzero_ell;
            for(int k=0;k<(1<<kdim);++k) {
                int rank=rank8(p^offsets[k],ell); ++c.rank_tests; ++c.scalar_polar_rank_histogram[rank];
                if(rank==8) {
                    ++c.rank8_results;
                    if(retain||witnesses.empty()) witnesses.push_back({b,ell,M((sol^ksol[k])>>7)});
                }
            }
        }
    }
    return witnesses;
}
template<size_t N> void array_json(std::ostream& o,const std::array<uint64_t,N>& a) {
    o<<'['; for(size_t j=0;j<N;++j) { if(j)o<<','; o<<a[j]; } o<<']';
}
void counts_json(std::ostream& o,const Counts& c) {
    o<<"\"prefixes\":"<<c.prefixes<<",\"quintic_prefixes\":"<<c.quintic_prefixes
     <<",\"B_cases\":"<<c.B_cases<<",\"eligible_nonzero_ell\":"<<c.eligible_nonzero_ell
     <<",\"rank_tests\":"<<c.rank_tests<<",\"rank8_results\":"<<c.rank8_results;
    o<<",\"g4_degree_histogram\":"; array_json(o,c.g4_degree_histogram);
    o<<",\"high_rank_histogram\":"; array_json(o,c.high_rank_histogram);
    o<<",\"kernel_dimension_histogram\":"; array_json(o,c.kernel_dimension_histogram);
    o<<",\"scalar_polar_rank_histogram\":"; array_json(o,c.scalar_polar_rank_histogram);
}
void controls(std::ostream& out) {
    uint64_t identities=0,quotient_vectors=0,kernel_checks=0,rank_checks=0;
    for(int a=0;a<128;++a) for(int b=0;b<128;++b) {
        assert(multiply(monomial(a),monomial(b))==monomial(a|b)); ++identities;
    }
    for(int relation=1;relation<256;++relation) {
        auto q=quotient(relation);
        for(int mask=0;mask<256;++mask) {
            M image=0; for(int j=0;j<8;++j) if((mask>>j)&1) image^=q[j];
            assert((image==0)==(mask==0||mask==relation)); ++quotient_vectors;
        }
    }
    uint32_t rng=0x917af41u;
    auto next=[&]() { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; };
    for(int test=0;test<4096;++test) {
        // Exhaustively check each 11-variable small system and its projection.
        std::array<M,128> eq{};
        for(int row=0;row<8;++row) eq[row]=next()&2047;
        auto kernel=nullspace(eq,11); auto projected=project(kernel);
        std::array<bool,2048> generated{}; std::array<bool,128> generated_ell{};
        for(unsigned s=0;s<(1u<<kernel.size());++s) {
            M v=0; for(unsigned j=0;j<kernel.size();++j) if((s>>j)&1) v^=kernel[j];
            assert(!generated[v]); generated[v]=true;
        }
        for(unsigned s=0;s<(1u<<projected.lifted.size());++s) {
            M v=0; for(unsigned j=0;j<projected.lifted.size();++j) if((s>>j)&1) v^=projected.lifted[j];
            assert(generated[v]); assert(!generated_ell[v&127]); generated_ell[v&127]=true;
        }
        for(int v=0;v<2048;++v) {
            bool satisfies=true; for(M row:eq) if(std::popcount(unsigned(row&v))&1) satisfies=false;
            assert(satisfies==generated[v]); if(satisfies) assert(generated_ell[v&127]); ++kernel_checks;
        }
        auto p=next()&((1u<<21)-1); auto ell=next()&127;
        assert((rank8(p,ell)==8)==pfaffian(polar_rows(p,ell),255)); ++rank_checks;
    }
    Factors f{{{1,2},{8,132},{32,400},{384,104}}};
    auto v=polynomials(f); assert(degree(v[10])==4);
    replay(f,{3,64,13}); Counts c; auto ws=scan(v,c,true); assert(!ws.empty());
    for(const auto& w:ws) replay(f,w);
    out<<"{\"pass\":true,\"symbolic_monomial_products\":"<<identities
       <<",\"quotient_vectors_checked\":"<<quotient_vectors<<",\"kernel_assignment_checks\":"<<kernel_checks
       <<",\"rank_pfaffian_checks\":"<<rank_checks<<",\"nonlinear_B_positive_control\":true"
       <<",\"positive_witnesses_replayed_256_rows_each\":"<<ws.size()<<','; counts_json(out,c); out<<"}\n";
}
int main(int argc,char** argv) {
    assert(argc==3||argc==5); std::string mode=argv[1];
    assert(!std::ifstream(argv[2]).good()); std::ofstream out(argv[2]); assert(out.good());
    auto start=std::chrono::steady_clock::now();
    if(mode=="--controls") { assert(argc==3); controls(out); std::cout<<"controls PASS\n"; return 0; }
    assert(mode=="--scan"&&argc==5);
    int first=std::stoi(argv[3]),last=std::stoi(argv[4]); assert(first>=1&&last<=255&&first<=last);
    Counts total; uint64_t witnesses=0;
    out<<"{\"relation_first\":"<<first<<",\"relation_last\":"<<last<<",\"relations\":[";
    for(int relation=first;relation<=last;++relation) {
        Counts c; auto q=quotient(relation);
        for(int code=0;code<4096;++code) {
            auto f=factors(q,code); auto v=polynomials(f); int d=degree(v[10]); assert(d<=5);
            ++c.prefixes; ++c.g4_degree_histogram[d]; if(d!=5) continue;
            ++c.quintic_prefixes; auto ws=scan(v,c,false);
            if(!ws.empty()) {
                ++witnesses; replay(f,ws[0]);
                std::cerr<<"witness relation="<<relation<<" code="<<code<<" B="<<ws[0].B
                         <<" ell="<<ws[0].ell<<" decode="<<ws[0].decode<<'\n';
            }
        }
        if(relation!=first) out<<',';
        out<<"{\"relation\":"<<relation<<','; counts_json(out,c); out<<'}'; out.flush(); total.add(c);
        std::cout<<"relation "<<relation<<" quintics "<<c.quintic_prefixes<<" rank8 "<<c.rank8_results<<std::endl;
    }
    double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    out<<"],\"complete\":true,\"totals\":{"; counts_json(out,total);
    out<<"},\"witness_prefixes\":"<<witnesses<<",\"algorithm_seconds\":"<<seconds<<"}\n";
    std::cout<<"complete seconds="<<seconds<<" prefixes="<<total.prefixes<<" quintics="<<total.quintic_prefixes
             <<" rank8="<<total.rank8_results<<std::endl;
}
