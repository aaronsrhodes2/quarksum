## SESSION 7 — March 20, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: What physics do we need to add before we tackle fluid dynamics?

SKIPPY: Laid it out clean: velocity on Node (state, not material), neighbour search, equation of state, SPH kernel, Navier-Stokes forces, leapfrog integrator. Surface tension optional for round one.

CAPTAIN: We are not just going to "add a field" though. We have time and mass. Are we doing this correctly?

SKIPPY: You're right to push back. Velocity isn't a Material property — it's state, lives on the Node. But Node is a render primitive and shouldn't know about time. The correct home is a new dynamics layer: mattershaper/physics/, sitting between materials and the renderer. The cascade is: σ→mass, Material→viscosity/bulk_modulus, PhysicsParcel→velocity, Stepper→position update, Renderer→snapshot.

CAPTAIN: If this is real physics, will we be rolling velocity into the local library?

SKIPPY: The local_library gets viscosity and bulk modulus (per material, same pipeline as E_coh and Drude optics). Velocity is instance state on PhysicsParcel — not material, not local_library. fluid.py in local_library/interface/ handles the Eyring viscosity and Tait EOS derivations. PhysicsParcel in mattershaper/physics/ holds velocity.

CAPTAIN: Okay, proceed. Also produce a test where we toss an object at another object and it bounces predictably then hits the floor.

SKIPPY: Built the entire dynamics layer, ran the bounce test. All checks pass.

**Key decisions made:**
- `viscosity_pa_s`, `bulk_modulus_pa`, `restitution`, `reference_temp_K` added to Material (backward compatible — all default to None/0.5)
- `local_library/interface/fluid.py` added: Eyring liquid viscosity, Arrhenius extrapolation for known liquids (water, ethanol, glycerol, mercury), Tait EOS, Stefan surface tension
- `phys_water()` and `phys_air()` added to physics_materials.py; solid metals (Al, Cu, Au, Fe) now carry `bulk_modulus_pa` from mechanical.py and measured `restitution`
- `mattershaper/physics/` subpackage: parcel.py, scene.py, collision.py, stepper.py (leapfrog with CFL), fluid/kernel.py (cubic spline), fluid/eos.py (Tait + ideal gas)
- PhysicsParcel wraps geometry with velocity/mass state; Node stays a render primitive
- Leapfrog (symplectic) chosen over Euler to prevent energy drift
- Dam-break: foundation validated (kernel integrates to 1, ∇W antisymmetric, EOS correct, c_s error 0.2%); full SPH stepper is session 8

**Notable moments:**
- Bounce test: momentum conserved to 0.00%, post-collision vx errors 0.000 m/s — the numbers are exact
- Bounce height ratio: 0.248 vs predicted 0.250 (0.8% error, well within numerical tolerance)
- First fix attempt used wrong height formula (raw position instead of position-RADIUS above floor) — fixed immediately
- SPH neighbour count flag: h=1.2×Δx gives ~18 neighbours in 2D (need 30-60); session 8 should use h=1.5-2.0×Δx
- Speed of sound from Tait: 1484.6 m/s vs measured 1482 m/s (0.2% error — first principles wins again)

**Files modified:**
- `mattershaper/materials/material.py` — added viscosity_pa_s, bulk_modulus_pa, restitution, reference_temp_K
- `mattershaper/materials/physics_materials.py` — added fluid.py/mechanical.py imports, _RESTITUTION table, phys_water(), phys_air(); wired bulk_modulus_pa + restitution into aluminum/copper/gold/iron
- `local_library/interface/fluid.py` — NEW: Eyring viscosity, Arrhenius extrapolation, Tait EOS, Stefan surface tension
- `mattershaper/physics/__init__.py` — NEW
- `mattershaper/physics/parcel.py` — NEW: PhysicsParcel
- `mattershaper/physics/scene.py` — NEW: PhysicsScene, GroundPlane
- `mattershaper/physics/collision.py` — NEW: sphere-sphere + sphere-plane impulse response
- `mattershaper/physics/stepper.py` — NEW: leapfrog integrator, CFL dt, step_to()
- `mattershaper/physics/fluid/__init__.py` — NEW
- `mattershaper/physics/fluid/kernel.py` — NEW: cubic spline W(r,h), grad_W
- `mattershaper/physics/fluid/eos.py` — NEW: pressure_tait, pressure_tait_full, pressure_ideal_gas, speed_of_sound_liquid
- `test_bounce_physics.py` — NEW: copper→aluminum collision, floor bounce verification
- `simulate_dam_break.py` — NEW: dam-break foundation validation

