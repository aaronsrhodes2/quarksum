import { useState, useEffect, useRef, useCallback } from "react";

// ── Material Properties ─────────────────────────────────────────
// English longbow: European yew (Taxus baccata)
// The same elasticity framework as our steel module:
//   σ = Eε (Hooke), deflection = FL³/(3EI) (Euler-Bernoulli beam)
// Yew is special: heartwood (compression) + sapwood (tension) = natural composite.
const YEW = {
  name: "Yew (Taxus baccata)",
  density_kg_m3: 670,
  youngs_modulus_gpa: 9.5, // MEASURED: along grain
  shear_modulus_gpa: 0.8,  // MEASURED: across grain
  poisson_ratio: 0.37,     // MEASURED: typical softwood
  compressive_strength_mpa: 52, // MEASURED: heartwood
  tensile_strength_mpa: 100,    // MEASURED: sapwood
  source: "Forest Products Laboratory, Wood Handbook (USDA)",
  note: "Same E=3K(1-2ν) framework as mechanical.py — applied to wood",
};

// ── Bow Geometry (historical English longbow) ───────────────────
const BOW_LENGTH_M = 1.83;      // 6 feet (Mary Rose standard)
const LIMB_LENGTH_M = 0.85;     // each limb ~85cm working length
const BOW_WIDTH_M = 0.038;      // ~1.5 inches at widest
const BOW_DEPTH_M = 0.032;      // D-section depth ~1.25 inches
const DRAW_LENGTH_M = 0.72;     // 28 inches (full military draw)
const STRING_LENGTH_M = 1.68;   // brace height ~15cm

// Second moment of area: I = bh³/12 for rectangular section
const I_BEAM = (BOW_WIDTH_M * BOW_DEPTH_M ** 3) / 12;

// Effective stiffness per limb (cantilever beam approximation)
// k_limb ≈ 3EI / L³
const E_PA = YEW.youngs_modulus_gpa * 1e9;
const K_LIMB = (3 * E_PA * I_BEAM) / LIMB_LENGTH_M ** 3;

// Two limbs working together, plus string geometry factor (~0.6)
const K_BOW = 2 * K_LIMB * 0.6;

// Max draw force at 28 inches
const MAX_DRAW_FORCE_N = K_BOW * DRAW_LENGTH_M;
const MAX_DRAW_FORCE_LBS = MAX_DRAW_FORCE_N * 0.2248;

// Strain energy stored = ½kx²
const STRAIN_ENERGY_J = 0.5 * K_BOW * DRAW_LENGTH_M ** 2;

// Arrow: ~60g war arrow
const ARROW_MASS_KG = 0.060;
// v = √(2E_stored × efficiency / m_arrow)
const EFFICIENCY = 0.75; // ~75% energy transfer typical
const ARROW_VELOCITY = Math.sqrt(
  (2 * STRAIN_ENERGY_J * EFFICIENCY) / ARROW_MASS_KG
);

// ── Rendering ───────────────────────────────────────────────────
const W = 700;
const H = 520;

