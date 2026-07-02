"""Truth-contract version anchor (D21; see `docs/truth_contract.md`).

The single source for the contract version stamped into every record (TC-2), so an
audit entry remains interpretable after the engine's rigor is upgraded and rigor is
comparable across versions. Bump per the monotonic rule: minor for a strengthening,
major for a structural change to what is guaranteed.
"""

# 1.1 (2026-06-30, D22): outcome honesty refined — refuse-to-adjudicate becomes a
#     first-class fifth outcome, distinct from abstain. Strengthening → minor bump.
# 1.0 (2026-06-29, D21): initial declaration.
CONTRACT_VERSION = "1.1"