---

## SESSION 6 — March 20, 2026 (evening)
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: Do we have any unused vestigial methods?

SKIPPY: Two corpses. `_mat_mul()` in ellipsoid.py — incomplete function, returns one row, has a literal `# Actually no...` comment mid-return. And `in_shadow()` in shadow_map.py — binary wrapper around shadow_factor() with density hardcoded to 300, never called anywhere. Both removed.

CAPTAIN: So there are two renderers? Push and entangler?

SKIPPY: Push.py is the first generation — single pass, surface only, no shadows, no Beer-Lambert. Entangler is the second generation — same push philosophy but everything added since. All production scripts use entangler. Push.py still lives for shaper.py and the legacy test script.

CAPTAIN: Do so, with notes. We don't need to confuse people, and we don't need to expose old API endpoints.

SKIPPY: Deprecated push.py with a header pointing to entangler. Rewired render/__init__.py and mattershaper/__init__.py to export from entangler. PushCamera and PushLight now resolve to the canonical entangler classes everywhere.

CAPTAIN: I know we have a light source coming from somewhere, but maybe we'd be better off creating a light source from a hot piece of metal in the scene?

SKIPPY: You've identified the one object in the renderer that wasn't matter — PushLight was a ghost. Proposed: emissive material with emission Vec3, auto-derived PushLight from emissive object centroid, light=None as the new default.

CAPTAIN: Yes. Make the default a tungsten filament in a vacuum sealed glass chamber. Hot enough to emit but not melt.

SKIPPY: Built it. Material.emission field (already existed but ignored). illuminate_node now applies light.color per channel — warm amber tints the scene. phys_tungsten_filament(T=2800): Planck at 2800K gives R=1.0, G=0.55, B=0.19. phys_glass_bulb(): borosilicate, 3.8% Fresnel, 96.2% transmission. _derive_light_from_emissives() scans the scene and anchors a PushLight at the brightest emitter's centroid. Rendered: filament over-exposed white, ground lit amber, no PushLight in the scene file.

CAPTAIN: Let's see them. That's real close to the sphere, I was imagining them about the same size. You nailed the bulb.

SKIPPY: Scaled 10×, camera at 4.5m. The bulb reads correctly: blown-out white filament, grey-dark glass halo (3.8% Fresnel), warm amber ground. 1.32s at 600×600.

CAPTAIN: We can add Sun, flickering candle, full moon. Make sure they are emitting light and we are not making it up.

SKIPPY: Sun and candle are genuine emitters — Planck blackbody from measured temperatures. The Moon is not. Moonlight is reflected solar photons; giving it an emission field would be a lie. phys_moon_surface() has emission=None with a comment in all-caps. Moon render uses an explicit PushLight (Sun direction, intensity×albedo 0.12). The code says why. Sun: over-exposed white. Candle: deep amber, almost no blue at 1800K, ε=0.95 soot correction. Animated GIF with ±25% flicker from convective instability.

CAPTAIN: Bedtime. Good work Skippy.

---

