// Exhaust independent two-planes of raw8 + four disjoint products, mod constants.
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <vector>

using U = uint16_t;
using Key = uint32_t;

Key canonical(U a, U b) {
    assert(a && b && a != b);
    U c = a ^ b;
    if (a > b) std::swap(a, b);
    if (b > c) std::swap(b, c);
    if (a > b) std::swap(a, b);
    return Key(a) | (Key(b) << 12);
}

U transform(U x, int kind, int block) {
    int a = 2*block, b = a+1, p = 8+block;
    if (kind == 0) return x ^ ((((x >> a) ^ (x >> b)) & 1) * ((1 << a) | (1 << b)));
    if (kind == 1) return x ^ ((((x >> a) ^ (x >> p)) & 1) << b);
    if (kind == 2) return x ^ (((x >> p) & 1) << b);
    if (kind == 3) return x ^ (((x >> p) & 1) << a);
    assert(kind == 4 && block < 3);
    U result = 0;
    for (int i = 0; i < 4; ++i) {
        int j = i == block ? block+1 : i == block+1 ? block : i;
        result |= ((x >> (2*i)) & 3) << (2*j);
        result |= ((x >> (8+i)) & 1) << (8+j);
    }
    return result;
}

bool evaluate(U x, int point) {
    int value = std::popcount(unsigned(x & point & 255)) & 1;
    for (int i = 0; i < 4; ++i)
        if (((x >> (8+i)) & 1) && ((point >> (2*i)) & 3) == 3) value ^= 1;
    return value;
}

struct Seed { int degree; std::string anf; };
Seed seed(U a, U b) {
    std::array<int,256> f{};
    for (int point = 0; point < 256; ++point) f[point] = evaluate(a, point) && evaluate(b, point);
    for (int bit = 0; bit < 8; ++bit)
        for (int mask = 0; mask < 256; ++mask)
            if (mask & (1 << bit)) f[mask] ^= f[mask ^ (1 << bit)];
    std::array<uint64_t,4> words{};
    int degree = -1;
    for (int mask = 0; mask < 256; ++mask) if (f[mask]) {
        words[mask/64] |= uint64_t(1) << (mask%64);
        degree = std::max(degree, int(std::popcount(unsigned(mask))));
    }
    std::ostringstream out;
    out << "0x" << std::hex << std::setfill('0');
    for (int i = 3; i >= 0; --i) out << std::setw(16) << words[i];
    return {degree, out.str()};
}

struct Orbit { U a, b; uint64_t size; Seed s; };

int main(int argc, char** argv) {
    assert(argc == 2);
    assert(!std::ifstream(argv[1]).good());
    auto start = std::chrono::steady_clock::now();
    std::vector<std::array<U,4096>> maps;
    for (int block = 0; block < 4; ++block) for (int kind = 0; kind < 4; ++kind) {
        std::array<U,4096> row{};
        for (int x = 0; x < 4096; ++x) row[x] = transform(x, kind, block);
        maps.push_back(row);
    }
    for (int block = 0; block < 3; ++block) {
        std::array<U,4096> row{};
        for (int x = 0; x < 4096; ++x) row[x] = transform(x, 4, block);
        maps.push_back(row);
    }
    assert(maps.size() == 19);
    for (auto& row : maps) {
        std::array<bool,4096> seen{};
        for (auto value : row) { assert(!seen[value]); seen[value] = true; }
        assert(row[0] == 0 && (row[0xf00] >> 8) == 15);
    }
    std::vector<uint8_t> visited(1 << 24);
    std::vector<Key> queue;
    queue.reserve(2794155);
    std::vector<Orbit> orbits;
    uint64_t total = 0;
    for (U a = 1; a < 4096; ++a) for (U b = a+1; b < 4096; ++b) {
        if ((a ^ b) < b) continue;
        Key key = Key(a) | (Key(b) << 12);
        if (visited[key]) continue;
        queue.clear(); queue.push_back(key); visited[key] = 1;
        for (size_t cursor = 0; cursor < queue.size(); ++cursor) {
            U u = queue[cursor] & 4095, v = queue[cursor] >> 12;
            for (auto& row : maps) {
                Key next = canonical(row[u], row[v]);
                if (!visited[next]) { visited[next] = 1; queue.push_back(next); }
            }
        }
        assert(7962624 % queue.size() == 0);
        total += queue.size();
        orbits.push_back({a,b,queue.size(),seed(a,b)});
    }
    assert(total == 2794155);
    std::map<int,uint64_t> classes, planes;
    for (auto& orbit : orbits) { ++classes[orbit.s.degree]; planes[orbit.s.degree] += orbit.size; }
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::ofstream out(argv[1]); assert(out.good());
    out << "{\n  \"status\":\"pass\",\n  \"all_independent_operand_planes\":" << total
        << ",\n  \"group_order\":7962624,\n  \"generators\":19,\n  \"plane_orbits\":" << orbits.size()
        << ",\n  \"algorithm_seconds\":" << seconds << ",\n  \"orbits\":[\n";
    for (size_t i = 0; i < orbits.size(); ++i) {
        auto& o = orbits[i];
        if (i) out << ",\n";
        out << "    {\"index\":" << i << ",\"factor_masks\":[" << o.a << ',' << o.b
            << "],\"orbit_size\":" << o.size << ",\"seed_degree\":" << o.s.degree
            << ",\"seed_ANF_hex\":\"" << o.s.anf << "\"}";
    }
    out << "\n  ],\n  \"degree_classes\":{";
    bool comma = false;
    for (auto [degree,count] : classes) {
        if (comma) out << ','; comma = true;
        out << '"' << degree << "\":{\"orbits\":" << count << ",\"planes\":" << planes[degree] << '}';
    }
    out << "},\n  \"scope\":\"Operand-plane orbits only; target orientation transported jointly. Not a multiplier exclusion.\"\n}\n";
    std::cout << "{\"status\":\"pass\",\"planes\":" << total << ",\"orbits\":" << orbits.size()
              << ",\"algorithm_seconds\":" << seconds << "}" << std::endl;
}
