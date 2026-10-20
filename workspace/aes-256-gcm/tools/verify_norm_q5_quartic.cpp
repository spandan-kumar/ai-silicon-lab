// Independent truth/Mobius/high-pivot replay of the specified quartic prefix.
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <unordered_set>
#include <vector>
using U = uint16_t;
struct F {
    std::array<uint64_t,4> x{};
    bool operator==(const F&) const = default;
    F operator^(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]^b.x[i]; return r; }
    F operator&(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]&b.x[i]; return r; }
    F& operator^=(const F& b) { for(int i=0;i<4;++i)x[i]^=b.x[i]; return *this; }
    bool bit(int i) const { return (x[i/64]>>(i%64))&1; }
    void set(int i) { x[i/64]^=uint64_t(1)<<(i%64); }
    int top() const { for(int i=3;i>=0;--i)if(x[i])return 64*i+63-std::countl_zero(x[i]); return -1; }
};
F anf(F f) {
    for(int b=0;b<8;++b) for(int m=0;m<256;++m)
        if((m&(1<<b))&&f.bit(m^(1<<b)))f.set(m);
    return f;
}
F combine(const std::vector<F>& c,U mask) {
    F r; while(mask){int i=std::countr_zero(mask);r^=c[i];mask&=mask-1;}return r;
}
uint32_t polar(const F& f) {
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
struct Result {
    uint64_t lefts=0,pairs=0,cosets=0;
    bool complete=false,escape=false;
    U left=0,right=0;
    int cancel=0,offset=0;
};
Result scan() {
    std::vector<F> truths(13), forms;
    for(int point=0;point<256;++point){
        for(int b=0;b<8;++b)if((point>>b)&1)truths[b].set(point);
    }
    const std::array<std::array<U,2>,5> factors{{{1,2},{8,260},{32,784},{128,832},{168,768}}};
    for(int i=0;i<5;++i)truths[8+i]=combine(truths,factors[i][0])&combine(truths,factors[i][1]);
    for(auto t:truths)forms.push_back(anf(t));
    F highmask;for(int m=0;m<256;++m)if(std::popcount(unsigned(m))>2)highmask.set(m);
    std::array<F,256> highrows{},fullrows{};
    std::array<U,256> selectors{};
    int highrank=0;
    for(int i=0;i<5;++i){
        F h=forms[8+i]&highmask,full=forms[8+i];U label=1<<i;
        while(h.top()>=0){
            int p=h.top();
            if(!selectors[p]){highrows[p]=h;fullrows[p]=full;selectors[p]=label;++highrank;break;}
            h^=highrows[p];full^=fullrows[p];label^=selectors[p];
        }
    }
    assert(highrank==3);
    std::array<uint32_t,2> kp{polar(forms[8]),polar(forms[10]^forms[11]^forms[12])};
    uint32_t Q=kp[0]^kp[1];
    assert(rank(Q)==8&&rank(kp[0])==2&&rank(kp[1])==6);
    std::array<uint32_t,4> offsets{};
    for(int s=0;s<4;++s)for(int j=0;j<2;++j)if((s>>j)&1)offsets[s]^=kp[j];
    std::array<uint32_t,28> Krows{};int Kr=0;
    for(auto v:kp)while(v){
        int p=31-std::countl_zero(v);
        if(!Krows[p]){Krows[p]=v;++Kr;break;}
        v^=Krows[p];
    }
    assert(Kr==2);
    // Rank checker controls: actual six-parallel-AND bent pair and a singular sum.
    F q5=anf(combine(truths,5)&combine(truths,160));
    F q6=anf(combine(truths,80)&combine(truths,10));
    auto bent=polar(q5^q6^anf(truths[0]&truths[1])^anf(truths[4]&truths[5]));
    assert(rank(bent)==8&&rank(bent^Q)==8&&rank(Q^Q)==0);
    std::array<std::array<F,13>,13> matrix{};
    for(int i=0;i<13;++i)for(int j=0;j<13;++j)matrix[i][j]=anf(truths[i]&truths[j]);
    std::unordered_set<uint32_t> seen;seen.reserve(20000);
    Result result;
    for(U left=1;left<8192;++left){
        ++result.lefts;
        std::vector<F> columns(13),quotient(13);
        for(int j=0;j<13;++j){
            for(int i=0;i<13;++i)if((left>>i)&1)columns[j]^=matrix[i][j];
            quotient[j]=columns[j]&highmask;
            for(int p=255;p>=0;--p)if(selectors[p]&&quotient[j].bit(p))quotient[j]^=highrows[p];
        }
        std::array<F,256> rows{};std::array<U,256> labels{};
        std::vector<U> kernel;
        for(int j=0;j<13;++j){
            F value=quotient[j];U label=1<<j;
            while(value.top()>=0){int p=value.top();if(!labels[p]){rows[p]=value;labels[p]=label;break;}
                value^=rows[p];label^=labels[p];}
            if(value.top()<0)kernel.push_back(label);
        }
        std::vector<F> images;for(U mask:kernel){
            assert(combine(quotient,mask).top()<0);images.push_back(combine(columns,mask));}
        F product;U right=0;unsigned oldgray=0;
        for(unsigned n=1;n<(1u<<kernel.size());++n){
            unsigned gray=n^(n>>1);int change=std::countr_zero(gray^oldgray);oldgray=gray;
            right^=kernel[change];product^=images[change];
            if(right<left)continue;
            ++result.pairs;
            int cancel=0;F quadratic=product;
            for(int p=255;p>=0;--p)if(selectors[p]&&quadratic.bit(p)){quadratic^=fullrows[p];cancel^=selectors[p];}
            assert((quadratic&highmask).top()<0);
            uint32_t p=polar(quadratic),key=p;
            for(int bit=27;bit>=0;--bit)if(Krows[bit]&&((key>>bit)&1))key^=Krows[bit];
            if(!seen.insert(key).second)continue;
            ++result.cosets;
            // s and s^3 give the same unordered pair of ranks.
            for(int s=0;s<2;++s)if(rank(p^offsets[s])==8&&rank(p^offsets[s]^Q)==8){
                result.escape=true;result.left=left;result.right=right;
                result.cancel=cancel;result.offset=s;return result;}
        }
    }
    assert(seen.contains(0));result.complete=true;return result;
}
int main(int argc,char**argv){
    assert(argc==2);
    assert(!std::ifstream(argv[1]).good());
    auto start=std::chrono::steady_clock::now();auto r=scan();
    double t=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::ofstream out(argv[1]);assert(out.good());
    out<<"{\"complete\":"<<(r.complete?"true":"false")
       <<",\"bent_pair_escape\":"<<(r.escape?"true":"false")<<",\"left_forms\":"<<r.lefts
       <<",\"eligible_unordered_pairs\":"<<r.pairs<<",\"quadratic_polar_cosets\":"<<r.cosets
       <<",\"left_mask\":"<<r.left<<",\"right_mask\":"<<r.right<<",\"cancel_h\":"<<r.cancel
       <<",\"K_offset_selector\":"<<r.offset<<",\"algorithm_seconds\":"<<t<<"}\n";
    std::cout<<"{\"complete\":"<<(r.complete?"true":"false")<<",\"escape\":"<<(r.escape?"true":"false")
             <<",\"pairs\":"<<r.pairs<<",\"cosets\":"<<r.cosets<<",\"seconds\":"<<t<<"}"<<std::endl;
}