// Bow curve: cubic bezier for each limb
function computeBowShape(drawFraction) {
  // drawFraction: 0 = braced, 1 = full draw
  const cx = 350;
  const cy = 260;
  const limbLen = 180; // pixels

  // Brace curve (undrawn): slight natural curve
  const baseCurve = 15;
  // Full draw curve: limbs bend significantly
  const drawCurve = baseCurve + drawFraction * 85;

  // String pull-back
  const stringPull = drawFraction * 140; // pixels

  // Nock positions (top and bottom of bow)
  const topNock = { x: cx - baseCurve + 5, y: cy - limbLen };
  const botNock = { x: cx - baseCurve + 5, y: cy + limbLen };

  // Grip (handle)
  const grip = { x: cx, y: cy };

  // Limb control points for bend
  const topCtrl1 = { x: cx - drawCurve * 0.3, y: cy - limbLen * 0.35 };
  const topCtrl2 = { x: cx - drawCurve * 0.8, y: cy - limbLen * 0.7 };

  const botCtrl1 = { x: cx - drawCurve * 0.3, y: cy + limbLen * 0.35 };
  const botCtrl2 = { x: cx - drawCurve * 0.8, y: cy + limbLen * 0.7 };

  // String nocking point (where fingers pull)
  const stringMid = { x: cx + stringPull, y: cy };

  // Nock positions shift slightly as limbs bend
  const topNockDrawn = {
    x: cx - drawCurve * 0.9,
    y: cy - limbLen + drawFraction * 15,
  };
  const botNockDrawn = {
    x: cx - drawCurve * 0.9,
    y: cy + limbLen - drawFraction * 15,
  };

  return {
    grip,
    topNock: topNockDrawn,
    botNock: botNockDrawn,
    topCtrl1,
    topCtrl2,
    botCtrl1,
    botCtrl2,
    stringMid,
    cx,
    cy,
    limbLen,
    drawCurve,
  };
}

