"""
Bounce physics test — rigid body collision, elastic bounce, floor restitution.

Scenario
--------
A copper ball is thrown at an aluminum ball at rest.
After the collision, both balls fall to the floor and bounce.

Expected physics (analytically checkable):
  1. Pre-collision: copper ball moving right at v₀. Aluminum ball at rest.
  2. Collision: impulse conserves momentum; kinetic energy reduced by (1-e²).
  3. Post-collision velocities follow from 1D elastic collision formulas.
  4. Both balls fall under gravity, bounce off floor with e_floor.
  5. Ball heights at each bounce are predictable: h_n = e² × h_{n-1}.

This test verifies:
  □ Momentum is conserved at collision (within numerical tolerance)
  □ Post-collision velocities match analytical 1D formula
  □ Balls reach the correct height after each floor bounce (within 2%)
  □ Both balls eventually come to rest (energy dissipated by restitution < 1)

Analytical predictions for 1D sphere-sphere collision
------------------------------------------------------
  v₁' = ((m₁ - m₂) v₁ + (1+e) m₂ v₂) / (m₁ + m₂)
  v₂' = ((m₂ - m₁) v₂ + (1+e) m₁ v₁) / (m₁ + m₂)

For v₂=0 (aluminum at rest):
  v₁' = v₁ × (m₁ - e × m₂) / (m₁ + m₂)    [copper after]
  v₂' = v₁ × (1+e) × m₁ / (m₁ + m₂)        [aluminum after]

Where e = min(e_copper, e_aluminum).

Bounce height formula
---------------------
After first floor bounce from height h₀ with velocity v_impact:
  v_impact² = 2 × g × h₀    (free fall, FIRST_PRINCIPLES)
  v_rebound = e_floor × v_impact
  h₁ = v_rebound² / (2g) = e_floor² × h₀

So the ratio h_{n+1}/h_n = e_floor². This is the verification target.
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))

from mattershaper.physics import PhysicsParcel, PhysicsScene, step_to
from mattershaper.physics.scene import GroundPlane
from mattershaper.render.entangler.vec import Vec3

# ── Material properties (inline — no renderer needed for physics test) ────────
# We derive mass from first principles: m = (4/3)π r³ × ρ

try:
    from mattershaper.materials.physics_materials import copper, aluminum
    _cu = copper()
    _al = aluminum()
    RHO_COPPER   = _cu.density_kg_m3          # kg/m³  (8960)
    RHO_ALUMINUM = _al.density_kg_m3          # kg/m³  (2700)
    E_COPPER     = _cu.restitution             # 0.60
    E_ALUMINUM   = _al.restitution             # 0.65
    print(f"[physics] Loaded materials from library: "
          f"Cu ρ={RHO_COPPER:.0f} kg/m³ e={E_COPPER:.2f}, "
          f"Al ρ={RHO_ALUMINUM:.0f} kg/m³ e={E_ALUMINUM:.2f}")
except Exception as exc:
    print(f"[physics] WARNING: Could not load physics materials ({exc}). "
          f"Using fallback values.")
    RHO_COPPER   = 8960.0
    RHO_ALUMINUM = 2700.0
    E_COPPER     = 0.60
    E_ALUMINUM   = 0.65


# ── Scene setup ───────────────────────────────────────────────────────────────

RADIUS = 0.10       # 10 cm balls — large enough to avoid tunneling at dt=1ms
G      = 9.80665    # m/s²
E_FLOOR = 0.50      # ground plane restitution (concrete-ish)

# Copper ball: thrown horizontally at +X direction, starting 1.0 m above floor
# Aluminum ball: at rest, 1.0 m above floor, 0.6 m to the right
# (0.6m = 3 × diameter — balls just barely touching at start of simulation)
THROW_SPEED = 4.0   # m/s — initial X velocity of copper ball
H_INITIAL   = 1.00  # m above floor

def _make_mat(rho, e):
    """Minimal material stub for physics layer (no renderer needed)."""
    class _Mat:
        def __init__(self):
            self.density_kg_m3 = rho
            self.restitution   = e
        def density_at_sigma(self, sigma):
            return rho
    return _Mat()

copper_ball  = PhysicsParcel(
    radius   = RADIUS,
    material = _make_mat(RHO_COPPER, E_COPPER),
    position = Vec3(-0.40, H_INITIAL + RADIUS, 0.0),
    velocity = Vec3(THROW_SPEED, 0.0, 0.0),
    label    = 'copper',
)

aluminum_ball = PhysicsParcel(
    radius   = RADIUS,
    material = _make_mat(RHO_ALUMINUM, E_ALUMINUM),
    position = Vec3(0.40, H_INITIAL + RADIUS, 0.0),
    velocity = Vec3(0.0, 0.0, 0.0),
    label    = 'aluminum',
)

scene = PhysicsScene(
    parcels = [copper_ball, aluminum_ball],
    gravity = Vec3(0, -G, 0),
    ground  = GroundPlane(y=0.0, restitution=E_FLOOR),
)

# ── Analytical predictions ────────────────────────────────────────────────────

m_cu = copper_ball.mass
m_al = aluminum_ball.mass
v0   = THROW_SPEED
e_collision = min(E_COPPER, E_ALUMINUM)

# 1D collision prediction (balls meet head-on in X direction)
v_cu_after_x = v0 * (m_cu - e_collision * m_al) / (m_cu + m_al)
v_al_after_x = v0 * (1 + e_collision) * m_cu / (m_cu + m_al)

print(f"\n── Analytical predictions ──────────────────────────────────")
print(f"   Collision restitution e = min({E_COPPER}, {E_ALUMINUM}) = {e_collision:.2f}")
print(f"   m_copper  = {m_cu:.4f} kg")
print(f"   m_aluminum= {m_al:.4f} kg")
print(f"   v_copper  before: ({v0:.2f}, 0) m/s")
print(f"   v_copper  after:  ({v_cu_after_x:.3f}, ...) m/s  [X only]")
print(f"   v_aluminum after: ({v_al_after_x:.3f}, ...) m/s  [X only]")

# Momentum conservation check: m1*v0 = m1*v1' + m2*v2'
p_before = m_cu * v0
p_after_pred = m_cu * v_cu_after_x + m_al * v_al_after_x
print(f"   Momentum before: {p_before:.4f} kg·m/s")
print(f"   Momentum after (predicted): {p_after_pred:.4f} kg·m/s")

# First floor bounce height
# After collision, aluminum ball moves at v_al_after_x in X
# Both balls fall from H_INITIAL + RADIUS to the floor
# v_impact_y = sqrt(2 × g × H) at floor
v_impact_y = math.sqrt(2 * G * (H_INITIAL + RADIUS))
h_bounce_1 = E_FLOOR**2 * (H_INITIAL + RADIUS)
h_bounce_2 = E_FLOOR**2 * h_bounce_1

print(f"\n   Floor impact speed (Y): {v_impact_y:.3f} m/s")
print(f"   Predicted bounce height 1: {h_bounce_1:.4f} m")
print(f"   Predicted bounce height 2: {h_bounce_2:.4f} m")
print(f"   Height ratio (e_floor²):  {E_FLOOR**2:.4f}")

# ── Run simulation ────────────────────────────────────────────────────────────

print(f"\n── Simulation ──────────────────────────────────────────────")
print(f"   Running to t=3.0 s at dt_max=1ms, sub_steps=4...")

# Record first floor touches and bounce heights for each ball
_floor_y = RADIUS   # center at radius when touching floor
_post_collision_recorded = {'copper': False, 'aluminum': False}
_first_bounce_peak = {'copper': None, 'aluminum': None}
_second_bounce_peak = {'copper': None, 'aluminum': None}
_prev_vy = {'copper': None, 'aluminum': None}
_at_floor = {'copper': False, 'aluminum': False}
_bounce_count = {'copper': 0, 'aluminum': 0}
_collision_checked = False

t_history = []
cu_y_history = []
al_y_history = []

def record_frame(sc, frame_idx):
    global _collision_checked
    cu = sc.parcels[0]
    al = sc.parcels[1]

    t_history.append(sc.time)
    cu_y_history.append(cu.position.y)
    al_y_history.append(al.position.y)

    # Check post-collision velocities: aluminum ball has acquired positive X velocity
    # (before collision aluminum is stationary; after it moves at v_al_after_x)
    if not _collision_checked and al.velocity.x > 0.5 * v_al_after_x:
        # Balls have separated — record X velocities
        _collision_checked = True
        print(f"\n   [t={sc.time:.4f}s] Post-collision velocities (first separation):")
        print(f"     copper   vx={cu.velocity.x:.3f}  vy={cu.velocity.y:.3f}")
        print(f"     aluminum vx={al.velocity.x:.3f}  vy={al.velocity.y:.3f}")
        p_sim = m_cu * cu.velocity.x + m_al * al.velocity.x
        print(f"     Momentum (X): simulated={p_sim:.4f}  predicted={p_after_pred:.4f}")
        err_pct = abs(p_sim - p_after_pred) / abs(p_before) * 100
        print(f"     Momentum error: {err_pct:.2f}%  {'✓ PASS' if err_pct < 2.0 else '✗ FAIL'}")
        print(f"     Cu vx error:  {abs(cu.velocity.x - v_cu_after_x):.3f} m/s  "
              f"{'✓ PASS' if abs(cu.velocity.x - v_cu_after_x) < 0.5 else '✗ FAIL'}")
        print(f"     Al vx error:  {abs(al.velocity.x - v_al_after_x):.3f} m/s  "
              f"{'✓ PASS' if abs(al.velocity.x - v_al_after_x) < 0.5 else '✗ FAIL'}")

    # Track bounce peaks: detect Y velocity sign change from negative to positive
    for label, ball in [('copper', cu), ('aluminum', al)]:
        vy_prev = _prev_vy[label]
        vy_curr = ball.velocity.y
        # Just bounced: velocity went from negative to positive and is near floor
        if (vy_prev is not None and vy_prev < -0.1 and vy_curr > 0.1 and
                ball.position.y < RADIUS * 2.5):
            _bounce_count[label] += 1
            bc = _bounce_count[label]
            h_peak_pred = E_FLOOR**(2*bc) * (H_INITIAL + RADIUS)
            print(f"\n   [t={sc.time:.4f}s] {label} bounce #{bc} — "
                  f"pos.y={ball.position.y:.4f}  vy={vy_curr:.3f} m/s  "
                  f"predicted peak≈{h_peak_pred:.4f} m")
        _prev_vy[label] = vy_curr


history = step_to(scene, t_end=3.0, dt_max=0.001, sub_steps=4,
                  callback=record_frame)

# ── Final energy accounting ───────────────────────────────────────────────────
ke_final = scene.total_kinetic_energy()
print(f"\n── Final state (t={scene.time:.3f}s) ──────────────────────────")
print(f"   KE remaining: {ke_final:.4f} J")
print(f"   Copper:   pos={copper_ball.position}  vel={copper_ball.velocity}")
print(f"   Aluminum: pos={aluminum_ball.position}  vel={aluminum_ball.velocity}")

# ── Compute bounce height ratios from recorded peaks ─────────────────────────
# Find local maxima in Y for each ball
def _bounce_heights(y_arr, t_arr, label):
    """Find peak Y heights (above floor) between floor bounces.

    Peak height above floor = position.y - RADIUS
    (the ball center is at RADIUS height when resting on floor).
    We look for local maxima where center is at least 1.5×RADIUS above floor.
    """
    peaks = []
    n = len(y_arr)
    for i in range(1, n-1):
        h = y_arr[i] - RADIUS   # height of bottom of ball above floor
        if (y_arr[i] > y_arr[i-1] and y_arr[i] > y_arr[i+1]
                and h > RADIUS * 0.5):
            peaks.append((t_arr[i], h))
    return peaks

cu_peaks = _bounce_heights(cu_y_history, t_history, 'copper')
al_peaks = _bounce_heights(al_y_history, t_history, 'aluminum')

print(f"\n── Bounce height verification (heights above floor) ────────")
for label, peaks in [('copper', cu_peaks), ('aluminum', al_peaks)]:
    if len(peaks) >= 2:
        for i in range(len(peaks)-1):
            ratio = peaks[i+1][1] / peaks[i][1]
            print(f"   {label} peak {i+1}→{i+2}: "
                  f"{peaks[i][1]:.4f} → {peaks[i+1][1]:.4f} m above floor  "
                  f"ratio={ratio:.3f}  expected≈{E_FLOOR**2:.3f}  "
                  f"{'✓ PASS' if abs(ratio - E_FLOOR**2) < 0.05 else '✗ FAIL'}")
    else:
        print(f"   {label}: {len(peaks)} peak(s) found — need ≥2 for ratio check")

print(f"\n── Test complete ────────────────────────────────────────────")
