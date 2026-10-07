# Specification Quality Checklist: Cargo Hazard Rules and Warehouse Staging

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable (8 automated pytest targets)
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios defined (flammable no-cert, explosive compliance gate, staging for long wait, full warehouse, unknown class, perishable adjustments, wrong-class review call, reset)
- [x] Edge cases identified (warehouse full at confirmation time, unknown cargo class, perishable weight override invariant, explosive/toxic with no allowed modes, backward compatibility for cargo with no class field)
- [x] Scope is clearly bounded (Out of Scope section)
- [x] Dependencies and assumptions identified (10 explicit assumptions + all config keys named)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (class selection + hazmat filter, compliance gate, warehouse registration, staging plan, perishable adjustments, operator cert declaration, utilisation view)
- [x] Feature meets measurable outcomes in Success Criteria
- [x] No implementation details leak into specification

## Constitution Compliance (JalSetu-specific)

- [x] P2: compute_staging_plan() and hazard filter defined as pure functions (FR-6, FR-2)
- [x] P3: Every constant named and required in data/config.yaml with source_status: assumed (FR-1, FR-8, FR-9, Assumptions 4–7)
- [x] P5: SC-1 through SC-8 are mandatory automated pytest targets
- [x] P8: All paths offline-capable; reset clears warehouses and compliance records within 1 second (FR-11)
- [x] P10: No new dependencies, auth, database; in-memory state only
- [x] P11: Hard filter exclusions in excluded list with named reasons (FR-2); no regulatory/safety text emitted (FR-5); compliance gate mandatory for restricted classes (FR-3)
- [x] P12: Staging confirmation is a two-step flow; capacity not updated on proposal (FR-7)
- [x] P13: [simulated] on all warehouse records, utilisation, compliance reviews (FR-4, FR-10)
- [x] P15: Compliance reviewer notes not sent to LLM (Assumption 9)

## Notes

All items pass. The spec is ready for `/speckit-plan` or `/speckit-clarify`.

Three deliberate design choices to flag for review:

1. **`explosive` and `toxic_corrosive` default to `allowed_modes: []`** (Assumption 3).
   This means no mode is offered for these classes by default. The rationale is that
   special road permits for explosives and toxic goods are required under Indian law but
   are not modelled here; offering road mode would be a false claim of eligibility. A
   future amendment can add `["road"]` when the permit model is implemented.

2. **Flammable default allows road and water** (Assumption 3). Flammable liquids
   (e.g. coconut oil, diesel) move routinely by road tanker and are common on Kerala
   waterways. Requiring certification for the water mode while allowing road is a
   reasonable assumed default. Tagged for verification with IWAI/PESO.

3. **Warehouse capacity at confirmation is authoritative** (FR-7). Two users proposing
   a staging plan against the same warehouse could both see "capacity available" in their
   proposals; whichever confirms first wins. This is consistent with the Feature 002
   pattern for sailing capacity and explicitly noted as not being a concurrency model.
