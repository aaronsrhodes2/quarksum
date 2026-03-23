# Non-Observer Viewpoint — Architecture Note

## Core Idea
The default camera mode is NON-OBSERVER: light is fixed in world space.
The photons were already there before you looked. Moving the camera
changes YOUR perspective, not the physics. The quarks are undisturbed.

Toggle to OBSERVER mode: light travels with camera. You brought a
flashlight. You are part of the system. The measurement apparatus
affects the result.

## Implementation (golden_vase.html)
- `u_observer` uniform: 0 = non-observer, 1 = observer
- `lightFixed = vec3(4.0, 4.0, 6.0)` — world-space (non-observer)
- `lightAttached = ro + right*2 + up*3 + forward*1` — camera-attached
- `lightPos = mix(lightFixed, lightAttached, u_observer)`

## Implications for Media Experience
- Observer detection changes when the viewer is decoupled from illumination
- In non-observer mode: specular highlights shift with camera angle but
  shadow positions are invariant — the scene exists independent of the viewer
- In observer mode: everything shifts — the viewer IS the experiment
- This distinction is fundamental to how the rendering communicates physics

## Future: Entanglement Bi-Directional Effect
- Effect increases with decreased distance from target (as a scaler)
- When we reach Layer 5 (continuous σ field), this modulates coupling
  strength between nearby field points
- Proximity drives precision — same principle as the ray marcher's
  adaptive step size
- The field tells you how much to care

## Connection to □σ = −ξR
The field equation doesn't include an observer term. σ(x) exists at
every point regardless of measurement. The non-observer viewpoint is
the honest rendering of this fact. Observer mode is the compromise
we make when we need to interact with the system.

## Date
2026-03-15
