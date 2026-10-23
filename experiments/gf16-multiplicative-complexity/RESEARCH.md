# GF(16) research and prior-art ledger

## 2026-10-23 — revision 1 and primary-source refresh

Exact question: determine unrestricted XOR-AND multiplicative complexity of
reduced GF(16) multiplication on eight input bits and four outputs. This is a
new contract for an existing research line, not a new mathematical result.
Historical tools, reports, and reviewed proofs remain in their original
[AES research directory](../aes-256-gcm/RESEARCH.md). The completed AES baseline
has not become incomplete because this separate question remains open.

The [machine ledger](PRIOR_ART.json) records exact queries and source facts.
Queries were run through web search on 2026-10-23; relevant primary pages/PDFs
were opened, not accepted solely from snippets. This is a bounded search, not
an exhaustive priority audit. No source corpus or author evidence pack was
downloaded or executed in this refresh.

### Closest results and model boundaries

| Primary source | Fact checked | Difference or limitation |
| --- | --- | --- |
| [Boyar–Find, July 24, 2015 PDF, Sections 2.1 and 5](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=919080) | Distinguishes quadratic/bilinear from general XOR-AND circuits; reports quadratic optimality for one/two-output quadratic maps and poses the more general finite-field question. | Existence of an optimal quadratic implementation does not preserve every actual circuit's old wires. This older open-problem statement alone does not establish the field's current state. |
| [MF-167 author entry, published September 4, 2026](https://slopdealer.com/research/papers/mf-167/) | Lists restricted quadratic GF(16) complexity nine and unrestricted GF(16) complexity in `[8,9]`. | The author explicitly leaves priority for the stronger quadratic result unverified. This refresh did not independently audit its complete proof/evidence pack; do not claim the restricted result as ours. |
| [ML-076 author entry, published September 4, 2026](https://slopdealer.com/research/papers/ml-076/) | Records the unrestricted reduced-field `[8,9]` question and possible algebraic/direct-refutation routes. | A register's open label is not exhaustive evidence of worldwide novelty. Its adjacent polynomial-multiplication bracket must be checked against newer/different sources rather than copied as current consensus. |
| [Morse, arXiv:2608.30238v1, August 31, 2026, Abstract and theorem 9.1](https://arxiv.org/html/2608.30238v1) | States unrestricted complexity nine for the seven coefficients of the unreduced four-term polynomial product. | This is an eight-input/seven-output map, not the reduced eight-input/four-output field map. Its lower bound does not automatically transfer through output reduction. The linked Lean development and claimed axiom audit were not executed here. |
| [Mirwald–Schnorr, DOI 10.1016/0304-3975(92)90235-8](https://www.sciencedirect.com/science/article/pii/0304397592902358) | Located the original 1992 paper and bibliographic/abstract record. | Full publisher fetch returned HTTP 403; the original full proof was not inspected in this refresh. Record this access limit rather than turning a secondary statement into a newly verified proof. |

### Decision

Novelty status: **unverified**. The existing normalizations, replay tools, and
conditional branch exclusions are local research progress; no global reduced
GF(16) lower bound, full eight-AND witness, world first, or physical improvement
has been established by this refresh. The newest nearby theorem must be treated
as prior art for its actual map, not silently extended to ours.

Continue by closing the final audit dependency of already-computed scans.
Consult [generated current status](STATUS.md) for the live evidence state.
Then review one of the remaining `r4=6,r3=4/5` or `r4=7` cases against these
sources before allocating a major campaign. A source that already settles the
exact reduced-field question would change the next milestone to independent
reproduction or another explicitly justified question.

### Future entries

Append dated searches and decision changes; do not rewrite old run checkpoints
as if they had known later outcomes. Each material claim should identify the
closest prior result, exact model/map difference, proof or replay status,
unavailable evidence, and a continue/pivot reason. Refresh primary-source
searches before major campaigns and publication, not only when asked whether a
result is novel. Failure to find a result is never proof of priority.
