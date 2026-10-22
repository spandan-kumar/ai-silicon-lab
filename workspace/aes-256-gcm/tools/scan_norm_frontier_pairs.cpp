// Exact one-product bent-pair necessary condition on supplied W5 spaces.
// EXPERIMENTAL CHECKPOINT (2026-10-22): controls only, no frontier campaign.
// Independent inventory replay/comparison is pending; see PROGRESS.md.
// Truth-table products, Mobius ANF, high-column kernels, all K5 offsets.
// A positive is not a GF(16) multiplier. A negative requires complete=true.
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>

using U = uint16_t;
using Clock = std::chrono::steady_clock;
struct F {
    std::array<uint64_t,4> x{};
    bool operator==(const F&) const = default;
    F operator^(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]^b.x[i];return r; }
    F operator&(const F& b) const { F r; for(int i=0;i<4;++i)r.x[i]=x[i]&b.x[i];return r; }
    F& operator^=(const F& b) {for(int i=0;i<4;++i)x[i]^=b.x[i];return *this;}
    bool bit(int i) const {return (x[i/64]>>(i%64))&1;}
    void flip(int i){x[i/64]^=uint64_t(1)<<(i%64);}
    int top() const {for(int i=3;i>=0;--i)if(x[i])return i*64+63-std::countl_zero(x[i]);return -1;}
};
F from_hex(std::string value){
    if(value.starts_with("0x"))value=value.substr(2);
    assert(!value.empty()&&value.size()<=64);F result;int word=0;
    for(size_t end=value.size();end;){size_t begin=end>16?end-16:0;
        result.x[word++]=std::stoull(value.substr(begin,end-begin),nullptr,16);end=begin;}
    return result;
}
std::string hex(const F& f){
    std::ostringstream out;out<<"0x"<<std::hex;int high=3;
    while(high>0&&!f.x[high])--high;
    out<<f.x[high];for(int i=high-1;i>=0;--i)out<<std::setw(16)<<std::setfill('0')<<f.x[i];
    return out.str();
}
F transform(F value){
    for(int b=0;b<8;++b)for(int m=0;m<256;++m)
        if((m&(1<<b))&&value.bit(m^(1<<b)))value.flip(m);
    return value;
}
F truth_slow(const F& polynomial){
    F truth;
    for(int point=0;point<256;++point){bool value=false;
        for(int m=0;m<256;++m)if(polynomial.bit(m)&&(point&m)==m)value=!value;
        if(value)truth.flip(point);}
    return truth;
}
F combine(const std::vector<F>& forms,U selector){
    F value;while(selector){int b=std::countr_zero(selector);assert(b<int(forms.size()));
        value^=forms[b];selector&=selector-1;}return value;
}
uint32_t polar(const F& form){
    uint32_t value=0;int bit=0;
    for(int i=0;i<8;++i)for(int j=i+1;j<8;++j,++bit)
        if(form.bit((1<<i)|(1<<j)))value|=uint32_t(1)<<bit;
    return value;
}
int rank(uint32_t p){
    std::array<unsigned,8> rows{},basis{};int bit=0,result=0;
    for(int i=0;i<8;++i)for(int j=i+1;j<8;++j,++bit)if((p>>bit)&1){rows[i]^=1u<<j;rows[j]^=1u<<i;}
    for(auto value:rows)while(value){int b=31-std::countl_zero(value);
        if(!basis[b]){basis[b]=value;++result;break;}value^=basis[b];}
    return result;
}
int pfaffian(uint32_t p,const std::vector<int>& vertices){
    if(vertices.empty())return 1;int result=0,first=vertices[0];
    auto pair_bit=[](int a,int b){int k=0;for(int i=0;i<8;++i)for(int j=i+1;j<8;++j,++k)if(i==a&&j==b)return k;assert(false);return 0;};
    for(size_t i=1;i<vertices.size();++i)if((p>>pair_bit(first,vertices[i]))&1){
        std::vector<int> rest;for(size_t j=1;j<vertices.size();++j)if(i!=j)rest.push_back(vertices[j]);
        result^=pfaffian(p,rest);}
    return result;
}
F high_mask(){F result;for(int m=0;m<256;++m)if(std::popcount(unsigned(m))>2)result.flip(m);return result;}
int form_rank(const std::vector<F>& forms){
    std::array<F,256> rows{};int rank=0;
    for(auto value:forms)while(value.top()>=0){int p=value.top();if(rows[p].top()<0){rows[p]=value;++rank;break;}value^=rows[p];}
    return rank;
}
struct State {int id,code;uint32_t source_coset;std::vector<F> nonlinear;std::vector<uint32_t> Q;};
State parse(const std::string& line){
    State s;int n;std::istringstream in(line);in>>s.id>>s.code>>s.source_coset>>n;assert(in&&n>=1&&n<=2);
    for(int i=0;i<5;++i){std::string word;in>>word;assert(in);s.nonlinear.push_back(from_hex(word));}
    for(int i=0;i<n;++i){uint32_t q;in>>q;assert(in&&q<(1u<<28));s.Q.push_back(q);}
    std::string extra;assert(!(in>>extra));assert(form_rank(s.nonlinear)==5);
    return s;
}
struct Witness {bool found=false;U left=0,right=0;unsigned old=0,Q_old=0;uint32_t t=0;F t_form;};
struct Result {
    bool complete=false;int high_rank=0,K_dimension=0;
    uint64_t lefts=0,pairs=0,cosets=0,offset_checks=0,rank_checks=0,truth_rows=0;
    std::array<uint64_t,14> kernels{};
    std::vector<Witness> witnesses;std::vector<uint32_t> K_polars;
    std::vector<unsigned> K_selectors;
    double seconds=0;
};
Result scan(const State& state){
    auto start=Clock::now();Result result;result.witnesses.resize(state.Q.size());
    const F highmask=high_mask();std::vector<F> forms,truths;
    for(int i=0;i<8;++i){F raw;raw.flip(1<<i);forms.push_back(raw);}
    for(auto f:state.nonlinear){
        assert(!f.bit(0));for(int i=0;i<8;++i)assert(!f.bit(1<<i));forms.push_back(f);}
    assert(form_rank(forms)==13);for(auto f:forms)truths.push_back(transform(f));
    std::array<F,256> high_rows{},full_rows{};std::array<unsigned,256> labels{};
    for(int i=0;i<5;++i){F value=state.nonlinear[i]&highmask,full=state.nonlinear[i];unsigned label=1u<<i;
        while(value.top()>=0){int p=value.top();if(!labels[p]){high_rows[p]=value;full_rows[p]=full;labels[p]=label;++result.high_rank;break;}
            value^=high_rows[p];full^=full_rows[p];label^=labels[p];}
        if(value.top()<0){assert(label&&polar(full));result.K_polars.push_back(polar(full));result.K_selectors.push_back(label);}}
    result.K_dimension=result.K_polars.size();assert(result.high_rank+result.K_dimension==5);
    std::vector<uint32_t> offsets(1u<<result.K_dimension);std::vector<unsigned> offset_selectors(offsets.size());
    for(unsigned s=1;s<offsets.size();++s){int b=std::countr_zero(s);unsigned rest=s&(s-1);
        offsets[s]=offsets[rest]^result.K_polars[b];offset_selectors[s]=offset_selectors[rest]^result.K_selectors[b];}
    assert(std::unordered_set<uint32_t>(offsets.begin(),offsets.end()).size()==offsets.size());
    for(size_t j=0;j<state.Q.size();++j){assert(rank(state.Q[j])==8);auto it=std::find(offsets.begin(),offsets.end(),state.Q[j]);assert(it!=offsets.end());
        result.witnesses[j].Q_old=offset_selectors[it-offsets.begin()];}
    std::array<uint32_t,28> K_rows{};
    for(auto value:result.K_polars)while(value){int p=31-std::countl_zero(value);if(!K_rows[p]){K_rows[p]=value;break;}value^=K_rows[p];}
    std::vector<int> pivots;for(int p=255;p>=0;--p)if(labels[p])pivots.push_back(p);
    auto quotient_high=[&](F value){value=value&highmask;for(int p:pivots)if(value.bit(p))value^=high_rows[p];return value;};
    std::array<std::array<F,13>,13> matrix{},reduced{};
    for(int i=0;i<13;++i)for(int j=i;j<13;++j){matrix[i][j]=transform(truths[i]&truths[j]);
        matrix[j][i]=matrix[i][j];reduced[i][j]=quotient_high(matrix[i][j]);reduced[j][i]=reduced[i][j];}
    std::unordered_set<uint32_t> seen;seen.reserve(20000);
    for(U left=1;left<8192;++left){
        ++result.lefts;std::vector<F> columns(13),quotient(13);
        for(int i=0;i<13;++i)if((left>>i)&1)for(int j=0;j<13;++j){columns[j]^=matrix[i][j];quotient[j]^=reduced[i][j];}
        std::array<F,256> rows{};std::array<U,256> row_labels{};std::vector<U> kernel;
        for(int j=0;j<13;++j){F value=quotient[j];U label=1u<<j;
            while(value.top()>=0){int p=value.top();if(!row_labels[p]){rows[p]=value;row_labels[p]=label;break;}
                value^=rows[p];label^=row_labels[p];}
            if(value.top()<0)kernel.push_back(label);}
        ++result.kernels[kernel.size()];std::vector<F> images;
        for(U k:kernel){assert(combine(quotient,k).top()<0);images.push_back(combine(columns,k));}
        F product;U right=0;unsigned oldgray=0;
        for(unsigned n=1;n<(1u<<kernel.size());++n){unsigned gray=n^(n>>1);int change=std::countr_zero(gray^oldgray);oldgray=gray;
            right^=kernel[change];product^=images[change];if(right<left)continue;++result.pairs;
            unsigned cancel=0;F quadratic=product;
            for(int p:pivots)if(quadratic.bit(p)){quadratic^=full_rows[p];cancel^=labels[p];}
            assert((quadratic&highmask).top()<0);uint32_t p=polar(quadratic),key=p;
            for(int bit=27;bit>=0;--bit)if(K_rows[bit]&&((key>>bit)&1))key^=K_rows[bit];
            if(!seen.insert(key).second)continue;++result.cosets;
            // Affine functions are free; key==0 is exactly the old W5 space.
            if(!key)continue;
            for(size_t q=0;q<state.Q.size();++q)if(!result.witnesses[q].found){
                for(size_t s=0;s<offsets.size();++s){++result.offset_checks;uint32_t t=p^offsets[s];++result.rank_checks;
                    if(rank(t)!=8)continue;++result.rank_checks;if(rank(t^state.Q[q])!=8)continue;
                    auto& witness=result.witnesses[q];witness.found=true;witness.left=left;witness.right=right;
                    witness.old=cancel^offset_selectors[s];witness.t=t;
                    witness.t_form=product^combine(state.nonlinear,witness.old);
                    assert((witness.t_form&highmask).top()<0&&polar(witness.t_form)==t);
                    F actual=(combine(truths,left)&combine(truths,right))^combine(truths,U(witness.old<<8));
                    F expected=truth_slow(witness.t_form);assert(actual==expected);
                    F Q_form=combine(state.nonlinear,witness.Q_old);assert((Q_form&highmask).top()<0&&polar(Q_form)==state.Q[q]);
                    assert((actual^truth_slow(Q_form))==truth_slow(witness.t_form^Q_form));result.truth_rows+=256;
                    break;}
            }
            if(std::all_of(result.witnesses.begin(),result.witnesses.end(),[](const Witness& w){return w.found;})){
                result.seconds=std::chrono::duration<double>(Clock::now()-start).count();return result;}
        }
    }
    result.complete=true;assert(result.lefts==8191);result.seconds=std::chrono::duration<double>(Clock::now()-start).count();return result;
}
void write_result(std::ostream& out,const State& state,const Result& r){
    out<<"{\"state_id\":"<<state.id<<",\"source_code\":"<<state.code<<",\"source_polar_coset\":"<<state.source_coset
       <<",\"complete\":"<<(r.complete?"true":"false")<<",\"high_rank\":"<<r.high_rank<<",\"K_dimension\":"<<r.K_dimension
       <<",\"left_forms\":"<<r.lefts<<",\"eligible_unordered_pairs\":"<<r.pairs<<",\"quadratic_polar_cosets\":"<<r.cosets
       <<",\"offset_checks\":"<<r.offset_checks<<",\"rank_checks\":"<<r.rank_checks<<",\"witness_truth_rows\":"<<r.truth_rows
       <<",\"algorithm_seconds\":"<<std::setprecision(12)<<r.seconds<<",\"K_polars\":[";
    for(size_t i=0;i<r.K_polars.size();++i){if(i)out<<',';out<<r.K_polars[i];}out<<"],\"K_gate_selectors\":[";
    for(size_t i=0;i<r.K_selectors.size();++i){if(i)out<<',';out<<r.K_selectors[i];}out<<"],\"right_kernel_dimension_histogram\":[";
    for(size_t i=0;i<r.kernels.size();++i){if(i)out<<',';out<<r.kernels[i];}out<<"],\"marks\":[";
    for(size_t q=0;q<state.Q.size();++q){if(q)out<<',';const auto& w=r.witnesses[q];
        out<<"{\"Q_polar\":"<<state.Q[q]<<",\"Q_old_gate_selector\":"<<w.Q_old<<",\"status\":\""<<(w.found?"positive":(r.complete?"negative":"unknown"))<<"\"";
        if(w.found)out<<",\"left_mask\":"<<w.left<<",\"right_mask\":"<<w.right<<",\"old_gate_selector\":"<<w.old
            <<",\"t_polar\":"<<w.t<<",\"t_plus_Q_polar\":"<<(w.t^state.Q[q])<<",\"t_anf_hex\":\""<<hex(w.t_form)<<"\"";
        out<<'}';}out<<"]}\n";
}
void controls(std::ostream& out){
    std::mt19937 rng(20261022);uint64_t mobius=0,pf=0;
    for(int i=0;i<128;++i){F f;for(auto& w:f.x)w=uint64_t(rng())|(uint64_t(rng())<<32);
        assert(transform(transform(f))==f);assert(transform(f)==truth_slow(f));++mobius;}
    for(int i=0;i<4096;++i){uint32_t p=rng()&((1u<<28)-1);assert((rank(p)==8)==bool(pfaffian(p,{0,1,2,3,4,5,6,7})));++pf;}
    assert(rank(0)==0);F f;f.x={1,0,1,0x123456789abcdef0};assert(from_hex(hex(f))==f);
    // Directly replay the established six-product fixture, before scanning it.
    std::vector<F> raw;for(int i=0;i<8;++i){F v;v.flip(1<<i);raw.push_back(transform(v));}
    F Q;for(int i=0;i<4;++i)Q^=transform(raw[2*i]&raw[2*i+1]);
    F R=transform(combine(raw,5)&combine(raw,160))^transform(combine(raw,80)&combine(raw,10))
        ^transform(raw[0]&raw[1])^transform(raw[4]&raw[5]);
    assert(polar(Q)==138420225&&rank(polar(R))==8&&rank(polar(R^Q))==8);
    assert((R&high_mask()).top()<0);
    out<<"{\"status\":\"pass\",\"truth_Mobius_controls\":"<<mobius<<",\"Pfaffian_elimination_controls\":"<<pf
       <<",\"actual_six_parallel_AND_pair\":true,\"zero_rank_control\":true}\n";
}
int main(int argc,char** argv){
    assert(argc>=3);std::string input=argv[1],output=argv[2];assert(!std::ifstream(output).good());
    if(input=="--self-test"){std::ofstream out(output);assert(out.good());controls(out);std::cout<<"self-test pass\n";return 0;}
    int begin=0,count=-1;for(int i=3;i<argc;i+=2){assert(i+1<argc);std::string flag=argv[i];
        if(flag=="--begin")begin=std::stoi(argv[i+1]);else{assert(flag=="--count");count=std::stoi(argv[i+1]);}}
    assert(begin>=0&&count>=-1);std::ifstream in(input);assert(in.good());std::ofstream out(output);assert(out.good());
    auto start=Clock::now();int index=0,states=0,positive=0,negative=0,complete=0;uint64_t lefts=0,pairs=0,cosets=0;
    std::string line;
    while(std::getline(in,line)){if(index++<begin)continue;if(count>=0&&states>=count)break;
        assert(!line.empty());auto state=parse(line);auto r=scan(state);write_result(out,state,r);out.flush();assert(out.good());
        ++states;complete+=r.complete;lefts+=r.lefts;pairs+=r.pairs;cosets+=r.cosets;
        for(const auto& w:r.witnesses){positive+=w.found;negative+=!w.found&&r.complete;}
        if(states%25==0)std::cout<<"states="<<states<<" positive="<<positive<<" negative="<<negative<<std::endl;
    }
    assert(states>0);double seconds=std::chrono::duration<double>(Clock::now()-start).count();
    std::string summary=output+".summary.json";assert(!std::ifstream(summary).good());std::ofstream meta(summary);assert(meta.good());
    meta<<"{\"status\":\"pass\",\"states\":"<<states<<",\"positive_Q_marks\":"<<positive<<",\"negative_Q_marks\":"<<negative
        <<",\"complete_states\":"<<complete<<",\"early_positive_states\":"<<(states-complete)<<",\"left_forms\":"<<lefts
        <<",\"eligible_unordered_pairs\":"<<pairs<<",\"quadratic_polar_cosets\":"<<cosets<<",\"wall_seconds\":"<<std::setprecision(12)<<seconds
        <<",\"scope\":\"One new quadratic bent-pair direction outside actual W5; necessary, not sufficient for GF16.\"}\n";
    std::cout<<"states="<<states<<" positive="<<positive<<" negative="<<negative<<" seconds="<<seconds<<std::endl;
}