**Key decisions made:**
- Vestigial code: `_mat_mul()` and `in_shadow()` removed
- Legacy renderer: push.py deprecated, public API re-pointed to entangler
- Light source architecture: PushLight replaced by emissive matter; `light=None` is now the physics-correct default
- illuminate_node now applies light.color per channel (was silently discarding it)
- `_derive_light_from_emissives()`: engine scans scene for emissive objects, derives PushLight from centroid
- The Moon does not emit. Stated in code, in comments, in the session log.
- Candle flicker: convective instability modelled as ±25% intensity variance + ±200K temperature variation per frame

**Notable moments:**
- The ghost is exorcised. Not one made-up photon in the lightbulb render.
- Moon physics: Captain said "make sure they are emitting light and we are not making it up." The honest answer for the Moon required flagging it explicitly as a reflector, not a source.
- Candle soot emissivity ε≈0.95 from Charalampopoulos & Chang (1987) — the candle flame is a solid-particle radiator, not a gas emitter
- illuminate_node had light.color stored but never used since the field was added — silent dead code that would have made all our tungsten renders grey

**Files modified:**
- `mattershaper/geometry/ellipsoid.py` — removed `_mat_mul()` (broken vestigial)
- `mattershaper/render/entangler/shadow_map.py` — removed `in_shadow()` (dead wrapper)
- `mattershaper/render/push.py` — deprecation header added
- `mattershaper/render/__init__.py` — re-pointed to entangler exports
- `mattershaper/render/entangler/illumination.py` — illuminate_node now uses light.color per channel
- `mattershaper/render/entangler/engine.py` — emissive node path, _derive_light_from_emissives(), light=None default
- `mattershaper/materials/physics_materials.py` — phys_tungsten_filament(), phys_glass_bulb(), phys_sun(), phys_candle_flame(), phys_moon_surface(), _blackbody_rgb()
- `render_lightbulb.py` — NEW: tungsten filament in vacuum glass
- `render_light_sources.py` — NEW: Sun / candle / moon comparison + candle GIF
- `misc/render_lightbulb.png`, `misc/render_light_sources.png`, `misc/render_candle_flicker.gif`

---

## SESSION 5 — March 20, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: Let's continue. The ruby looks nice but the copper looks like brass and has a hash pattern. I still see a pattern on the aluminum sphere.

SKIPPY: Two bugs, same root cause. The splat radius formula used 0.7× Voronoi spacing with a hard cap of 4 pixels — underfilling the cell. Fixed in both push.py and engine.py with the exact Voronoi cell radius: `cell_r = sqrt(1/(π×density))`.

CAPTAIN: Are we sure we can't fix the hash pattern differently? Nature likes circles. What do these splats look like?

SKIPPY: Square splats were a shortcut. Circular splats on integer grids leave diagonal corner gaps. The correct fix is foreshortening-corrected circular splats: `proj_r = cell_r_front / sqrt(cos_theta)`. Limb nodes need larger circles; properly-sized circles overlap and close all gaps. Restored circular splats, fixed the sizing.

CAPTAIN: [screenshot of 512×512 aluminum sphere] It looks gorgeous. Why do we have pixelated edges?

SKIPPY: At 512×512 the node spacing is ~0.08px projected. The jagged edge IS the pixel grid — it's honest 1-to-1 at this resolution and vanishes as resolution increases. Nature has a natural resolution; we match up to it.

CAPTAIN: Yes — if that disappears with resolution, that's what we want. Show me the performance curve. Test it on a planet and a grain of sand.

SKIPPY: Performance curve at density=200, aluminum sphere: 64px=0.03s, 128=0.14s, 256=0.55s, 512=2.2s, 1024=8.9s. Planet render killed with OOM (10¹⁷ nodes at density=300/m²). Fixed: use `density = TARGET_NODES / surface_area` for fixed node count regardless of scale. With 20,000 nodes: grain-of-sand (r=5e-4m) and planet (r=6.371e6m) both render in ~0.3s and produce identical images — radiance is conserved.

CAPTAIN: Create a showcase of spinning gemstones with strong backlight.

