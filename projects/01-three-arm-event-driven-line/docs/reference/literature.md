# Literature

Academic and technical sources the architecture actually draws on. Each entry says what it
gave us.

> **Citations verified 2026-08-24** — author lists, venues, volumes, and page ranges
> checked against the CrossRef API by DOI, the arXiv API by identifier, and the NIST
> publication record. Two errors were corrected in the process: the Cao et al. title was
> recorded with its two halves transposed, and the Ghzouli et al. author list was missing
> its fifth author. Check a citation before adding it; it takes one `curl`.

## Digital twin classification

**Kritzinger, W., Karner, M., Traar, G., Henjes, J., Sihn, W. (2018).**
*Digital Twin in manufacturing: A categorical literature review and classification.*
IFAC-PapersOnLine, 51(11), 1016–1022.
<https://www.sciencedirect.com/science/article/pii/S2405896318316021>

The canonical classification, by degree of information-flow automation:

| Term | Information flow |
|---|---|
| Digital Model | No automated exchange in either direction |
| Digital Shadow | Automated physical → virtual |
| Digital Twin | Automated bidirectional |

**What it gave us:** the vocabulary for our maturity levels, and the reason we renamed
them. Our charter draft used "Mirror" for automated physical → virtual and "Shadow" for
the divergence-measuring stage — the opposite of this paper's usage. Renamed in charter
v1.2 ([ADR-0011](../adr/0011-twin-maturity-model-and-modes.md)).

**Where we extend it:** this classification asks whether information flows automatically.
It does not ask whether the model is *correct*. Our L2 (Validated) adds that question,
because a shadow whose divergence nobody measures is an assertion rather than a twin.

## ISO 23247 in practice

**Cao, H., Söderlund, H., Fang, Q., et al. (2025).**
*Towards AI-based Sustainable and XR-based human-centric manufacturing: Implementation of
ISO 23247 for digital twins of production systems.*
arXiv:2508.14580 [cs.HC], submitted 20 August 2025.
<https://arxiv.org/abs/2508.14580> · <https://doi.org/10.48550/arXiv.2508.14580>
Preprint — 13 authors; not, as far as we checked, peer-reviewed and published elsewhere.

A practical ISO 23247 implementation on a lab-scale production line — conveyor, assembly
stations, PLC control, RFID-tagged pallets, real-time bidirectional connectivity.

**What it gave us:** confirmation that ISO 23247 has been applied to a system of the same
class as ours, and a worked example of instantiating its reference architecture rather
than only citing it. Also useful as a description of what the industrial (non-ROS)
approach looks like — OPC UA, CODESYS, a commercial simulation package — which is the
alternative our stack is chosen against.

**Standardized approach overview.** Shao, G., Kibira, D., Frechette, S.P. (NIST, published
26 October 2024). *Digital Twins for Advanced Manufacturing: The Standardized Approach.*
<https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957417> — 20 pages, freely
downloadable. Accessible summary of the standards landscape from one of the standard's
contributing institutions.

## Behaviour trees and orchestration

**Ghzouli, R., Berger, T., Johnsen, E.B., Wąsowski, A., Dragule, S. (2023).**
*Behavior Trees and State Machines in Robotics Applications.*
IEEE Transactions on Software Engineering, 49(9), 4243–4267.
<https://arxiv.org/abs/2208.04211> · <https://doi.org/10.1109/TSE.2023.3269081>

A comparative analysis of both formalisms in real robotics codebases.

**What it gave us:** grounding for [ADR-0007](../adr/0007-behaviour-trees-for-orchestration.md)
beyond preference. Two points carried most weight: the two formalisms are comparable in
expressive power, so the choice turns on secondary properties — composability, how
recovery is expressed, runtime inspectability — and ROS's own trajectory is evidence, with
ROS 1 navigation orchestrated by hierarchical state machines and ROS 2's Nav2 changing its
primary customization mechanism to behaviour trees.

**BehaviorTree.CPP documentation.** <https://www.behaviortree.dev/docs/ros2_integration/>
The recommended pattern: a centralized coordinator node owning behaviour execution, with
other components service-oriented and delegating decisions to it. Matches our L3/L4 split.

## Reading order

New to digital twins as a field: Kritzinger first — it is short and it fixes the
vocabulary. Then the NIST overview for the standards landscape. Then our own
[`../architecture/standards-alignment.md`](../architecture/standards-alignment.md), which
is where the two meet this project.

New to behaviour trees: the BehaviorTree.CPP documentation before the comparative paper.
The paper is more useful once you have seen a tree.
