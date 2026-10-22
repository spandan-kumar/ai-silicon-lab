// Exact scalar-Q5 scan when the first eight raw operand covectors have rank 7.
// No gate permutation quotient. See --controls for an admitted nonlinear-B case.
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using Mask = uint16_t;
struct F {
    std::array<uint64_t, 2> x{};
    F operator^(const F& b) const { return {{x[0]^b.x[0], x[1]^b.x[1]}}; }
    F operator&(const F& b) const { return {{x[0]&b.x[0], x[1]&b.x[1]}}; }
    F& operator^=(const F& b) { x[0]^=b.x[0]; x[1]^=b.x[1]; return *this; }
    bool bit(int p) const { return (x[p/64]>>(p%64))&1; }
    void set(int p) { x[p/64]^=uint64_t(1)<<(p%64); }
    int top() const {
        if(x[1]) return 127-std::countl_zero(x[1]);
        if(x[0]) return 63-std::countl_zero(x[0]);
        return -1;
    }
};
F anf(F f) {
    constexpr uint64_t masks[] = {0x5555555555555555ull,0x3333333333333333ull,
        0x0f0f0f0f0f0f0f0full,0x00ff00ff00ff00ffull,0x0000ffff0000ffffull,
        0x00000000ffffffffull};
    for(int b=0;b<6;++b) for(auto& v:f.x) v^=(v&masks[b])<<(1<<b);
    f.x[1]^=f.x[0];
    return f;
}
F combine(const std::vector<F>& v, Mask m) {
    F r;
    while(m) { int j=std::countr_zero(m); r^=v[j]; m&=m-1; }
    return r;
}
int degree(const F& a) {
    int d=0;
    for(int p=0;p<128;++p) if(a.bit(p)) d=std::max(d,std::popcount(unsigned(p)));
    return d;
}
uint32_t polar(const F& a) {
    uint32_t p=0; int k=0;
    for(int i=0;i<7;++i) for(int j=i+1;j<7;++j,++k)
        if(a.bit((1<<i)|(1<<j))) p|=1u<<k;
    return p;
}
int rank8(uint32_t p, Mask ell) {
    std::array<unsigned,8> rows{},basis{}; int k=0,r=0;
    for(int i=0;i<7;++i) for(int j=i+1;j<7;++j,++k) if((p>>k)&1) {
        rows[i]^=1u<<j; rows[j]^=1u<<i;
    }
    for(int i=0;i<7;++i) if((ell>>i)&1) { rows[i]^=128; rows[7]^=1u<<i; }
    for(auto v:rows) while(v) {
        int b=31-std::countl_zero(v);
        if(!basis[b]) { basis[b]=v; ++r; break; }
        v^=basis[b];
    }
    return r;
}
std::array<F,7> raw;
F highmask;
void initialize() {
    for(int b=0;b<7;++b) for(int p=0;p<128;++p) if((p>>b)&1) raw[b].set(p);
    for(int p=0;p<128;++p) if(std::popcount(unsigned(p))>2) highmask.set(p);
    for(int p=0;p<128;++p) {
        F monomial; monomial.set(p); assert(anf(anf(monomial)).x==monomial.x);
    }
    assert(rank8((1u<<0)|(1u<<11)|(1u<<18),64)==8);
    assert(rank8(0,1)==2 && rank8(0,0)==0);
}
std::array<Mask,8> quotient(int relation) {
    assert(relation>=1&&relation<=255);
    int pivot=31-std::countl_zero(unsigned(relation)), next=0;
    std::array<Mask,8> q{};
    for(int j=0;j<8;++j) if(j!=pivot) q[j]=1<<next++;
    for(int j=0;j<8;++j) if(j!=pivot&&((relation>>j)&1)) q[pivot]^=q[j];
    Mask check=0;
    for(int j=0;j<8;++j) if((relation>>j)&1) check^=q[j];
    assert(check==0);
    return q;
}
using Factors = std::array<std::array<Mask,2>,4>;
Factors make_factors(const std::array<Mask,8>& q, int code) {
    Factors f{}; int bit=0;
    for(int g=0;g<4;++g) for(int side=0;side<2;++side) {
        f[g][side]=q[2*g+side];
        for(int j=0;j<g;++j,++bit) if((code>>bit)&1) f[g][side]^=1<<(7+j);
    }
    assert(bit==12); return f;
}
std::vector<F> truths(const Factors& factors) {
    std::vector<F> v(raw.begin(),raw.end());
    for(const auto& f:factors) v.push_back(combine(v,f[0])&combine(v,f[1]));
    return v;
}
int span_rank(const std::vector<F>& v) {
    std::array<F,128> rows{}; int r=0;
    for(auto f:v) while(f.top()>=0) {
        int p=f.top();
        if(rows[p].top()<0) { rows[p]=f; ++r; break; }
        f^=rows[p];
    }
    return r;
}
struct Prefix {
    std::vector<F> t,a;
    std::array<F,128> hrows{},fullrows{};
    std::array<Mask,128> labels{};
    std::vector<Mask> klab;
    std::vector<uint32_t> koff;
    std::vector<Mask> kselect;
    std::array<std::array<F,4>,7> prod{};
    int hrank=0;
    explicit Prefix(const Factors& f): t(truths(f)) {
        for(auto v:t) a.push_back(anf(v));
        assert(span_rank(t)==11);
        for(int j=0;j<4;++j) {
            F h=a[7+j]&highmask, full=a[7+j]; Mask label=1<<j;
            while(h.top()>=0) {
                int p=h.top();
                if(!labels[p]) {
                    hrows[p]=h; fullrows[p]=full; labels[p]=label; ++hrank; break;
                }
                h^=hrows[p]; full^=fullrows[p]; label^=labels[p];
            }
            if(h.top()<0) klab.push_back(label);
        }
        assert(hrank<=3&&int(klab.size())+hrank==4);
        for(unsigned s=0;s<(1u<<klab.size());++s) {
            Mask label=0; for(unsigned j=0;j<klab.size();++j) if((s>>j)&1) label^=klab[j];
            F f; for(int j=0;j<4;++j) if((label>>j)&1) f^=a[7+j];
            assert((f&highmask).top()<0); koff.push_back(polar(f)); kselect.push_back(label);
        }
        for(int j=0;j<7;++j) for(int g=0;g<4;++g) prod[j][g]=anf(t[j]&t[7+g]);
    }
    F high_reduce(F h) const {
        for(int p=127;p>=0;--p) if(labels[p]&&h.bit(p)) h^=hrows[p];
        return h;
    }
    std::pair<F,Mask> cancel(F f) const {
        Mask label=0;
        for(int p=127;p>=0;--p) if(labels[p]&&f.bit(p)) { f^=fullrows[p]; label^=labels[p]; }
        assert((f&highmask).top()<0); return {f,label};
    }
};
struct Counts {
    uint64_t prefixes=0,quintics=0,bcases=0,eligible=0,ranktests=0,escapes=0;
    std::array<uint64_t,6> degreehist{};
    std::array<uint64_t,4> hrankhist{};
    std::array<uint64_t,9> rankhist{};
    std::array<uint64_t,8> kernelhist{};
};
struct Witness { bool found=false; int b=0; Mask ell=0,decode=0; };
void verify_witness(const Factors& f, const Witness& w) {
    auto t=truths(f); F B;
    for(int g=0;g<4;++g) if((w.b>>g)&1) B^=t[7+g];
    auto q=anf(combine(t,w.ell)&B);
    for(int g=0;g<4;++g) if((w.decode>>g)&1) q^=anf(t[7+g]);
    assert(degree(q)<=2 && rank8(polar(q),w.ell)==8);
    // Direct full-256 evaluation, independently checking quadratic high terms.
    std::array<unsigned char,256> truth{};
    for(int p=0;p<256;++p) {
        int old=p&127, x=(p>>7)&1;
        int v=std::popcount(unsigned(old&w.ell))&1;
        truth[p]=v*(x+int(B.bit(old))%2)%2;
        for(int g=0;g<4;++g) if((w.decode>>g)&1) truth[p]^=t[7+g].bit(old);
    }
    for(int b=0;b<8;++b) for(int p=0;p<256;++p) if((p>>b)&1) truth[p]^=truth[p^(1<<b)];
    for(int p=0;p<256;++p) {
        assert(!truth[p]||std::popcount(unsigned(p))<=2);
        if(p<128) assert(bool(truth[p])==q.bit(p));
        else assert(bool(truth[p])==(std::popcount(unsigned(p))==2&&((w.ell>>(std::countr_zero(unsigned(p^128))))&1)));
    }
}
Witness scan_prefix(const Prefix& p, Counts& c) {
    Witness w;
    for(int b=0;b<16;++b) {
        ++c.bcases;
        std::array<F,7> full{}, quot{};
        for(int j=0;j<7;++j) {
            for(int g=0;g<4;++g) if((b>>g)&1) full[j]^=p.prod[j][g];
            quot[j]=p.high_reduce(full[j]&highmask);
        }
        std::array<F,128> rows{}; std::array<Mask,128> labels{};
        std::vector<Mask> kernel;
        for(int j=0;j<7;++j) {
            F v=quot[j]; Mask label=1<<j;
            while(v.top()>=0) {
                int top=v.top();
                if(!labels[top]) { rows[top]=v; labels[top]=label; break; }
                v^=rows[top]; label^=labels[top];
            }
            if(v.top()<0) kernel.push_back(label);
        }
        ++c.kernelhist[kernel.size()];
        for(unsigned s=1;s<(1u<<kernel.size());++s) {
            Mask ell=0; for(unsigned j=0;j<kernel.size();++j) if((s>>j)&1) ell^=kernel[j];
            assert(ell!=0); ++c.eligible;
            F f,h;
            for(int j=0;j<7;++j) if((ell>>j)&1) { f^=full[j]; h^=quot[j]; }
            assert(h.top()<0);
            auto [q,label]=p.cancel(f); uint32_t polarq=polar(q);
            for(unsigned k=0;k<p.koff.size();++k) {
                int rank=rank8(polarq^p.koff[k],ell); ++c.ranktests; ++c.rankhist[rank];
                if(rank==8) {
                    ++c.escapes;
                    if(!w.found) w={true,b,ell,Mask(label^p.kselect[k])};
                }
            }
        }
    }
    return w;
}
template<size_t N> void json_array(std::ostream& o,const std::array<uint64_t,N>& a) {
    o<<'['; for(size_t j=0;j<N;++j) { if(j)o<<','; o<<a[j]; } o<<']';
}
void json_counts(std::ostream& o,const Counts& c) {
    o<<"\"prefixes\":"<<c.prefixes<<",\"quintic_prefixes\":"<<c.quintics
     <<",\"B_cases\":"<<c.bcases<<",\"eligible_nonzero_ell\":"<<c.eligible
     <<",\"rank_tests\":"<<c.ranktests<<",\"rank8_results\":"<<c.escapes
     <<",\"g4_degree_histogram\":"; json_array(o,c.degreehist);
    o<<",\"high_rank_histogram\":"; json_array(o,c.hrankhist);
    o<<",\"kernel_dimension_histogram\":"; json_array(o,c.kernelhist);
    o<<",\"scalar_polar_rank_histogram\":"; json_array(o,c.rankhist);
}
int main(int argc,char** argv) {
    initialize(); assert(argc==3||argc==5);
    std::string mode=argv[1]; const char* path=argv[2];
    assert(!std::ifstream(path).good()); std::ofstream out(path); assert(out.good());
    auto start=std::chrono::steady_clock::now();
    if(mode=="--controls") {
        assert(argc==3);
        Factors f{{{1,2},{8,132},{32,400},{384,104}}};
        Prefix p(f); assert(degree(p.a[10])==4);
        Witness exact{true,3,64,13}; verify_witness(f,exact);
        Counts c; auto w=scan_prefix(p,c); assert(w.found&&c.escapes>0); verify_witness(f,w);
        // Every quotient has precisely its intended one-dimensional kernel.
        uint64_t qchecks=0;
        for(int r=1;r<256;++r) {
            auto q=quotient(r);
            for(int v=0;v<256;++v) {
                Mask image=0; for(int j=0;j<8;++j) if((v>>j)&1) image^=q[j];
                assert((image==0)==(v==0||v==r)); ++qchecks;
            }
        }
        out<<"{\"pass\":true,\"quotient_vectors_checked\":"<<qchecks
           <<",\"nonlinear_B_positive_control\":true,\"witness_B\":"<<w.b
           <<",\"witness_ell\":"<<w.ell<<",\"witness_decode\":"<<w.decode<<',';
        json_counts(out,c); out<<"}\n";
        std::cout<<"controls PASS; rank8 results "<<c.escapes<<std::endl;
    } else {
        assert(mode=="--scan"&&argc==5);
        int first=std::stoi(argv[3]),last=std::stoi(argv[4]); assert(1<=first&&first<=last&&last<=255);
        Counts total; uint64_t witness_count=0;
        out<<"{\"relation_first\":"<<first<<",\"relation_last\":"<<last<<",\"relations\":[";
        for(int relation=first;relation<=last;++relation) {
            Counts c; auto q=quotient(relation);
            for(int code=0;code<4096;++code) {
                auto f=make_factors(q,code); auto t=truths(f);
                int d=degree(anf(t[10])); assert(d<=5); ++c.prefixes; ++c.degreehist[d];
                if(d!=5) continue;
                ++c.quintics; Prefix p(f); ++c.hrankhist[p.hrank]; auto w=scan_prefix(p,c);
                if(w.found) {
                    verify_witness(f,w); ++witness_count;
                    std::cerr<<"rank8 witness relation="<<relation<<" code="<<code
                             <<" B="<<w.b<<" ell="<<w.ell<<" decode="<<w.decode<<'\n';
                }
            }
            if(relation!=first) out<<',';
            out<<"{\"relation\":"<<relation<<','; json_counts(out,c); out<<'}'; out.flush();
            total.prefixes+=c.prefixes; total.quintics+=c.quintics; total.bcases+=c.bcases;
            total.eligible+=c.eligible; total.ranktests+=c.ranktests; total.escapes+=c.escapes;
            for(size_t j=0;j<6;++j) total.degreehist[j]+=c.degreehist[j];
            for(size_t j=0;j<4;++j) total.hrankhist[j]+=c.hrankhist[j];
            for(size_t j=0;j<8;++j) total.kernelhist[j]+=c.kernelhist[j];
            for(size_t j=0;j<9;++j) total.rankhist[j]+=c.rankhist[j];
            std::cout<<"relation "<<relation<<" quintics "<<c.quintics<<" rank8 "<<c.escapes<<std::endl;
        }
        double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        out<<"],\"complete\":true,\"totals\":{"; json_counts(out,total);
        out<<"},\"witness_prefixes\":"<<witness_count<<",\"algorithm_seconds\":"<<sec<<"}\n";
        std::cout<<"complete seconds="<<sec<<" prefixes="<<total.prefixes
                 <<" quintics="<<total.quintics<<" rank8="<<total.escapes<<std::endl;
    }
}