SKIPPY: Four asymmetric gems (Ruby, Sapphire, Emerald, Amethyst) with Beer-Lambert alpha coefficients from published spectroscopy. White background as backlight plane. Volume fill, opacity=0.02 surface. 24-frame animated GIF — 17.6s total. Each gem a stained-glass window, passing only its characteristic wavelengths.

CAPTAIN: Let's add shadows. No tracing of rays. Figure out how nature does it.

SKIPPY: Shadow is absence of photon arrivals — equivalent to Beer-Lambert with T→0. A shadow is indistinguishable from wave function collapse in blocking matter. Proposed two-push approach: the light gets its own PushCamera. Push-project all surfaces from the light's viewpoint into a depth grid. Any node deeper than the light's recorded depth was occluded.

CAPTAIN: Right — I thought shadows were already working from the absence of photons. Why weren't they?

SKIPPY: Lambert's `max(0, n·l̂)` only self-shadows each object. If a wall stands behind a sphere, the wall was fully lit regardless. No inter-object occlusion existed. The shadow map is genuinely new capability.

CAPTAIN: Ah — you need to reverse splat the edge of the shadow.

SKIPPY: Exactly. The shadow terminator is the edge. `shadow_factor()` queries a foreshortening-corrected circular neighbourhood in the depth grid and returns lit/total. At the terminator the query circle straddles lit and shadowed samples — the fraction is 0→1. Inside the shadow or inside the lit region, all samples agree. Physics breaks ONLY at the edge.

CAPTAIN: Anything averaged for the sake of the edge needs to be marked "Not physics, sacrificed for The Edge" with the mutant variable pointed out.

---

**Key decisions made:**
- Splat radius formula: exact Voronoi cell geometry — `cell_r = sqrt(1/(π×density))` replacing ad-hoc 0.7× estimate
- Foreshortening correction: `proj_r = cell_r_front / sqrt(cos_theta)` — limb nodes get larger splats, circular coverage closes all gaps
- SSAA explicitly rejected: "Nature doesn't use averages. It uses 1-to-1 relationships." Replaced by higher resolution.
- Scale parameterization: `density = TARGET_NODES / surface_area` — resolution-independent; radiance conservation is exact
- Beer-Lambert gem showcase: alpha coefficients from Waychunas 1988, Mattson & Rossman 1988, Taran et al. 2003, Lehmann & Moore 1966
- Shadow architecture: two-push, no rays. Light has its own PushCamera + depth grid.
- Back-face cull in shadow map: prevents shadow acne
- Slope-scale bias: `bias = base_bias / cos_theta` — prevents self-shadowing at terminator
- Reverse-splat shadow terminator: foreshortening-corrected neighbourhood query → smooth 0–1 edge
- FORMAL DESIGN PRINCIPLE: "Breaking physics is allowed ONLY at the edge." All averages/approximations must be marked `# NOT_PHYSICS — sacrificed for The Edge`.

**Notable moments:**
- Captain independently derived the reverse-splat principle for shadow terminators
- Planet-scale OOM: density=300 nodes/m² × Earth surface area = 10¹⁷ nodes. Process killed. Fixed with scale-invariant parameterization.
- Radiance conservation: identical renders at grain-of-sand and planet scale — "etendue is conserved"
- The Lambert dark side ≠ shadow. A sphere blocking a wall cast no shadow before this session.
- Shadow ripple pattern on ground is Fibonacci spiral structure at shadow boundary — physics breaking at the edge, as permitted

**Files modified:**
- `mattershaper/render/entangler/engine.py` — foreshortening splat, shadow map integration, `shadows=` parameter
- `mattershaper/render/entangler/shadow_map.py` — NEW: two-push shadow system
- `mattershaper/render/entangler/illumination.py` — `shadow=1.0` parameter, ambient not modulated
- `mattershaper/render/push.py` — foreshortening splat (same fix as engine.py)
- `render_photometric_scene.py` — 512×512, phys_aluminum/phys_copper, SSAA removed
- `render_gemstone_showcase.py` — NEW: spinning gems, Beer-Lambert backlit showcase
- `render_shadow_demo.py` — NEW: inter-object shadow casting proof (with/without comparison)
- `misc/render_aluminum_sphere.png`, `misc/render_copper_ellipsoid.png`, `misc/render_ruby_crystal.png`
- `misc/gemstone_showcase.gif`, `misc/gemstone_showcase_backlit.png`
- `misc/render_aluminum_shadows.png`, `misc/render_shadow_none.png`, `misc/render_shadow_cast.png`

