// Exact one-product extensions of all 4096 independent-raw-input four-gate prefixes.
// This is a finite Boolean-circuit search, not a full GF(16) multiplier search.
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <unordered_set>
#include <vector>
using Mask = uint16_t;
struct F {
    std::array<uint64_t,4> x{};
    F operator^(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]^b.x[i]; return r; }
    F operator&(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]&b.x[i]; return r; }
    F& operator^=(const F& b) { for(int i=0;i<4;++i)x[i]^=b.x[i]; return *this; }
    bool operator==(const F&) const = default;
    bool bit(int i) const { return (x[i/64]>>(i%64))&1; }
    void flip(int i) { x[i/64]^=uint64_t(1)<<(i%64); }
    int top() const { for(int i=3;i>=0;--i)if(x[i])return 64*i+63-std::countl_zero(x[i]); return -1; }
};
F anf(F f) {
    for(int b=0;b<8;++b)for(int m=0;m<256;++m)
        if((m&(1<<b))&&f.bit(m^(1<<b)))f.flip(m);
    return f;
}
F combine(const std::vector<F>& rows,Mask selector) {
    F r;
    while(selector){int j=std::countr_zero(selector);r^=rows[j];selector&=selector-1;}
    return r;
}
int degree(F f) {
    int d=0;for(int m=0;m<256;++m)if(f.bit(m))d=std::max(d,std::popcount(unsigned(m)));return d;
}
uint32_t polar(F f) {
    uint32_t p=0;int k=0;
    for(int i=0;i<8;++i)for(int j=i+1;j<8;++j,++k)if(f.bit((1<<i)|(1<<j)))p|=1u<<k;
    return p;
}
int rank(uint32_t p) {
    std::array<unsigned,8> rows{},basis{};int k=0,r=0;
    for(int i=0;i<8;++i)for(int j=i+1;j<8;++j,++k)if((p>>k)&1){rows[i]^=1u<<j;rows[j]^=1u<<i;}
    for(auto v:rows)while(v){int b=31-std::countl_zero(v);if(!basis[b]){basis[b]=v;++r;break;}v^=basis[b];}
    return r;
}
struct Prefix {
    int code;
    std::array<std::array<Mask,2>,4> factors{};
    std::vector<F> truths,forms;
    Prefix(int number):code(number),truths(12) {
        for(int point=0;point<256;++point)for(int j=0;j<8;++j)if((point>>j)&1)truths[j].flip(point);
        int bits=number;
        for(int i=0;i<4;++i){
            unsigned mask=(1u<<i)-1;
            auto a=bits&mask;bits>>=i;auto b=bits&mask;bits>>=i;
            factors[i]={Mask((1u<<(2*i))|(a<<8)),Mask((1u<<(2*i+1))|(b<<8))};
            truths[8+i]=combine(truths,factors[i][0])&combine(truths,factors[i][1]);
        }
        assert(bits==0);
        for(auto t:truths)forms.push_back(anf(t));
        // The mixed derivative in each gate's fresh pair is exactly one.
        for(int i=0;i<4;++i){
            int a=1<<(2*i),b=1<<(2*i+1);
            for(int x=0;x<256;++x)
                assert((truths[8+i].bit(x)^truths[8+i].bit(x^a)^truths[8+i].bit(x^b)^truths[8+i].bit(x^a^b)));
        }
    }
};
struct Result {
    uint64_t lefts=0,pairs=0,cosets=0;
    std::array<uint64_t,9> maximum_rank_histogram{};
    std::array<uint64_t,13> right_kernel_histogram{};
    int highrank=0,Kdimension=0,maximum_rank=0;
    bool complete=false;
    Mask witness_left=0,witness_right=0,witness_decoder=0;
};
F highmask() { F r;for(int m=0;m<256;++m)if(std::popcount(unsigned(m))>2)r.flip(m);return r; }
Result scan(const Prefix& prefix) {
    const auto& forms=prefix.forms;F high=highmask();
    std::array<F,256> H{},full{};std::array<Mask,256> labels{};
    Result r;
    for(int i=0;i<4;++i){
        F value=forms[8+i]&high,wire=forms[8+i];Mask label=1<<i;
        while(value.top()>=0){int p=value.top();
            if(!labels[p]){H[p]=value;full[p]=wire;labels[p]=label;++r.highrank;break;}
            value^=H[p];wire^=full[p];label^=labels[p];
        }
    }
    std::vector<uint32_t> offsets;std::vector<Mask> offset_gates;
    std::array<uint32_t,28> K{};
    for(Mask s=0;s<16;++s){
        F f;for(int i=0;i<4;++i)if((s>>i)&1)f^=forms[8+i];
        if((f&high).top()>=0)continue;
        uint32_t p=polar(f);offsets.push_back(p);offset_gates.push_back(s);
        while(p){int bit=31-std::countl_zero(p);if(!K[bit]){K[bit]=p;++r.Kdimension;break;}p^=K[bit];}
    }
    assert(r.Kdimension==4-r.highrank&&offsets.size()==(1u<<r.Kdimension));
    // Linear projection of each basis product modulo H. Store high residue,
    // corrected quadratic coefficients, and the actual gate cancellation.
    std::array<std::array<F,12>,12> matrix{};
    std::array<std::array<uint32_t,12>,12> polar_matrix{};
    std::array<std::array<Mask,12>,12> cancel_matrix{};
    for(int i=0;i<12;++i)for(int j=0;j<12;++j){
        F f=anf(prefix.truths[i]&prefix.truths[j]);Mask cancel=0;
        for(int p=255;p>=0;--p)if(labels[p]&&f.bit(p)){f^=full[p];cancel^=labels[p];}
        matrix[i][j]=f&high;polar_matrix[i][j]=polar(f);cancel_matrix[i][j]=cancel;
    }
    std::array<F,12> columns{};std::array<uint32_t,12> polars{};std::array<Mask,12> cancellations{};
    std::unordered_set<uint32_t> seen;
    Mask previous=0;
    for(Mask left=1;left<4096;++left){
        ++r.lefts;Mask changed=previous^left;previous=left;
        while(changed){int i=std::countr_zero(changed);changed&=changed-1;
            for(int j=0;j<12;++j){columns[j]^=matrix[i][j];polars[j]^=polar_matrix[i][j];cancellations[j]^=cancel_matrix[i][j];}}
        std::array<F,256> rows{};std::array<Mask,256> selectors{};std::vector<Mask> kernel;
        for(int j=0;j<12;++j){
            F value=columns[j];Mask label=1<<j;
            while(value.top()>=0){int p=value.top();if(!selectors[p]){rows[p]=value;selectors[p]=label;break;}
                value^=rows[p];label^=selectors[p];}
            if(value.top()<0)kernel.push_back(label);
        }
        ++r.right_kernel_histogram[kernel.size()];
        std::vector<uint32_t> images;std::vector<Mask> gate_images;
        for(auto right:kernel){
            F residual;uint32_t p=0;Mask cancel=0;
            for(int j=0;j<12;++j)if((right>>j)&1){residual^=columns[j];p^=polars[j];cancel^=cancellations[j];}
            assert(residual.top()<0);images.push_back(p);gate_images.push_back(cancel);
        }
        Mask right=0,cancel=0;uint32_t p=0;unsigned oldgray=0;
        for(unsigned n=1;n<(1u<<kernel.size());++n){
            unsigned gray=n^(n>>1);int j=std::countr_zero(gray^oldgray);oldgray=gray;
            right^=kernel[j];p^=images[j];cancel^=gate_images[j];if(right<left)continue;
            ++r.pairs;uint32_t key=p;
            for(int bit=27;bit>=0;--bit)if(K[bit]&&((key>>bit)&1))key^=K[bit];
            if(!seen.insert(key).second)continue;
            ++r.cosets;int maximum=0;
            for(unsigned s=0;s<offsets.size();++s){
                int rk=rank(p^offsets[s]);maximum=std::max(maximum,rk);
                if(rk==8&&!r.witness_left){
                    r.witness_left=left;r.witness_right=right;r.witness_decoder=cancel^offset_gates[s];
                    F scalar=anf(combine(prefix.truths,left)&combine(prefix.truths,right));
                    for(int i=0;i<4;++i)if((r.witness_decoder>>i)&1)scalar^=forms[8+i];
                    assert((scalar&high).top()<0&&rank(polar(scalar))==8);
                }
            }
            ++r.maximum_rank_histogram[maximum];r.maximum_rank=std::max(r.maximum_rank,maximum);
        }
    }
    assert(seen.contains(0)&&r.lefts==4095);r.complete=true;return r;
}
void write(std::ostream& out,const Prefix& p,const Result& r) {
    out<<"{\"code\":"<<p.code<<",\"degrees\":[";
    for(int i=0;i<4;++i)out<<(i?",":"")<<degree(p.forms[8+i]);
    out<<"],\"high_rank\":"<<r.highrank<<",\"quadratic_offset_dimension\":"<<r.Kdimension
       <<",\"complete\":"<<(r.complete?"true":"false")<<",\"lefts\":"<<r.lefts<<",\"pairs\":"<<r.pairs
       <<",\"polar_cosets\":"<<r.cosets<<",\"maximum_polar_rank\":"<<r.maximum_rank<<",\"maximum_rank_histogram\":[";
    for(int i=0;i<9;++i)out<<(i?",":"")<<r.maximum_rank_histogram[i];
    out<<"],\"right_kernel_histogram\":[";
    for(int i=0;i<13;++i)out<<(i?",":"")<<r.right_kernel_histogram[i];
    out<<"],\"witness_left\":"<<r.witness_left<<",\"witness_right\":"<<r.witness_right
       <<",\"witness_gate_decoder\":"<<r.witness_decoder<<"}";
}
int main(int argc,char** argv) {
    assert(argc==4);int begin=std::stoi(argv[2]),end=std::stoi(argv[3]);
    assert(0<=begin&&begin<end&&end<=4096&&!std::ifstream(argv[1]).good());
    auto start=std::chrono::steady_clock::now();std::ofstream out(argv[1]);assert(out.good());
    // Proper quartic scalar positive control: g5=(x2+x4+x6)(g1+g2).
    Prefix quartic(1586);assert(degree(quartic.forms[11])==4);
    F Q=anf(combine(quartic.truths,84)&combine(quartic.truths,768));
    Q^=quartic.forms[8]^quartic.forms[10]^quartic.forms[11];
    assert((Q&highmask()).top()<0&&rank(polar(Q))==8);
    auto control=scan(quartic);assert(control.witness_left&&control.maximum_rank==8);
    out<<"{\"scope\":\"All ordered first-four prefixes with independent eight raw factors; one unrestricted product extension; degree-five fourth gate only. Not a complete GF16 search.\",\"begin\":"<<begin<<",\"end\":"<<end<<",\"positive_quartic_control\":";
    write(out,quartic,control);out<<",\"cases\":[";
    std::map<int,int> degrees;int quintics=0,escapes=0;
    for(int code=begin;code<end;++code){
        Prefix p(code);int d=degree(p.forms[11]);++degrees[d];assert(2<=d&&d<=5);
        if(d!=5)continue;
        Result r=scan(p);if(quintics++)out<<",";write(out,p,r);out.flush();
        if(r.witness_left)++escapes;
        if(quintics%32==0)std::cout<<"completed quintic prefixes "<<quintics<<" through code "<<code<<std::endl;
    }
    double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    out<<"],\"degree_histogram\":{";bool comma=false;
    for(auto [d,n]:degrees){if(comma)out<<",";comma=true;out<<"\""<<d<<"\":"<<n;}
    out<<"},\"quintic_prefixes\":"<<quintics<<",\"prefixes_admitting_rank8_scalar\":"<<escapes
       <<",\"complete\":true,\"algorithm_seconds\":"<<seconds<<"}\n";
    std::cout<<"{\"begin\":"<<begin<<",\"end\":"<<end<<",\"quintics\":"<<quintics<<",\"escapes\":"<<escapes<<",\"seconds\":"<<seconds<<"}"<<std::endl;
}
