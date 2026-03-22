#!/usr/bin/env bash
# clone_sol.sh — Export the built-in Sol structure, rename it, and checksum the copy.
#
# Demonstrates the full workflow:
#   1. Dump Sol's raw JSON spec from the CLI
#   2. Save it locally as custom_sol.json
#   3. Run the StoQ checksum and display a formatted report
#   4. Run the quark-chain reconstruction and display a formatted report
#
# Requirements: python (with quarksum installed)
#
# Usage:
#   chmod +x examples/clone_sol.sh
#   ./examples/clone_sol.sh

set -euo pipefail

WORK_DIR="$(mktemp -d)"
SPEC_FILE="${WORK_DIR}/custom_sol.json"
STOQ_FILE="${WORK_DIR}/stoq_result.json"
QC_FILE="${WORK_DIR}/qc_result.json"

# Remove any leftover custom_sol.json from a previous run
if [ -f "custom_sol.json" ]; then
    echo "=== Removing existing custom_sol.json ==="
    rm -f "custom_sol.json"
fi

echo "=== Step 1: Export Sol's structure spec ==="
python -m quarksum --spec > "${SPEC_FILE}"
echo "  Saved to ${SPEC_FILE}"

echo ""
echo "=== Step 2: Rename to custom_sol ==="
if command -v jq &>/dev/null; then
    jq '.name = "custom_sol"' "${SPEC_FILE}" > "${SPEC_FILE}.tmp" && mv "${SPEC_FILE}.tmp" "${SPEC_FILE}"
else
    sed -i.bak 's/"name": "Solar System (Sun to Oort Cloud)"/"name": "custom_sol"/' "${SPEC_FILE}"
    rm -f "${SPEC_FILE}.bak"
fi
echo "  Name is now: $(python -c "import json,sys; print(json.load(open('${SPEC_FILE}'))['name'])")"

# ── Step 3: StoQ checksum ────────────────────────────────────────────────────

echo ""
echo "=== Step 3: StoQ Checksum (bare quark mass reconstruction) ==="
python -m quarksum --file "${SPEC_FILE}" 2>/dev/null > "${STOQ_FILE}"

python - "${STOQ_FILE}" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
s = d["scope_summary"]

def sci(v): return f"{v:.4e}"
def pct(v): return f"{v:+.4f}%"

print(f"""
  Structure:       {d['structure_name']}
  Stated mass:     {sci(d['stated_mass_kg'])} kg

  ── Particle Inventory ──────────────────────────
  Protons:         {sci(s['nucleons']['protons'])}
  Neutrons:        {sci(s['nucleons']['neutrons'])}
  Electrons:       {sci(s['electrons'])}
  Up quarks:       {sci(s['quarks']['up'])}
  Down quarks:     {sci(s['quarks']['down'])}
  Bodies:          {s['bodies']}
  Materials:       {s['materials']}

  ── Mass Closure ────────────────────────────────
  Reconstructed:   {sci(d['reconstructed_mass_kg'])} kg  (from bare quark + electron rest masses)
  Mass defect:     {sci(d['mass_defect_kg'])} kg
  Defect:          {pct(d['mass_defect_percent'])}
  NOTE: ~99% defect is expected — bare quark rest masses account for only
        ~1% of nucleon mass. The other 99% is QCD confinement energy.""")

if d.get("per_body"):
    print("\n  ── Per-Body Breakdown ──────────────────────────")
    for b in d["per_body"]:
        print(f"    {b['name']:30s}  mass={sci(b['stated_mass_kg'])} kg"
              f"  p={sci(b['total_protons'])}  n={sci(b['total_neutrons'])}"
              f"  e={sci(b['total_electrons'])}  defect={pct(b['mass_defect_percent'])}")
PYEOF

# ── Step 4: Quark-chain reconstruction ───────────────────────────────────────

echo ""
echo "=== Step 4: Quark-Chain Reconstruction (full binding energy budget) ==="
python -m quarksum --file "${SPEC_FILE}" --quark-chain 2>/dev/null > "${QC_FILE}"

python - "${QC_FILE}" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))

def sci(v): return f"{v:.4e}"
def pct(v): return f"{v:+.4f}%"

stated = d["stated_mass_kg"]
predicted = d["predicted_mass_kg"]

print(f"""
  Structure:       {d['structure_name']}
  Stated mass:     {sci(stated)} kg
  Atoms counted:   {d['atom_count']:.4e}

  ── Energy Budget ───────────────────────────────
  Bare quark mass:       {sci(d['bare_quark_mass_kg'])} kg
  Electron mass:         {sci(d['electron_mass_kg'])} kg
  + QCD binding:         {sci(d['qcd_binding_joules'])} J   (adds ~99% of nucleon mass)
  - Nuclear binding:     {sci(d['nuclear_binding_joules'])} J   (holds nucleus together)
  - Chemical binding:    {sci(d['chemical_binding_joules'])} J   (molecular bonds)

  ── Final Comparison ────────────────────────────
  Stated mass:           {sci(stated)} kg
  Predicted mass:        {sci(predicted)} kg
  Residual defect:       {sci(d['mass_defect_kg'])} kg  ({pct(d['mass_defect_percent'])})

  RESULT: The books {"CLOSE" if abs(d['mass_defect_percent']) < 1.0 else "are within " + pct(d['mass_defect_percent'])} — predicted mass reconstructed
          from quarks matches the stated mass to {abs(d['mass_defect_percent']):.4f}%.""")
PYEOF

echo ""
echo "=== Cleanup ==="
rm -rf "${WORK_DIR}"
echo "Done."