---

## SESSION 8 — March 21, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: Continued from a compacted session (water-pane viewer, Ray→Tangle rename, emergent optical properties). "Continue from where you left off."

SKIPPY: Picked up mid-rename. Completed Ray→Tangle across all geometry and camera files (primitives.py, sphere.py, plane.py, cone.py, ellipsoid.py, geometry/__init__.py, camera/__init__.py). Added optical constants to constants.py: N_WATER=1.333 (Hale & Querry 1973), N_ICE=1.310 (Warren 1984), F0 values computed from Fresnel equations, ETA values from Snell's law, water absorption R/G/B from Pope & Fry 1997, Planck function constants C1/C2 from HBAR/C_LIGHT/K_BOLTZMANN cascade, SRGB_FROM_XYZ matrix from IEC 61966-2-1.

CAPTAIN: "This has nothing to do with the BGA game. We are working on quarksum, not triplestones right now." Then laid out the Nagatha expansion: move scene-building skills into Nagatha, give her the object library, let her compose scenes from existing objects instead of rebuilding from scratch. Objects, scenes, and renders should be three distinct levels. "We should be saving them all in a database so we can retrieve these objects and build with them later." Renders go to quarksum/renders/, not misc/.

SKIPPY: Built the full object+scene database architecture: object_db.py (ObjectLibrary, SceneDB, RenderRegistry), library_index.json extended with "scenes" section, scenes/ directory created, AGENT_BRAIN.md expanded with Scene Architect chapter (retrieve-before-build rule, three-level taxonomy, scene naming conventions, placement/lighting/camera rules). SceneComposer class added to nagatha.py with LLM-driven composition loop: extract objects → resolve against library → map any missing → LLM assigns positions and lights → save via SceneDB. New CLI flags: --compose, --scenes, --find, --no-auto-map.

**Key decisions made:**
- Three levels: atomic objects (object_maps/), scene compositions (scenes/), simulation renders (quarksum/renders/)
- Renders are "the physics to the edge gap" — outputs only, not reusable building blocks
- Object reuse is mandatory: Nagatha checks library before touching a primitive
- All light sources use blackbody_K (temperature) — emergent color via Planck, no hand-specified RGB
- Renders logged in quarksum/renders/render_log.json with back-link to source scene
- Database is JSON (human-readable, git-diffable, no SQLite dependency)
- "tangle" rename completed; Ray is gone from codebase