export default function LongbowDraw() {
  const canvasRef = useRef(null);
  const [drawFraction, setDrawFraction] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [released, setReleased] = useState(false);
  const [arrowPos, setArrowPos] = useState(0);
  const animRef = useRef(null);

  // Draw interaction
  const handleMouseDown = useCallback(
    (e) => {
      if (released) return;
      const rect = e.target.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const shape = computeBowShape(drawFraction);
      const dx = x - shape.stringMid.x;
      const dy = y - shape.stringMid.y;
      if (dx * dx + dy * dy < 1600) {
        setIsDragging(true);
      }
    },
    [drawFraction, released]
  );

  const handleMouseMove = useCallback(
    (e) => {
      if (!isDragging || released) return;
      const rect = e.target.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const shape = computeBowShape(0);
      const pull = Math.max(0, x - shape.cx);
      const frac = Math.min(1, pull / 140);
      setDrawFraction(frac);
    },
    [isDragging, released]
  );

  const handleMouseUp = useCallback(() => {
    if (isDragging && drawFraction > 0.1) {
      setIsDragging(false);
      setReleased(true);
      // Animate release
      const startFrac = drawFraction;
      const startTime = performance.now();
      const snapDuration = 80; // ms — bowstring snaps fast

      const snapBack = (ts) => {
        const elapsed = ts - startTime;
        const t = Math.min(1, elapsed / snapDuration);
        // Damped snap: overshoot then settle
        const eased = 1 - Math.cos(t * Math.PI * 1.5) * Math.exp(-t * 3);
        setDrawFraction(startFrac * Math.max(0, 1 - eased));

        if (t < 1) {
          animRef.current = requestAnimationFrame(snapBack);
        } else {
          setDrawFraction(0);
          // Arrow flies
          let arrowX = 0;
          const arrowFly = () => {
            arrowX += 12;
            setArrowPos(arrowX);
            if (arrowX < 400) {
              animRef.current = requestAnimationFrame(arrowFly);
            }
          };
          animRef.current = requestAnimationFrame(arrowFly);
        }
      };
      animRef.current = requestAnimationFrame(snapBack);
    } else {
      setIsDragging(false);
    }
  }, [isDragging, drawFraction]);

  const reset = useCallback(() => {
    setDrawFraction(0);
    setIsDragging(false);
    setReleased(false);
    setArrowPos(0);
    if (animRef.current) cancelAnimationFrame(animRef.current);
  }, []);

  // ── Drawing ─────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, W, H);

    // Background
    const bg = ctx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, "#1a1a0e");
    bg.addColorStop(1, "#0e1a0e");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    const shape = computeBowShape(drawFraction);

    // ── Bow Limbs (bezier curves with wood grain) ───────────────
    ctx.save();

    // Top limb
    ctx.beginPath();
    ctx.moveTo(shape.grip.x, shape.grip.y);
    ctx.bezierCurveTo(
      shape.topCtrl1.x, shape.topCtrl1.y,
      shape.topCtrl2.x, shape.topCtrl2.y,
      shape.topNock.x, shape.topNock.y
    );
    ctx.lineWidth = 14;
    const woodGrad = ctx.createLinearGradient(
      shape.grip.x, shape.grip.y,
      shape.topNock.x, shape.topNock.y
    );
    woodGrad.addColorStop(0, "#8B6914");
    woodGrad.addColorStop(0.3, "#A0782C");
    woodGrad.addColorStop(0.6, "#DAA520");
    woodGrad.addColorStop(1, "#B8860B");
    ctx.strokeStyle = woodGrad;
    ctx.lineCap = "round";
    ctx.stroke();

    // Top limb taper overlay
    ctx.beginPath();
    ctx.moveTo(shape.grip.x, shape.grip.y);
    ctx.bezierCurveTo(
      shape.topCtrl1.x, shape.topCtrl1.y,
      shape.topCtrl2.x, shape.topCtrl2.y,
      shape.topNock.x, shape.topNock.y
    );
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(139, 90, 20, 0.4)";
    ctx.stroke();

    // Bottom limb
    ctx.beginPath();
    ctx.moveTo(shape.grip.x, shape.grip.y);
    ctx.bezierCurveTo(
      shape.botCtrl1.x, shape.botCtrl1.y,
      shape.botCtrl2.x, shape.botCtrl2.y,
      shape.botNock.x, shape.botNock.y
    );
    ctx.lineWidth = 14;
    ctx.strokeStyle = woodGrad;
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(shape.grip.x, shape.grip.y);
    ctx.bezierCurveTo(
      shape.botCtrl1.x, shape.botCtrl1.y,
      shape.botCtrl2.x, shape.botCtrl2.y,
      shape.botNock.x, shape.botNock.y
    );
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(139, 90, 20, 0.4)";
    ctx.stroke();

    // Grip wrap
    ctx.beginPath();
    ctx.arc(shape.grip.x, shape.grip.y, 10, 0, Math.PI * 2);
    ctx.fillStyle = "#4a3520";
    ctx.fill();

    // Nock tips
    for (const nock of [shape.topNock, shape.botNock]) {
      ctx.beginPath();
      ctx.arc(nock.x, nock.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#ddd";
      ctx.fill();
    }

    // ── Bowstring ───────────────────────────────────────────────
    ctx.beginPath();
    ctx.moveTo(shape.topNock.x, shape.topNock.y);
    ctx.lineTo(shape.stringMid.x, shape.stringMid.y);
    ctx.lineTo(shape.botNock.x, shape.botNock.y);
    ctx.strokeStyle = "#e8d8b8";
    ctx.lineWidth = 2;
    ctx.stroke();

    // String nocking point (pull handle)
    if (!released) {
      ctx.beginPath();
      ctx.arc(shape.stringMid.x, shape.stringMid.y, 8, 0, Math.PI * 2);
      ctx.fillStyle = isDragging ? "#ffd93d" : "rgba(255,217,61,0.5)";
      ctx.fill();
      if (!isDragging && drawFraction < 0.05) {
        ctx.fillStyle = "#aaa";
        ctx.font = "11px monospace";
        ctx.textAlign = "left";
        ctx.fillText("← drag to draw", shape.stringMid.x + 14, shape.stringMid.y + 4);
      }
    }

    // ── Arrow ───────────────────────────────────────────────────
    if (drawFraction > 0.05 && !released) {
      // Arrow on string
      const arrowTail = shape.stringMid.x;
      const arrowHead = arrowTail - 110;
      ctx.beginPath();
      ctx.moveTo(arrowTail, shape.cy);
      ctx.lineTo(arrowHead, shape.cy);
      ctx.strokeStyle = "#c8b080";
      ctx.lineWidth = 3;
      ctx.stroke();
      // Arrowhead
      ctx.beginPath();
      ctx.moveTo(arrowHead, shape.cy);
      ctx.lineTo(arrowHead + 10, shape.cy - 6);
      ctx.lineTo(arrowHead + 10, shape.cy + 6);
      ctx.closePath();
      ctx.fillStyle = "#aaa";
      ctx.fill();
      // Fletching
      ctx.beginPath();
      ctx.moveTo(arrowTail - 5, shape.cy - 5);
      ctx.lineTo(arrowTail - 20, shape.cy - 8);
      ctx.lineTo(arrowTail - 20, shape.cy);
      ctx.fillStyle = "rgba(180,60,60,0.6)";
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(arrowTail - 5, shape.cy + 5);
      ctx.lineTo(arrowTail - 20, shape.cy + 8);
      ctx.lineTo(arrowTail - 20, shape.cy);
      ctx.fill();
    }

    // Arrow in flight
    if (released && arrowPos > 0) {
      const ax = shape.cx - 110 - arrowPos;
      if (ax > -120) {
        ctx.beginPath();
        ctx.moveTo(ax + 110, shape.cy);
        ctx.lineTo(ax, shape.cy);
        ctx.strokeStyle = "#c8b080";
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(ax, shape.cy);
        ctx.lineTo(ax + 10, shape.cy - 6);
        ctx.lineTo(ax + 10, shape.cy + 6);
        ctx.closePath();
        ctx.fillStyle = "#aaa";
        ctx.fill();
      }
    }

    ctx.restore();

    // ── Stress visualization on limbs ───────────────────────────
    if (drawFraction > 0.1) {
      const maxStrain = drawFraction * 0.02; // ~2% max surface strain
      ctx.fillStyle = `rgba(255, ${Math.floor(120 - drawFraction * 100)}, 50, ${drawFraction * 0.4})`;
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      const stressX = shape.topCtrl2.x - 40;
      const stressY = shape.topCtrl2.y - 5;
      ctx.fillText(
        `ε = ${(maxStrain * 100).toFixed(2)}%`,
        stressX,
        stressY
      );
    }

    // ── Physics Panel ───────────────────────────────────────────
    const px = W - 255;
    const py = 10;
    const pw = 245;
    const ph = 280;

    ctx.fillStyle = "rgba(10, 15, 10, 0.85)";
    ctx.fillRect(px, py, pw, ph);
    ctx.strokeStyle = "#3a5a3a";
    ctx.lineWidth = 1;
    ctx.strokeRect(px, py, pw, ph);

    let ly = py + 18;
    const lx = px + 10;
    const gap = 15;

    ctx.fillStyle = "#ffd93d";
    ctx.font = "bold 11px monospace";
    ctx.textAlign = "left";
    ctx.fillText("MATERIAL: " + YEW.name, lx, ly); ly += gap + 3;

    ctx.fillStyle = "#aac8aa";
    ctx.font = "10px monospace";
    ctx.fillText(`ρ = ${YEW.density_kg_m3} kg/m³`, lx, ly); ly += gap;
    ctx.fillText(`E = ${YEW.youngs_modulus_gpa} GPa (along grain)`, lx, ly); ly += gap;
    ctx.fillText(`σ_comp = ${YEW.compressive_strength_mpa} MPa (heart)`, lx, ly); ly += gap;
    ctx.fillText(`σ_tens = ${YEW.tensile_strength_mpa} MPa (sap)`, lx, ly); ly += gap;

    ly += 5;
    ctx.fillStyle = "#8ab88a";
    ctx.fillText(`Stave: ${BOW_LENGTH_M}m (6 ft)`, lx, ly); ly += gap;
    ctx.fillText(`I = ${(I_BEAM * 1e9).toFixed(3)} × 10⁻⁹ m⁴`, lx, ly); ly += gap;
    ctx.fillText(`k_bow = ${K_BOW.toFixed(0)} N/m`, lx, ly); ly += gap;

    ly += 5;
    ctx.fillStyle = "#e8a860";
    const currentForce = K_BOW * DRAW_LENGTH_M * drawFraction;
    const currentEnergy = 0.5 * K_BOW * (DRAW_LENGTH_M * drawFraction) ** 2;
    ctx.fillText(`Draw: ${(drawFraction * 100).toFixed(0)}%  (${(DRAW_LENGTH_M * drawFraction * 100).toFixed(0)} cm)`, lx, ly); ly += gap;
    ctx.fillText(`F = ${currentForce.toFixed(0)} N (${(currentForce * 0.2248).toFixed(0)} lbs)`, lx, ly); ly += gap;
    ctx.fillText(`E_stored = ${currentEnergy.toFixed(1)} J`, lx, ly); ly += gap;

    if (drawFraction > 0.95 || released) {
      ly += 5;
      ctx.fillStyle = "#ff9a6b";
      ctx.fillText(`Arrow: ${ARROW_MASS_KG * 1000}g war arrow`, lx, ly); ly += gap;
      ctx.fillText(`v = ${ARROW_VELOCITY.toFixed(0)} m/s (${(ARROW_VELOCITY * 3.28084).toFixed(0)} fps)`, lx, ly); ly += gap;
      ctx.fillText(`KE = ${(0.5 * ARROW_MASS_KG * ARROW_VELOCITY ** 2).toFixed(0)} J`, lx, ly);
    }

    // Draw force bar
    const barX = px + 10;
    const barY = ph + py - 10;
    const barW = pw - 20;
    ctx.fillStyle = "#2a3a2a";
    ctx.fillRect(barX, barY - 8, barW, 8);
    const fillW = barW * drawFraction;
    const forceColor = drawFraction < 0.5 ? "#4a8a4a" : drawFraction < 0.8 ? "#8a8a2a" : "#aa4a2a";
    ctx.fillStyle = forceColor;
    ctx.fillRect(barX, barY - 8, fillW, 8);

  }, [drawFraction, isDragging, released, arrowPos]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: "monospace",
        background: "#0a0f0a",
        padding: "20px",
        borderRadius: "12px",
        gap: "12px",
      }}
    >
      <div style={{ color: "#ffd93d", fontSize: "14px", fontWeight: "bold" }}>
        ENGLISH LONGBOW — Euler-Bernoulli Beam Bending
      </div>
      <div style={{ color: "#7a8a6a", fontSize: "11px" }}>
        Yew stave: E = {YEW.youngs_modulus_gpa} GPa | Same σ = Eε framework as mechanical.py
      </div>

      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        style={{
          borderRadius: "8px",
          border: "1px solid #2a3a2a",
          cursor: isDragging ? "grabbing" : "grab",
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />

      <div style={{ display: "flex", gap: "10px" }}>
        <button
          onClick={reset}
          style={{
            padding: "8px 20px",
            background: "#3a2a1a",
            color: "#ffa",
            border: "none",
            borderRadius: "6px",
            fontFamily: "monospace",
            fontSize: "12px",
            cursor: "pointer",
          }}
        >
          ↺ RESET
        </button>
      </div>

      <div
        style={{
          color: "#556",
          fontSize: "10px",
          maxWidth: "620px",
          textAlign: "center",
          lineHeight: "1.5",
        }}
      >
        Deflection = FL³/(3EI) — same Euler-Bernoulli beam theory used in structural engineering.
        Draw force at 28": ~{MAX_DRAW_FORCE_LBS.toFixed(0)} lbs.
        Stored energy: {STRAIN_ENERGY_J.toFixed(0)} J → {ARROW_VELOCITY.toFixed(0)} m/s arrow velocity.
        Mary Rose longbows (1545) pulled 100-185 lbs.
      </div>
    </div>
  );
}
