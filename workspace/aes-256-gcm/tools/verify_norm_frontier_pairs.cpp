// Independent W5 bent-pair necessary-condition replay.
// Boolean-ring monomial-union products; joint coefficient ROW equations in
// 13 right-factor + 5 old-cancellation variables, projected right kernels.
// No truth/Mobius products or production high-column quotient reduction.
// Algorithmic independence within one research team, not external peer review.
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

using Joint = uint32_t; // 18 bits: uint16_t would silently lose old corrections.
using Clock = std::chrono::steady_clock;
constexpr Joint RIGHT_MASK = (1u << 13) - 1;
struct Poly {
    std::array<uint64_t, 4> words{};
    Poly operator^(const Poly& other) const {
        Poly result;
        for (int i = 0; i < 4; ++i) result.words[i] = words[i] ^ other.words[i];
        return result;
    }
    Poly& operator^=(const Poly& other) {
        for (int i = 0; i < 4; ++i) words[i] ^= other.words[i];
        return *this;
    }
    bool operator==(const Poly&) const = default;
    void toggle(int monomial) { words[monomial / 64] ^= uint64_t(1) << (monomial % 64); }
    bool bit(int monomial) const { return (words[monomial / 64] >> (monomial % 64)) & 1; }
};
template<class F> void terms(const Poly& p, F visit) {
    for (int word = 0; word < 4; ++word)
        for (uint64_t bits = p.words[word]; bits; bits &= bits - 1)
            visit(64 * word + std::countr_zero(bits));
}
Poly multiply(const Poly& left, const Poly& right) {
    Poly result;
    terms(left, [&](int a) { terms(right, [&](int b) { result.toggle(a | b); }); });
    return result;
}
Poly select(const std::vector<Poly>& forms, Joint selector) {
    Poly result;
    while (selector) {
        result ^= forms.at(std::countr_zero(selector));
        selector &= selector - 1;
    }
    return result;
}
Poly parse_hex(std::string text) {
    assert(text.starts_with("0x")); text = text.substr(2);
    assert(!text.empty() && text.size() <= 64);
    Poly result; int word = 0;
    for (size_t end = text.size(); end;) {
        size_t begin = end > 16 ? end - 16 : 0;
        result.words[word++] = std::stoull(text.substr(begin, end - begin), nullptr, 16);
        end = begin;
    }
    return result;
}
std::string hex(const Poly& p) {
    std::ostringstream out; out << "0x" << std::hex;
    int high = 3; while (high > 0 && !p.words[high]) --high;
    out << p.words[high];
    for (int i = high - 1; i >= 0; --i) out << std::setfill('0') << std::setw(16) << p.words[i];
    return out.str();
}
bool evaluate(const Poly& p, unsigned x) {
    bool result = false;
    terms(p, [&](int m) { if ((x & unsigned(m)) == unsigned(m)) result = !result; });
    return result;
}
bool quadratic(const Poly& p) {
    bool result = true;
    terms(p, [&](int m) { if (std::popcount(unsigned(m)) > 2) result = false; });
    return result;
}
uint32_t polar(const Poly& p) {
    uint32_t result = 0; int bit = 0;
    for (int a = 0; a < 8; ++a) for (int b = a + 1; b < 8; ++b, ++bit)
        if (p.bit((1 << a) | (1 << b))) result |= 1u << bit;
    return result;
}
std::array<unsigned, 8> polar_rows(uint32_t packed) {
    std::array<unsigned, 8> rows{}; int bit = 0;
    for (int a = 0; a < 8; ++a) for (int b = a + 1; b < 8; ++b, ++bit)
        if ((packed >> bit) & 1) { rows[a] |= 1u << b; rows[b] |= 1u << a; }
    return rows;
}
int matrix_rank(uint32_t packed) {
    std::array<unsigned, 8> basis{}; int rank = 0;
    for (unsigned value : polar_rows(packed)) while (value) {
        int bit = std::countr_zero(value);
        if (basis[bit]) value ^= basis[bit];
        else { basis[bit] = value; ++rank; break; }
    }
    return rank;
}
bool pfaffian(const std::array<unsigned, 8>& rows, unsigned vertices = 255) {
    if (!vertices) return true;
    int first = std::countr_zero(vertices);
    unsigned rest = vertices ^ (1u << first); bool result = false;
    for (unsigned partners = rows[first] & rest; partners; partners &= partners - 1) {
        int next = std::countr_zero(partners);
        result ^= pfaffian(rows, rest ^ (1u << next));
    }
    return result;
}
std::vector<Joint> row_kernel(const std::vector<Joint>& equations, int width) {
    assert(width >= 0 && width <= 18);
    std::array<Joint, 18> rows{};
    for (Joint equation : equations) while (equation) {
        int bit = std::countr_zero(equation); assert(bit < width);
        if (rows[bit]) equation ^= rows[bit];
        else { rows[bit] = equation; break; }
    }
    std::vector<Joint> result;
    for (int free = 0; free < width; ++free) if (!rows[free]) {
        Joint value = 1u << free;
        for (int pivot = width - 1; pivot >= 0; --pivot)
            if (rows[pivot] && (std::popcount(rows[pivot] & value) & 1)) value ^= 1u << pivot;
        result.push_back(value);
    }
    return result;
}
struct Projection { std::vector<Joint> right, old; };
Projection project(const std::vector<Joint>& basis) {
    std::array<Joint, 13> rows{}; Projection result;
    for (Joint value : basis) {
        Joint right = value & RIGHT_MASK;
        while (right) {
            int bit = std::countr_zero(right);
            if (rows[bit]) { value ^= rows[bit]; right = value & RIGHT_MASK; }
            else { rows[bit] = value; break; }
        }
        if (!right) result.old.push_back(value >> 13);
    }
    for (Joint row : rows) if (row) result.right.push_back(row);
    return result;
}
std::vector<Joint> span(const std::vector<Joint>& basis) {
    std::vector<Joint> result{0};
    for (Joint value : basis) {
        size_t n = result.size();
        for (size_t j = 0; j < n; ++j) result.push_back(result[j] ^ value);
    }
    return result;
}
struct State {
    int id = 0, code = 0; uint32_t source_coset = 0;
    std::vector<Poly> old; std::vector<uint32_t> Q;
};
State parse(const std::string& line) {
    std::istringstream in(line); State result; int marks = 0;
    in >> result.id >> result.code >> result.source_coset >> marks;
    assert(in && result.id >= 0 && marks >= 1 && marks <= 2);
    for (int i = 0; i < 5; ++i) {
        std::string text; in >> text; assert(in); Poly form = parse_hex(text);
        assert(!form.bit(0)); for (int j = 0; j < 8; ++j) assert(!form.bit(1 << j));
        result.old.push_back(form);
    }
    for (int i = 0; i < marks; ++i) {
        uint32_t q = 0; in >> q; assert(in && q < (1u << 28)); result.Q.push_back(q);
    }
    std::string extra; assert(!(in >> extra));
    return result;
}
struct Witness {
    bool found = false; Joint left = 0, right = 0, cancel = 0, q_cancel = 0;
    uint32_t packed = 0; Poly candidate;
};
struct Result {
    bool complete = false; int Kdim = 0;
    uint64_t lefts = 0, pairs = 0, nonzero_cosets = 0, witness_rows = 0;
    std::array<uint64_t, 14> histogram{};
    std::vector<Joint> Kselectors; std::vector<uint32_t> Kpolars;
    std::vector<Witness> witnesses; double seconds = 0;
};
void replay(const std::vector<Poly>& forms, const std::vector<Poly>& old,
            uint32_t q, Witness& witness) {
    Poly left = select(forms, witness.left), right = select(forms, witness.right);
    Poly correction = select(old, witness.cancel), qform = select(old, witness.q_cancel);
    witness.candidate = multiply(left, right) ^ correction;
    assert(quadratic(witness.candidate) && quadratic(qform) && polar(qform) == q);
    assert(polar(witness.candidate) == witness.packed);
    assert(matrix_rank(witness.packed) == 8 && matrix_rank(witness.packed ^ q) == 8);
    assert(pfaffian(polar_rows(witness.packed)) && pfaffian(polar_rows(witness.packed ^ q)));
    for (unsigned x = 0; x < 256; ++x) {
        unsigned wires = x;
        for (int i = 0; i < 5; ++i) if (evaluate(old[i], x)) wires |= 1u << (8 + i);
        bool l = std::popcount(wires & witness.left) & 1;
        bool r = std::popcount(wires & witness.right) & 1;
        bool c = std::popcount((wires >> 8) & witness.cancel) & 1;
        bool qbit = std::popcount((wires >> 8) & witness.q_cancel) & 1;
        bool actual = (l && r) ^ c;
        assert(actual == evaluate(witness.candidate, x));
        assert((actual ^ qbit) == evaluate(witness.candidate ^ qform, x));
    }
}
Result scan(const State& state, bool force_complete = false) {
    auto start = Clock::now(); Result result; result.witnesses.resize(state.Q.size());
    std::vector<Poly> forms;
    for (int i = 0; i < 8; ++i) { Poly raw; raw.toggle(1 << i); forms.push_back(raw); }
    forms.insert(forms.end(), state.old.begin(), state.old.end());
    std::vector<Poly> old_forms(32);
    for (Joint s = 0; s < 32; ++s) {
        old_forms[s] = select(state.old, s);
        if (s) assert(!(old_forms[s] == Poly{}));
        if (quadratic(old_forms[s])) {
            result.Kselectors.push_back(s); result.Kpolars.push_back(polar(old_forms[s]));
        }
    }
    result.Kdim = std::countr_zero(result.Kselectors.size());
    assert(result.Kselectors.size() == (size_t(1) << result.Kdim));
    std::unordered_set<uint32_t> Kset(result.Kpolars.begin(), result.Kpolars.end());
    assert(Kset.size() == result.Kpolars.size());
    std::array<uint32_t, 28> Krows{};
    for (uint32_t value : result.Kpolars) while (value) {
        int bit = std::countr_zero(value);
        if (Krows[bit]) value ^= Krows[bit]; else { Krows[bit] = value; break; }
    }
    for (size_t q = 0; q < state.Q.size(); ++q) {
        assert(matrix_rank(state.Q[q]) == 8);
        auto found = std::find(result.Kpolars.begin(), result.Kpolars.end(), state.Q[q]);
        assert(found != result.Kpolars.end());
        result.witnesses[q].q_cancel = result.Kselectors[found - result.Kpolars.begin()];
    }
    std::array<std::array<Poly, 13>, 13> products{};
    std::array<bool, 256> active{};
    for (int i = 0; i < 13; ++i) for (int j = 0; j < 13; ++j) {
        products[i][j] = multiply(forms[i], forms[j]);
        terms(products[i][j], [&](int m) { if (std::popcount(unsigned(m)) > 2) active[m] = true; });
    }
    std::vector<int> monomials;
    for (int m = 0; m < 256; ++m) if (active[m]) monomials.push_back(m);
    std::array<std::vector<Joint>, 13> deltas;
    std::vector<Joint> equations(monomials.size());
    for (size_t m = 0; m < monomials.size(); ++m) {
        for (int old = 0; old < 5; ++old)
            if (state.old[old].bit(monomials[m])) equations[m] ^= 1u << (13 + old);
        for (int i = 0; i < 13; ++i) {
            Joint row = 0;
            for (int j = 0; j < 13; ++j) if (products[i][j].bit(monomials[m])) row ^= 1u << j;
            deltas[i].push_back(row);
        }
    }
    // Squares f*f=f guarantee every old high monomial is active above.
    for (const auto& old : state.old) terms(old, [&](int m) {
        if (std::popcount(unsigned(m)) > 2) assert(active[m]);
    });
    std::vector<Poly> columns(13);
    Joint previous = 0; std::unordered_set<uint32_t> seen; seen.reserve(20000);
    for (Joint left = 1; left <= RIGHT_MASK; ++left) {
        for (Joint changed = previous ^ left; changed; changed &= changed - 1) {
            int bit = std::countr_zero(changed);
            for (int j = 0; j < 13; ++j) columns[j] ^= products[bit][j];
            for (size_t m = 0; m < equations.size(); ++m) equations[m] ^= deltas[bit][m];
        }
        previous = left; ++result.lefts;
        auto kernel = row_kernel(equations, 18); auto projected = project(kernel);
        assert(projected.old.size() == size_t(result.Kdim));
        auto pure_old = span(projected.old); std::sort(pure_old.begin(), pure_old.end());
        assert(pure_old == result.Kselectors);
        int dimension = projected.right.size(); ++result.histogram[dimension];
        std::array<uint32_t, 13> images{};
        for (int i = 0; i < dimension; ++i) {
            Joint solution = projected.right[i];
            Poly candidate = select(columns, solution & RIGHT_MASK) ^ old_forms[solution >> 13];
            assert(quadratic(candidate)); images[i] = polar(candidate);
        }
        Joint solution = 0; uint32_t packed = 0;
        for (unsigned n = 1; n < (1u << dimension); ++n) {
            int bit = std::countr_zero(n);
            solution ^= projected.right[bit]; packed ^= images[bit];
            Joint right = solution & RIGHT_MASK; assert(right);
            if (right < left) continue;
            ++result.pairs;
            uint32_t key = packed;
            for (int p = 0; p < 28; ++p) if ((key >> p) & 1) key ^= Krows[p];
            if (!key || !seen.insert(key).second) continue;
            ++result.nonzero_cosets;
            for (size_t q = 0; q < state.Q.size(); ++q) if (!result.witnesses[q].found) {
                for (size_t k = 0; k < result.Kpolars.size(); ++k) {
                    uint32_t value = packed ^ result.Kpolars[k];
                    if (matrix_rank(value) != 8 || matrix_rank(value ^ state.Q[q]) != 8) continue;
                    auto& witness = result.witnesses[q]; witness.found = true;
                    witness.left = left; witness.right = right;
                    witness.cancel = (solution >> 13) ^ result.Kselectors[k]; witness.packed = value;
                    replay(forms, state.old, state.Q[q], witness); result.witness_rows += 256;
                    break;
                }
            }
            if (!force_complete && std::all_of(result.witnesses.begin(), result.witnesses.end(),
                [](const Witness& witness) { return witness.found; })) {
                result.seconds = std::chrono::duration<double>(Clock::now() - start).count(); return result;
            }
        }
    }
    result.complete = true;
    result.seconds = std::chrono::duration<double>(Clock::now() - start).count(); return result;
}
template<class T> void array_json(std::ostream& out, const T& values) {
    out << '['; bool comma = false;
    for (auto value : values) { if (comma) out << ','; out << value; comma = true; }
    out << ']';
}
void write(std::ostream& out, const State& state, const Result& result) {
    out << "{\"state_id\":" << state.id << ",\"complete\":" << (result.complete ? "true" : "false")
        << ",\"high_rank\":" << 5 - result.Kdim << ",\"K_dimension\":" << result.Kdim
        << ",\"left_forms\":" << result.lefts << ",\"eligible_unordered_pairs\":" << result.pairs
        << ",\"quadratic_nonzero_cosets\":" << result.nonzero_cosets
        << ",\"witness_truth_rows\":" << result.witness_rows
        << ",\"algorithm_seconds\":" << std::setprecision(12) << result.seconds
        << ",\"K_all_polars\":"; array_json(out, result.Kpolars);
    out << ",\"K_all_selectors\":"; array_json(out, result.Kselectors);
    out << ",\"right_kernel_dimension_histogram\":"; array_json(out, result.histogram);
    out << ",\"marks\":[";
    for (size_t q = 0; q < state.Q.size(); ++q) {
        if (q) out << ','; const auto& witness = result.witnesses[q];
        out << "{\"Q_polar\":" << state.Q[q] << ",\"Q_old_gate_selector\":" << witness.q_cancel
            << ",\"status\":\"" << (witness.found ? "positive" : result.complete ? "negative" : "unknown") << '"';
        if (witness.found) out << ",\"left_mask\":" << witness.left << ",\"right_mask\":" << witness.right
            << ",\"old_gate_selector\":" << witness.cancel << ",\"t_polar\":" << witness.packed
            << ",\"t_plus_Q_polar\":" << (witness.packed ^ state.Q[q])
            << ",\"t_anf_hex\":\"" << hex(witness.candidate) << '"';
        out << '}';
    }
    out << "]}\n";
}
void controls(std::ostream& out) {
    std::mt19937 rng(20261022); uint64_t kernels = 0, projections = 0, products = 0, ranks = 0;
    for (int width = 0; width <= 9; ++width) for (int sample = 0; sample < 32; ++sample) {
        std::vector<Joint> equations(12);
        for (auto& row : equations) row = rng() & ((1u << width) - 1);
        auto got = span(row_kernel(equations, width)); std::sort(got.begin(), got.end());
        std::vector<Joint> expected;
        for (Joint value = 0; value < (1u << width); ++value) {
            bool okay = true;
            for (Joint row : equations) if (std::popcount(row & value) & 1) okay = false;
            if (okay) expected.push_back(value);
        }
        assert(got == expected); ++kernels;
    }
    // High old-selector bits 16 and 17 are deliberately present. Check a
    // small projected problem by brute force while using actual 18-bit words.
    for (int sample = 0; sample < 64; ++sample) {
        std::vector<Joint> equations(5);
        for (auto& row : equations) row = (rng() & 31) | ((rng() & 31) << 13);
        // Force unused right coordinates 5..12 to zero.
        for (int i = 5; i < 13; ++i) equations.push_back(1u << i);
        auto projected = project(row_kernel(equations, 18));
        std::unordered_set<Joint> got;
        for (Joint solution : span(projected.right)) got.insert(solution & RIGHT_MASK);
        for (Joint right = 0; right < 32; ++right) {
            bool expected = false;
            for (Joint old = 0; old < 32; ++old) {
                Joint value = right | (old << 13); bool okay = true;
                for (Joint row : equations) if (std::popcount(row & value) & 1) okay = false;
                if (okay) expected = true;
            }
            assert(got.contains(right) == expected);
        }
        ++projections;
    }
    for (int sample = 0; sample < 128; ++sample) {
        Poly a, b;
        for (auto& word : a.words) word = uint64_t(rng()) << 32 | rng();
        for (auto& word : b.words) word = uint64_t(rng()) << 32 | rng();
        auto product = multiply(a, b);
        for (unsigned x = 0; x < 256; ++x)
            assert(evaluate(product, x) == (evaluate(a, x) && evaluate(b, x)));
        assert(parse_hex(hex(a)) == a); ++products;
    }
    for (int sample = 0; sample < 2048; ++sample) {
        uint32_t value = rng() & ((1u << 28) - 1);
        assert(pfaffian(polar_rows(value)) == (matrix_rank(value) == 8)); ++ranks;
    }
    // Explicit two-variable product does not fit in 16-bit joint selectors.
    auto last = row_kernel({(1u << 17) | 1}, 18);
    auto solutions = span(last); assert(std::find(solutions.begin(), solutions.end(), (1u << 17) | 1) != solutions.end());
    out << "{\"status\":\"pass\",\"joint_kernel_bruteforce_controls\":" << kernels
        << ",\"projected_18bit_kernel_controls\":" << projections
        << ",\"monomial_product_full_truth_controls\":" << products
        << ",\"Pfaffian_rank_controls\":" << ranks << ",\"bit17_preserved\":true}\n";
}
int main(int argc, char** argv) {
    assert(argc >= 3); std::string input = argv[1], output = argv[2];
    assert(!std::ifstream(output).good()); std::ofstream out(output); assert(out.good());
    if (input == "--controls") { controls(out); std::cout << "controls pass\n"; return 0; }
    int begin = 0, count = -1; bool force_complete = false;
    for (int i = 3; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--begin") { assert(i + 1 < argc); begin = std::stoi(argv[++i]); }
        else if (arg == "--count") { assert(i + 1 < argc); count = std::stoi(argv[++i]); }
        else { assert(arg == "--force-complete"); force_complete = true; }
    }
    assert(begin >= 0 && count >= -1); std::ifstream in(input); assert(in.good());
    auto start = Clock::now(); std::string line; int index = 0, states = 0, positives = 0, negatives = 0;
    while (std::getline(in, line)) {
        if (index++ < begin) continue;
        if (count >= 0 && states >= count) break;
        assert(!line.empty()); State state = parse(line); Result result = scan(state, force_complete);
        write(out, state, result); out.flush(); assert(out.good()); ++states;
        for (const auto& witness : result.witnesses) { positives += witness.found; negatives += !witness.found && result.complete; }
        if (states % 25 == 0) std::cout << "states=" << states << " positive=" << positives << " negative=" << negatives << std::endl;
    }
    assert(states);
    std::cout << "states=" << states << " positive=" << positives << " negative=" << negatives
        << " wall_seconds=" << std::chrono::duration<double>(Clock::now() - start).count() << std::endl;
}