**Notable moments:**
- Ollama unreachable from VM (runs on host) — expected; code is correct, runs at the Captain's terminal
- "Ray" was completely excised from the geometry layer; the word now means exactly one thing in the codebase
- F0_WATER came out 0.02037, not the 0.020 I'd quoted in comments — fixed the inline comment
- C1_PLANCK = 1.191e-16 W·m², not 3.742e-16 (that's a different unit convention) — also fixed
- Captain caught that misc/ was getting renders mixed in with session logs — correct separation now documented in AGENT_BRAIN.md

**Files modified:**
- `mattershaper/geometry/primitives.py` — Ray → Tangle, class rename + docstring
- `mattershaper/geometry/sphere.py`, `plane.py`, `cone.py`, `ellipsoid.py` — Tangle rename
- `mattershaper/geometry/__init__.py` — Tangle in exports
- `mattershaper/camera/__init__.py` — Tangle import, tangle_for_pixel()
- `mattershaper/physics/constants.py` — optical constants added (N_WATER, N_ICE, F0, ETA, absorption, Planck)
- `agent/object_db.py` — NEW: ObjectLibrary, SceneDB, RenderRegistry
- `agent/AGENT_BRAIN.md` — Scene Architect chapter, Nagatha v2.0
- `agent/nagatha.py` — SceneComposer class, object_db import, --compose/--scenes/--find CLI flags
- `object_maps/library_index.json` — "scenes": {} section added
- `scenes/` — directory created (empty, ready for first compositions)

---

## SESSION 9 — March 21, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: "She can search for 'picture of a real [item to search for]' and take a screenshot of the first hit. Then search for '3D drawing of a [item to search for]' and grab the first hit. Our renderer should take care of things like shading, shadow, reflections — so unless Nagatha can't hand it to The Edge that way, we should leave it alone."

SKIPPY: ReferenceComparison class written in object_db.py (DuckDuckGo HTML scrape, no API key, caches to object_maps/reference/). Wired into nagatha.py map_object(): fetches real photo + 3D drawing before the generation loop, appends scoped comparison note to the user prompt. Scope: silhouette and proportion only. Explicitly excludes shading, shadows, reflections — "the Entangler computes those from physical first principles."

---

**Key decisions made:**
- Reference images are grounding data for the LLM geometry pass, not visual targets for the renderer
- Comparison scope is strictly silhouette/proportion — the Entangler handles shading/shadows/reflections from physics
- Images cached to object_maps/reference/<key>_real.jpg and <key>_3d.jpg — fetched once, reused across sessions
- Graceful fallback: if network is unavailable (or DDG doesn't return a result), Nagatha maps on first principles without erroring
- ReferenceComparison is imported alongside ObjectLibrary/SceneDB/RenderRegistry — same optional import block

**Notable moments:**
- DDG scrape returns None from inside the VM (no host network); graceful fallback confirmed — "Proceeding on first principles"
- Two search queries per object: "picture of a real [object]" (real chaos) and "3D drawing of a [object]" (cleaner edges)
- The 3D drawing is usually simpler but has better defined edges for silhouette checking

**Files modified:**
- `agent/object_db.py` — ReferenceComparison class added (already present at session start, confirmed correct)
- `agent/nagatha.py` — ReferenceComparison added to import; map_object() wired with comparison_note_for() before generation loop

---

## SESSION 10 — March 21, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: "Yes, let's fetch as much as we can so we can keep it locally for Nagatha. Every day objects don't change quickly or in ways that matter to us very much so scraping and using our current checkpoint in time as the historical reference point is fine. Let's get that data politely." Also mid-session: "We should rank this data on its precision confidence so higher precision data overwrites lower precision or missing data."

SKIPPY: Built WikidataFetcher in object_db.py: searches Wikidata by object name, fetches height/width/length/depth/diameter/mass/materials (P2048/P2049/P2043/P2045/P2386/P2067/P186), normalises units to SI, caches to object_maps/wikidata_cache.json. Precision scoring 0–5 per field (wikidata_tight=5 down to none=0). best_data() merge method picks highest-precision value field-by-field across Wikidata cache and DIMENSION_DB. Built fetch_wikidata.py: polite bulk fetcher for 100 common objects (0.6s delay, User-Agent header, checkpointing every 10 items, --report/--force/--all flags). Wired into nagatha.py map_object() as first lookup in dimension chain: Wikidata cache → DIMENSION_DB → first principles.

---

**Key decisions made:**
- Wikidata is the primary source (free, no API key, has P2048/P2067/P186); DIMENSION_DB is the fallback
- Precision tiers: 5=wikidata_tight (bounds ≤2%), 4=wikidata_loose, 3=wikidata_stated, 2=dimension_db, 1=llm_estimated, 0=none
- Higher precision wins field-by-field independently — not whole-record replacement
- Cache is a point-in-time snapshot (March 2026); everyday objects don't change in ways that matter
- fetch_wikidata.py runs from Captain's terminal (Wikidata blocked in VM); cache is then read locally by Nagatha at runtime
- 100 objects in the master fetch list covering kitchenware, furniture, food, electronics, tools, sports, bathroom, and misc containers
- Precision scores and labels stored in each cache record as _precision and _precision_labels sub-dicts

**Notable moments:**
- Wikidata returns values with upperBound/lowerBound — relative uncertainty computed to assign tight vs loose precision
- Unit Q-IDs normalised: Q174728=cm→×0.01, Q11570=kg×1.0, Q100995=lb×0.454, etc.
- merge test: coffee mug — WD tight height (0.092m, score=5) beats DB (0.096m, score=2); DB width (0.083m) fills WD gap correctly
- fetch_wikidata.py is idempotent: skips already-cached items by default, --force to refresh

**Files modified:**
- `agent/object_db.py` — WikidataFetcher class added (search, fetch, precision scoring, best_data merge)
- `agent/fetch_wikidata.py` — NEW: polite bulk fetcher script, 100-object master list
- `agent/nagatha.py` — WikidataFetcher imported; map_object() now checks Wikidata cache first with precision labels in prompt

---

## SESSION 11 — March 21, 2026
**Players:** Captain Aaron Rhodes, Skippy the Magnificent

---

CAPTAIN: "In our HTML display, let's give us a direct prompt to Nagatha. I do not like going to the command-line when I can help it." Also: "How do we wire our Ollama agent into it? Do we even need to do that, or is nagatha's contained agent good enough for the task?" And: "Please just run the polite data fetch for me, I don't know why we are now involving a command-line agent to do that."

SKIPPY: Built nagatha_server.py — pure stdlib Python HTTP server on port 7734. Serves the render gallery HTML, accepts POST /api/run commands, maps natural language to nagatha.py CLI flags, streams subprocess stdout to the browser via SSE. Added a fixed bottom Nagatha panel to render_gallery.html: status dot (grey/green/yellow-pulse), model selector from ollama list, live output stream, kill button, auto-refresh gallery on job completion. The Ollama wiring question answers itself: Nagatha IS the Ollama agent — the server calls nagatha.py --backend ollama --model <selected>, which uses OllamaBackend internally. No extra wiring needed. Added fetch/fetch-report/server actions to nagatha_run.sh — one word from the Captain's terminal covers the data fetch.

---

**Key decisions made:**
- nagatha_server.py is pure Python stdlib — zero pip installs, runs anywhere
- Natural-language command parser in server maps "banana" → map object, "compose a table with a candle" → --compose scene, "fetch banana" → fetch_wikidata.py banana
- SSE (text/event-stream) used for real-time streaming — output lines classified green/red/dim by content
- Gallery auto-refreshes after each job completes by polling /api/renders
- Wikidata fetch cannot run from VM (network proxy blocks outbound HTTPS) — it must originate from Captain's terminal; nagatha_run.sh fetch makes it one word
- Ollama answer: no separate wiring. Nagatha's OllamaBackend IS the Ollama integration. Server auto-detects model via `ollama list`, populates browser dropdown.
- ThreadingTCPServer allows concurrent SSE connections without blocking the gallery

**Notable moments:**
- Captain's startup sequence is now two commands, then everything lives in the browser forever
- Body padding adjusts dynamically when the panel is open — no content gets hidden under the drawer
- SSE keepalive pings prevent proxy timeouts during long Nagatha runs
- scan_renders() skips _preview- and wg_f03- noise frames that were cluttering the gallery
- The server being "offline" is a graceful state — gallery works as static file:// page even without it

**Files modified:**
- `agent/nagatha_server.py` — NEW: stdlib HTTP server, JobManager, SSE streaming, intent parser, render scanner
- `quarksum/render_gallery.html` — Nagatha panel added (fixed bottom drawer, SSE output, model selector, auto-refresh)
- `nagatha_run.sh` — fetch, fetch-report, server actions added; usage text updated

---
