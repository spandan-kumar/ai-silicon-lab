// Independent first-eight-input replay. Boolean-ring products are constructed
// by monomial union, then high-degree coefficient ROW equations are solved
// jointly in 12 right-factor and 4 old-gate cancellation variables. This does
// not use the producer's truth-table Mobius/high-column quotient algorithm.
// Same research team: algorithmic independence is not external peer review.
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <vector>

using Mask = uint16_t;
struct Poly {
    std::array<uint64_t,4> words{};
    Poly operator^(const Poly& b) const {
        return {{words[0]^b.words[0], words[1]^b.words[1],
                 words[2]^b.words[2], words[3]^b.words[3]}};
    }
    Poly& operator^=(const Poly& b) {
        for(int j=0;j<4;++j) words[j]^=b.words[j];
        return *this;
    }
    bool operator==(const Poly&) const = default;
    void toggle(int m) { words[m/64]^=uint64_t(1)<<(m%64); }
    bool bit(int m) const { return (words[m/64]>>(m%64))&1; }
};
template<class F> void terms(const Poly& p,F visit) {
    for(int w=0;w<4;++w) {
        uint64_t bits=p.words[w];
        while(bits) {
            int bit=std::countr_zero(bits);
            visit(64*w+bit);
            bits&=bits-1;
        }
    }
}
Poly monomial(int m) { Poly p; p.toggle(m); return p; }
Poly multiply(const Poly& a,const Poly& b) {
    Poly p;
    terms(a,[&](int x) { terms(b,[&](int y) { p.toggle(x|y); }); });
    return p;
}
Poly combine(const std::vector<Poly>& rows,Mask selector) {
    Poly p;
    while(selector) {
        int j=std::countr_zero(selector);
        p^=rows.at(j);
        selector&=selector-1;
    }
    return p;
}
int degree(const Poly& p) {
    int d=0;
    terms(p,[&](int m) { d=std::max(d,std::popcount(unsigned(m))); });
    return d;
}
bool evaluate(const Poly& p,int assignment) {
    bool value=false;
    terms(p,[&](int m) { if((assignment&m)==m) value=!value; });
    return value;
}
uint32_t polar(const Poly& p) {
    uint32_t value=0; int k=0;
    for(int a=0;a<8;++a) for(int b=a+1;b<8;++b,++k)
        if(p.bit((1<<a)|(1<<b))) value|=1u<<k;
    return value;
}
std::array<unsigned,8> polar_rows(uint32_t value,int width=8) {
    std::array<unsigned,8> rows{}; int k=0;
    for(int a=0;a<width;++a) for(int b=a+1;b<width;++b,++k)
        if((value>>k)&1) { rows[a]|=1u<<b; rows[b]|=1u<<a; }
    return rows;
}
int matrix_rank(uint32_t value,int width=8) {
    auto rows=polar_rows(value,width); int rank=0;
    for(int column=0;column<width;++column) {
        int next=rank;
        while(next<width&&!((rows[next]>>column)&1)) ++next;
        if(next==width) continue;
        std::swap(rows[next],rows[rank]);
        for(int j=rank+1;j<width;++j)
            if((rows[j]>>column)&1) rows[j]^=rows[rank];
        ++rank;
    }
    return rank;
}
bool pfaffian(const std::array<unsigned,8>& rows,unsigned vertices) {
    if(!vertices) return true;
    int first=std::countr_zero(vertices);
    unsigned rest=vertices^(1u<<first); bool value=false;
    for(unsigned partners=rows[first]&rest;partners;partners&=partners-1) {
        int partner=std::countr_zero(partners);
        value^=pfaffian(rows,rest^(1u<<partner));
    }
    return value;
}
std::vector<Mask> nullspace(const std::array<Mask,256>& equations,int width) {
    std::array<Mask,16> rows{};
    for(Mask equation:equations) while(equation) {
        int column=std::countr_zero(equation);
        assert(column<width);
        if(rows[column]) equation^=rows[column];
        else { rows[column]=equation; break; }
    }
    std::vector<Mask> result;
    for(int free=0;free<width;++free) if(!rows[free]) {
        Mask value=Mask(1u<<free);
        for(int column=width-1;column>=0;--column)
            if(rows[column]&&(std::popcount(unsigned(rows[column]&value))&1))
                value^=Mask(1u<<column);
        result.push_back(value);
    }
    return result;
}
std::vector<Mask> nullspace_columns(const std::vector<Poly>& columns) {
    std::array<Mask,256> equations{};
    for(size_t j=0;j<columns.size();++j) terms(columns[j],[&](int m) {
        if(std::popcount(unsigned(m))>2) equations[m]^=Mask(1u<<j);
    });
    return nullspace(equations,columns.size());
}
struct Projection { std::vector<Mask> lifted,zero; };
Projection project(const std::vector<Mask>& joint) {
    std::array<Mask,12> rows{}; Projection result;
    for(Mask value:joint) {
        Mask right=value&4095;
        while(right) {
            int column=std::countr_zero(right);
            if(rows[column]) { value^=rows[column]; right=value&4095; }
            else { rows[column]=value; break; }
        }
        if(!right) result.zero.push_back(value);
    }
    for(Mask value:rows) if(value) result.lifted.push_back(value);
    return result;
}
using Factors=std::array<std::array<Mask,2>,4>;
struct Prefix { Factors factors{}; std::vector<Poly> forms; };
Prefix prefix(int code) {
    assert(code>=0&&code<4096);
    Prefix p;
    for(int j=0;j<8;++j) p.forms.push_back(monomial(1<<j));
    unsigned bits=code;
    for(int gate=0;gate<4;++gate) {
        unsigned mask=(1u<<gate)-1;
        Mask left=Mask((1u<<(2*gate))|((bits&mask)<<8)); bits>>=gate;
        Mask right=Mask((1u<<(2*gate+1))|((bits&mask)<<8)); bits>>=gate;
        p.factors[gate]={left,right};
        p.forms.push_back(multiply(combine(p.forms,left),combine(p.forms,right)));
    }
    assert(!bits);
    return p;
}
struct Result {
    int code=0, high_rank=0, offset_dimension=0;
    std::array<int,4> degrees{};
    uint64_t pairs=0;
    std::array<uint64_t,9> rank_histogram{};
    std::array<uint64_t,13> kernel_histogram{};
    std::unordered_map<uint32_t,int> cosets;
    Mask witness_left=0,witness_right=0,witness_decoder=0;
    double seconds=0;
};
void replay_witness(const Prefix& p,Mask left,Mask right,Mask decoder) {
    std::vector<Poly> old(p.forms.begin()+8,p.forms.end());
    Poly q=multiply(combine(p.forms,left),combine(p.forms,right))^combine(old,decoder);
    assert(degree(q)<=2&&matrix_rank(polar(q))==8);
    assert(pfaffian(polar_rows(polar(q)),255));
    for(int x=0;x<256;++x) {
        unsigned wires=x;
        for(int gate=0;gate<4;++gate) {
            bool l=std::popcount(unsigned(wires&p.factors[gate][0]))&1;
            bool r=std::popcount(unsigned(wires&p.factors[gate][1]))&1;
            if(l&&r) wires|=1u<<(8+gate);
            assert(bool((wires>>(8+gate))&1)==evaluate(p.forms[8+gate],x));
        }
        bool l=std::popcount(unsigned(wires&left))&1;
        bool r=std::popcount(unsigned(wires&right))&1;
        bool decoded=(l&&r)^(std::popcount(unsigned((wires>>8)&decoder))&1);
        assert(decoded==evaluate(q,x));
    }
}
Result scan(int code,bool require_quintic=true) {
    auto start=std::chrono::steady_clock::now();
    Prefix p=prefix(code); Result result; result.code=code;
    for(int j=0;j<4;++j) result.degrees[j]=degree(p.forms[8+j]);
    assert(!require_quintic||result.degrees[3]==5);
    std::vector<Poly> old(p.forms.begin()+8,p.forms.end());
    auto old_kernel=nullspace_columns(old);
    result.offset_dimension=old_kernel.size();
    result.high_rank=4-result.offset_dimension;
    std::vector<uint32_t> offsets{0};
    for(Mask selector:old_kernel) {
        Poly q=combine(old,selector); assert(degree(q)<=2);
        uint32_t offset=polar(q); assert(offset);
        size_t previous=offsets.size();
        for(size_t j=0;j<previous;++j) offsets.push_back(offsets[j]^offset);
    }
    std::array<std::array<Poly,12>,12> products{};
    for(int i=0;i<12;++i) for(int j=0;j<12;++j)
        products[i][j]=multiply(p.forms[i],p.forms[j]);
    std::array<Mask,256> old_equations{};
    for(int g=0;g<4;++g) terms(old[g],[&](int m) {
        if(std::popcount(unsigned(m))>2) old_equations[m]^=Mask(1u<<(12+g));
    });
    std::array<Poly,12> columns{}; unsigned previous=0;
    result.cosets.reserve(16000);
    for(unsigned left=1;left<4096;++left) {
        for(unsigned changed=left^previous;changed;changed&=changed-1) {
            int i=std::countr_zero(changed);
            for(int j=0;j<12;++j) columns[j]^=products[i][j];
        }
        previous=left;
        auto equations=old_equations;
        for(int j=0;j<12;++j) terms(columns[j],[&](int m) {
            if(std::popcount(unsigned(m))>2) equations[m]^=Mask(1u<<j);
        });
        auto projected=project(nullspace(equations,16));
        assert(projected.zero.size()==old_kernel.size());
        int dimension=projected.lifted.size(); ++result.kernel_histogram[dimension];
        std::array<uint32_t,12> images{};
        for(int j=0;j<dimension;++j) {
            Mask solution=projected.lifted[j]; Poly q;
            for(int i=0;i<12;++i) if((solution>>i)&1) q^=columns[i];
            q^=combine(old,solution>>12);
            assert(degree(q)<=2); images[j]=polar(q);
        }
        Mask solution=0; uint32_t packed=0;
        for(int number=1;number<(1<<dimension);++number) {
            int changed=std::countr_zero(unsigned(number));
            solution^=projected.lifted[changed]; packed^=images[changed];
            Mask right=solution&4095;
            assert(right);
            if(right<left) continue;
            ++result.pairs;
            uint32_t key=packed;
            for(auto offset:offsets) key=std::min(key,packed^offset);
            if(result.cosets.contains(key)) continue;
            int maximum=0; Mask extra=0;
            for(size_t j=0;j<offsets.size();++j) {
                int rank=matrix_rank(packed^offsets[j]);
                if(rank>maximum) { maximum=rank; extra=Mask(j); }
            }
            result.cosets.emplace(key,maximum); ++result.rank_histogram[maximum];
            if(maximum==8&&!result.witness_left) {
                Mask decoder=solution>>12;
                for(size_t j=0;j<old_kernel.size();++j)
                    if((extra>>j)&1) decoder^=old_kernel[j];
                result.witness_left=Mask(left); result.witness_right=right;
                result.witness_decoder=decoder;
                replay_witness(p,Mask(left),right,decoder);
            }
        }
    }
    assert(result.cosets.contains(0));
    uint64_t left_count=0;
    for(auto count:result.kernel_histogram) left_count+=count;
    assert(left_count==4095);
    result.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    return result;
}
template<class T,size_t N> void array_json(std::ostream& out,const std::array<T,N>& a) {
    out<<'[';
    for(size_t j=0;j<N;++j) { if(j) out<<','; out<<a[j]; }
    out<<']';
}
void result_json(std::ostream& out,const Result& r) {
    int maximum=0;
    for(int rank=0;rank<=8;++rank) if(r.rank_histogram[rank]) maximum=rank;
    out<<"{\"code\":"<<r.code<<",\"degrees\":"; array_json(out,r.degrees);
    out<<",\"high_rank\":"<<r.high_rank<<",\"quadratic_offset_dimension\":"<<r.offset_dimension
       <<",\"complete\":true,\"lefts\":4095,\"pairs\":"<<r.pairs
       <<",\"polar_cosets\":"<<r.cosets.size()<<",\"maximum_polar_rank\":"<<maximum
       <<",\"maximum_rank_histogram\":"; array_json(out,r.rank_histogram);
    out<<",\"right_kernel_histogram\":"; array_json(out,r.kernel_histogram);
    out<<",\"witness_left\":"<<r.witness_left<<",\"witness_right\":"<<r.witness_right
       <<",\"witness_gate_decoder\":"<<r.witness_decoder<<",\"algorithm_seconds\":"<<r.seconds<<'}';
}
uint32_t next_random(uint32_t& state) {
    state^=state<<13; state^=state>>17; state^=state<<5; return state;
}
std::array<uint64_t,3> controls() {
    uint32_t rng=20261020; std::array<uint64_t,3> counts{};
    for(int width=0;width<8;++width) for(int sample=0;sample<64;++sample) {
        std::array<Mask,256> equations{};
        unsigned mask=(1u<<width)-1;
        for(int j=0;j<12;++j) equations[j]=Mask(next_random(rng)&mask);
        auto basis=nullspace(equations,width);
        std::vector<bool> got(1u<<width);
        for(unsigned s=0;s<(1u<<basis.size());++s) {
            Mask value=0;
            for(size_t j=0;j<basis.size();++j) if((s>>j)&1) value^=basis[j];
            got[value]=true;
        }
        for(unsigned value=0;value<=mask;++value) {
            bool expected=true;
            for(Mask row:equations) if(std::popcount(unsigned(row&value))&1) expected=false;
            assert(got[value]==expected);
        }
        ++counts[0];
    }
    for(int sample=0;sample<64;++sample) {
        std::array<Mask,9> columns{};
        for(auto& c:columns) c=next_random(rng)&31;
        std::array<Mask,256> equations{};
        for(int j=0;j<9;++j) for(int bit=0;bit<5;++bit)
            if((columns[j]>>bit)&1) equations[bit]^=Mask(1u<<(j<5?j:j+7));
        auto projected=project(nullspace(equations,16));
        std::array<bool,32> got{};
        for(unsigned s=0;s<(1u<<projected.lifted.size());++s) {
            Mask value=0;
            for(size_t j=0;j<projected.lifted.size();++j)
                if((s>>j)&1) value^=projected.lifted[j];
            got[value&31]=true;
            Mask check=0;
            for(int j=0;j<9;++j) if((value>>(j<5?j:j+7))&1) check^=columns[j];
            assert(!check);
        }
        for(int right=0;right<32;++right) {
            bool expected=false;
            for(int cancel=0;cancel<16;++cancel) {
                Mask check=0;
                for(int j=0;j<5;++j) if((right>>j)&1) check^=columns[j];
                for(int j=0;j<4;++j) if((cancel>>j)&1) check^=columns[5+j];
                if(!check) expected=true;
            }
            assert(got[right]==expected);
        }
        ++counts[1];
    }
    for(int width:{2,4,6,8}) {
        int edges=width*(width-1)/2;
        unsigned samples=width<8?1u<<edges:1024;
        for(unsigned j=0;j<samples;++j) {
            uint32_t value=width<8?j:next_random(rng)&((1u<<28)-1);
            assert(pfaffian(polar_rows(value,width),(1u<<width)-1)==(matrix_rank(value,width)==width));
            ++counts[2];
        }
    }
    Prefix p=prefix(1586);
    std::vector<Poly> old(p.forms.begin()+8,p.forms.end());
    Poly q=multiply(combine(p.forms,84),combine(p.forms,768))^combine(old,13);
    assert(degree(p.forms[11])==4&&degree(q)==2&&matrix_rank(polar(q))==8);
    replay_witness(p,84,768,13);
    // Direct semantic check of symbolic union products, all 144 basis pairs.
    for(const Poly& a:p.forms) for(const Poly& b:p.forms) {
        Poly product=multiply(a,b);
        for(int x=0;x<256;++x)
            assert(evaluate(product,x)==(evaluate(a,x)&&evaluate(b,x)));
    }
    return counts;
}
int main(int argc,char** argv) {
    auto start=std::chrono::steady_clock::now();
    int begin=0,end=4096; bool run_controls=false; std::string path;
    for(int i=1;i<argc;++i) {
        std::string arg=argv[i];
        if(arg=="--begin") begin=std::stoi(argv[++i]);
        else if(arg=="--end") end=std::stoi(argv[++i]);
        else if(arg=="--out") path=argv[++i];
        else if(arg=="--controls") run_controls=true;
        else { std::cerr<<"Unknown argument: "<<arg<<'\n'; return 2; }
    }
    assert(begin>=0&&end<=4096&&begin<=end&&!path.empty());
    { std::ifstream existing(path); assert(!existing.good()); }
    std::ofstream out(path); assert(out.good());
    out<<"{\"algorithm\":\"symbolic monomial-union products, joint row equations, projected nullspace, low-pivot polar rank\","
          "\"external_peer_review\":false,\"begin\":"<<begin<<",\"end\":"<<end;
    if(run_controls) {
        auto counts=controls();
        out<<",\"controls\":{\"status\":\"pass\",\"small_kernel_bruteforce_controls\":"<<counts[0]
           <<",\"projected_kernel_bruteforce_controls\":"<<counts[1]
           <<",\"Pfaffian_vs_row_rank_controls\":"<<counts[2]
           <<",\"quartic_positive_256_row_truth_replay\":true,\"symbolic_truth_product_checks\":36864,"
             "\"quartic_positive_complete_scan\":";
        auto positive=scan(1586,false); assert(positive.witness_left);
        result_json(out,positive); out<<'}';
    }
    std::array<uint64_t,6> histogram{}; uint64_t quintics=0,admitting=0;
    out<<",\"cases\":[";
    for(int code=begin;code<end;++code) {
        auto p=prefix(code); int d=degree(p.forms[11]); assert(d>=2&&d<=5); ++histogram[d];
        if(d!=5) continue;
        if(quintics++) out<<',';
        auto row=scan(code); admitting+=bool(row.witness_left); result_json(out,row);
        if(quintics%128==0) std::cout<<"Completed "<<quintics<<" quintic prefixes; latest code "<<code<<std::endl;
    }
    double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    out<<"],\"degree_histogram\":"; array_json(out,histogram);
    out<<",\"quintic_prefixes\":"<<quintics<<",\"prefixes_admitting_rank8_scalar\":"<<admitting
       <<",\"complete\":true,\"algorithm_seconds\":"<<seconds<<"}\n";
    assert(out.good()); out.close();
    std::cout<<"{\"status\":\"pass\",\"quintic_prefixes\":"<<quintics
             <<",\"prefixes_admitting_rank8_scalar\":"<<admitting<<",\"algorithm_seconds\":"<<seconds<<"}\n";
}
