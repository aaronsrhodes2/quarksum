import { useState, useEffect, useRef, useCallback } from "react";

// ── Material Properties (from local_library.interface) ──────────
// These are the REAL values computed by our mechanical module.
const STEEL = {
  name: "Iron (α-ferrite, BCC)",
  density_kg_m3: 7874,
  youngs_modulus_gpa: 212.2,
  shear_modulus_gpa: 82.2,
  bulk_modulus_gpa: 168.4,
  poisson_ratio: 0.29,
  cohesive_energy_ev: 4.28,
  crystal_structure: "BCC",
  source: "local_library.interface.mechanical",
};

// ── Bar Geometry ────────────────────────────────────────────────
const BAR_LENGTH_M = 1.2; // 1.2 meter bar
const BAR_WIDTH_M = 0.05; // 5cm × 5cm cross section
const BAR_HEIGHT_M = 0.05;
const BAR_VOLUME_M3 = BAR_LENGTH_M * BAR_WIDTH_M * BAR_HEIGHT_M;
const BAR_MASS_KG = STEEL.density_kg_m3 * BAR_VOLUME_M3;

// Moment of inertia for rotation about pivot (parallel axis theorem)
// I_cm = (1/12) × m × L²   (thin rod about center)
// I_pivot = I_cm + m × d²   (shifted to pivot point)
const I_CM = (1 / 12) * BAR_MASS_KG * BAR_LENGTH_M ** 2;

// ── Box / Pivot ─────────────────────────────────────────────────
const BOX_WIDTH_M = 0.3;
const BOX_HEIGHT_M = 0.4;
const FLOOR_Y_M = 0; // floor level

// Overhang: center of gravity past the box edge by this much
const OVERHANG_FRACTION = 0.53; // 53% hangs off → CoG just past edge
const PIVOT_FROM_LEFT = BAR_LENGTH_M * (1 - OVERHANG_FRACTION);

// Distance from pivot to center of mass
const D_CM_FROM_PIVOT = BAR_LENGTH_M / 2 - PIVOT_FROM_LEFT;

// I about pivot
const I_PIVOT = I_CM + BAR_MASS_KG * D_CM_FROM_PIVOT ** 2;

const G_ACCEL = 9.80665; // m/s²

// ── Rendering Scale ─────────────────────────────────────────────
const SCALE = 320; // pixels per meter
const CANVAS_W = 700;
const CANVAS_H = 480;

// Box position in canvas coords
const BOX_LEFT_PX = 180;
const BOX_TOP_PX = CANVAS_H - BOX_HEIGHT_M * SCALE - 20;
const PIVOT_X_PX = BOX_LEFT_PX + BOX_WIDTH_M * SCALE;
const PIVOT_Y_PX = BOX_TOP_PX;
const FLOOR_Y_PX = CANVAS_H - 20;

export default function SteelBarTip() {
  const canvasRef = useRef(null);
  const [angle, setAngle] = useState(0);
  const [angularVel, setAngularVel] = useState(0);
  const [running, setRunning] = useState(false);
  const [fallen, setFallen] = useState(false);
  const [time, setTime] = useState(0);
  const [showPhysics, setShowPhysics] = useState(true);
  const animRef = useRef(null);
  const lastTimeRef = useRef(null);

  // Max angle before bar tip hits the floor
  const barTipHangLength = BAR_LENGTH_M * OVERHANG_FRACTION;
  const heightAboveFloor = BOX_HEIGHT_M;
  const maxAngle = Math.asin(Math.min(1, heightAboveFloor / barTipHangLength));

  const reset = useCallback(() => {
    setAngle(0);
    setAngularVel(0);
    setRunning(false);
    setFallen(false);
    setTime(0);
    lastTimeRef.current = null;
    if (animRef.current) cancelAnimationFrame(animRef.current);
  }, []);

  // Physics step
  const step = useCallback(
    (timestamp) => {
      if (!lastTimeRef.current) lastTimeRef.current = timestamp;
      const dtReal = (timestamp - lastTimeRef.current) / 1000;
      lastTimeRef.current = timestamp;

      // Clamp dt to avoid explosion on tab switch
      const dt = Math.min(dtReal, 0.05);

      setAngle((prev) => {
        setAngularVel((prevOmega) => {
          // Torque = m × g × d_cm × cos(angle)
          // As bar tips, moment arm = d_cm × cos(θ) (projection)
          const torque =
            BAR_MASS_KG * G_ACCEL * D_CM_FROM_PIVOT * Math.cos(prev);
          const alpha = torque / I_PIVOT;
          const newOmega = prevOmega + alpha * dt;
          return newOmega;
        });

        return prev; // angle updated below
      });

      setAngle((prev) => {
        setAngularVel((prevOmega) => {
          const newAngle = prev + prevOmega * dt;

          if (newAngle >= maxAngle) {
            setFallen(true);
            setRunning(false);
            return prevOmega;
          }

          setTime((t) => t + dt);
          return prevOmega;
        });

        // Recompute to avoid stale closure
        const torque =
          BAR_MASS_KG * G_ACCEL * D_CM_FROM_PIVOT * Math.cos(prev);
        const alpha = torque / I_PIVOT;
        const newOmega = angularVel + alpha * dt;
        const newAngle = prev + newOmega * dt;

        if (newAngle >= maxAngle) {
          return maxAngle;
        }
        return newAngle;
      });

      if (!fallen) {
        animRef.current = requestAnimationFrame(step);
      }
    },
    [fallen, angularVel, maxAngle]
  );

  // Simpler physics loop using refs
  const angleRef = useRef(0);
  const omegaRef = useRef(0);
  const timeRef = useRef(0);
  const fallenRef = useRef(false);

  const startSim = useCallback(() => {
    angleRef.current = 0;
    omegaRef.current = 0;
    timeRef.current = 0;
    fallenRef.current = false;
    setAngle(0);
    setAngularVel(0);
    setTime(0);
    setFallen(false);
    setRunning(true);
    lastTimeRef.current = null;

    const tick = (timestamp) => {
      if (!lastTimeRef.current) lastTimeRef.current = timestamp;
      const dtReal = (timestamp - lastTimeRef.current) / 1000;
      lastTimeRef.current = timestamp;
      const dt = Math.min(dtReal, 0.03);

      if (fallenRef.current) return;

      const a = angleRef.current;
      const torque = BAR_MASS_KG * G_ACCEL * D_CM_FROM_PIVOT * Math.cos(a);
      const alpha = torque / I_PIVOT;

      omegaRef.current += alpha * dt;
      angleRef.current += omegaRef.current * dt;
      timeRef.current += dt;

      if (angleRef.current >= maxAngle) {
        angleRef.current = maxAngle;
        fallenRef.current = true;
        setFallen(true);
        setRunning(false);
      }

      setAngle(angleRef.current);
      setAngularVel(omegaRef.current);
      setTime(timeRef.current);

      if (!fallenRef.current) {
        animRef.current = requestAnimationFrame(tick);
      }
    };

    animRef.current = requestAnimationFrame(tick);
  }, [maxAngle]);

  useEffect(() => {
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  // ── Drawing ─────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = CANVAS_W;
    const h = CANVAS_H;

    ctx.clearRect(0, 0, w, h);

    // Background
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, "#1a1a2e");
    bg.addColorStop(1, "#16213e");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // Floor
    ctx.fillStyle = "#2a2a3e";
    ctx.fillRect(0, FLOOR_Y_PX, w, h - FLOOR_Y_PX);
    ctx.strokeStyle = "#4a4a6e";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, FLOOR_Y_PX);
    ctx.lineTo(w, FLOOR_Y_PX);
    ctx.stroke();

    // Box
    const boxPx = {
      x: BOX_LEFT_PX,
      y: BOX_TOP_PX,
      w: BOX_WIDTH_M * SCALE,
      h: BOX_HEIGHT_M * SCALE,
    };
    ctx.fillStyle = "#3a506b";
    ctx.fillRect(boxPx.x, boxPx.y, boxPx.w, boxPx.h);
    ctx.strokeStyle = "#5a7a9b";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(boxPx.x, boxPx.y, boxPx.w, boxPx.h);

    // Box label
    ctx.fillStyle = "#8aaa bb";
    ctx.font = "11px monospace";
    ctx.textAlign = "center";
    ctx.fillStyle = "#8aaabb";
    ctx.fillText("FULCRUM", boxPx.x + boxPx.w / 2, boxPx.y + boxPx.h / 2 + 4);

    // Pivot point (top-right of box)
    const px = PIVOT_X_PX;
    const py = PIVOT_Y_PX;

    // ── Steel Bar (rotated around pivot) ──────────────────────────
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(angle); // positive = clockwise = tipping down

    const barLeftFromPivot = -PIVOT_FROM_LEFT * SCALE;
    const barRightFromPivot = (BAR_LENGTH_M - PIVOT_FROM_LEFT) * SCALE;
    const barThickness = BAR_HEIGHT_M * SCALE * 2.5; // exaggerate for visibility

    // Bar shadow
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fillRect(
      barLeftFromPivot,
      3,
      (barRightFromPivot - barLeftFromPivot),
      barThickness + 2
    );

    // Bar body — steel gradient
    const barGrad = ctx.createLinearGradient(0, -barThickness / 2, 0, barThickness / 2);
    barGrad.addColorStop(0, "#b8c4d0");
    barGrad.addColorStop(0.3, "#8a9aaa");
    barGrad.addColorStop(0.7, "#6a7a8a");
    barGrad.addColorStop(1, "#4a5a6a");
    ctx.fillStyle = barGrad;
    ctx.fillRect(
      barLeftFromPivot,
      -barThickness / 2,
      barRightFromPivot - barLeftFromPivot,
      barThickness
    );
    ctx.strokeStyle = "#5a6a7a";
    ctx.lineWidth = 1;
    ctx.strokeRect(
      barLeftFromPivot,
      -barThickness / 2,
      barRightFromPivot - barLeftFromPivot,
      barThickness
    );

    // Center of gravity marker
    const cogX = (BAR_LENGTH_M / 2 - PIVOT_FROM_LEFT) * SCALE;
    ctx.beginPath();
    ctx.arc(cogX, 0, 6, 0, Math.PI * 2);
    ctx.fillStyle = "#ff6b6b";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 8px monospace";
    ctx.textAlign = "center";
    ctx.fillText("CG", cogX, 3);

    // Weight arrow from CG
    const arrowLen = 30;
    ctx.save();
    ctx.rotate(-angle); // un-rotate so arrow points straight down
    ctx.beginPath();
    ctx.moveTo(cogX * Math.cos(angle), cogX * Math.sin(angle));
    ctx.lineTo(cogX * Math.cos(angle), cogX * Math.sin(angle) + arrowLen);
    ctx.strokeStyle = "#ff6b6b";
    ctx.lineWidth = 2;
    ctx.stroke();
    // arrowhead
    ctx.beginPath();
    ctx.moveTo(cogX * Math.cos(angle) - 4, cogX * Math.sin(angle) + arrowLen - 6);
    ctx.lineTo(cogX * Math.cos(angle), cogX * Math.sin(angle) + arrowLen);
    ctx.lineTo(cogX * Math.cos(angle) + 4, cogX * Math.sin(angle) + arrowLen - 6);
    ctx.stroke();
    ctx.fillStyle = "#ff6b6b";
    ctx.font = "10px monospace";
    ctx.textAlign = "left";
    ctx.fillText("mg", cogX * Math.cos(angle) + 8, cogX * Math.sin(angle) + arrowLen - 2);
    ctx.restore();

    ctx.restore();

    // Pivot dot
    ctx.beginPath();
    ctx.arc(px, py, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffd93d";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // ── Dimension lines ─────────────────────────────────────────
    ctx.strokeStyle = "#556";
    ctx.lineWidth = 0.5;
    ctx.setLineDash([3, 3]);

    // Overhang dimension
    const dimY = BOX_TOP_PX - 30;
    ctx.beginPath();
    ctx.moveTo(px, dimY);
    ctx.lineTo(px + BAR_LENGTH_M * OVERHANG_FRACTION * SCALE * Math.cos(angle), dimY);
    ctx.stroke();
    ctx.fillStyle = "#aab";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    const ohMid = px + (BAR_LENGTH_M * OVERHANG_FRACTION * SCALE) / 2;
    ctx.fillText(
      `${(BAR_LENGTH_M * OVERHANG_FRACTION * 100).toFixed(0)}cm overhang`,
      ohMid,
      dimY - 5
    );

    ctx.setLineDash([]);

    // ── Physics Panel ───────────────────────────────────────────
    if (showPhysics) {
      const panelX = 10;
      const panelY = 10;
      const panelW = 260;
      const panelH = 245;

      ctx.fillStyle = "rgba(10, 15, 30, 0.85)";
      ctx.fillRect(panelX, panelY, panelW, panelH);
      ctx.strokeStyle = "#3a5a7a";
      ctx.lineWidth = 1;
      ctx.strokeRect(panelX, panelY, panelW, panelH);

      ctx.fillStyle = "#ffd93d";
      ctx.font = "bold 11px monospace";
      ctx.textAlign = "left";
      let ly = panelY + 18;
      const lx = panelX + 10;
      const gap = 15;

      ctx.fillText("MATERIAL: " + STEEL.name, lx, ly);
      ly += gap + 3;
      ctx.fillStyle = "#aac";
      ctx.font = "10px monospace";
      ctx.fillText(`ρ = ${STEEL.density_kg_m3} kg/m³`, lx, ly); ly += gap;
      ctx.fillText(`E = ${STEEL.youngs_modulus_gpa.toFixed(1)} GPa`, lx, ly); ly += gap;
      ctx.fillText(`G = ${STEEL.shear_modulus_gpa.toFixed(1)} GPa`, lx, ly); ly += gap;
      ctx.fillText(`ν = ${STEEL.poisson_ratio}`, lx, ly); ly += gap;

      ly += 5;
      ctx.fillStyle = "#7a9abb";
      ctx.fillText(`Bar: ${BAR_LENGTH_M}m × ${BAR_WIDTH_M * 100}cm²`, lx, ly); ly += gap;
      ctx.fillText(`Mass: ${BAR_MASS_KG.toFixed(2)} kg`, lx, ly); ly += gap;
      ctx.fillText(`I_pivot: ${I_PIVOT.toFixed(4)} kg·m²`, lx, ly); ly += gap;
      ctx.fillText(`CoG offset: ${(D_CM_FROM_PIVOT * 100).toFixed(1)} cm`, lx, ly); ly += gap;

      ly += 5;
      ctx.fillStyle = "#ff9a6b";
      const torque = BAR_MASS_KG * G_ACCEL * D_CM_FROM_PIVOT * Math.cos(angle);
      ctx.fillText(`τ = ${torque.toFixed(3)} N·m`, lx, ly); ly += gap;
      ctx.fillText(`θ = ${(angle * 180 / Math.PI).toFixed(2)}°`, lx, ly); ly += gap;
      ctx.fillText(`ω = ${angularVel.toFixed(3)} rad/s`, lx, ly); ly += gap;
      ctx.fillText(`t = ${time.toFixed(2)} s`, lx, ly);
    }

    // ── Status ──────────────────────────────────────────────────
    if (fallen) {
      ctx.fillStyle = "rgba(255, 80, 80, 0.15)";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#ff6b6b";
      ctx.font = "bold 18px monospace";
      ctx.textAlign = "center";
      ctx.fillText("IMPACT", w / 2, 40);
      ctx.font = "12px monospace";
      ctx.fillStyle = "#ddd";
      ctx.fillText(
        `Fell in ${time.toFixed(2)}s — final ω = ${angularVel.toFixed(2)} rad/s`,
        w / 2,
        62
      );
    }
  }, [angle, angularVel, time, fallen, showPhysics]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: "monospace",
        background: "#0d1117",
        padding: "20px",
        borderRadius: "12px",
        gap: "12px",
      }}
    >
      <div style={{ color: "#ffd93d", fontSize: "14px", fontWeight: "bold" }}>
        MECHANICAL LEVERAGE TEST — Steel Bar Tipping
      </div>
      <div style={{ color: "#7a8a9a", fontSize: "11px" }}>
        Material properties from local_library.interface.mechanical
      </div>

      <canvas
        ref={canvasRef}
        width={CANVAS_W}
        height={CANVAS_H}
        style={{ borderRadius: "8px", border: "1px solid #2a3a4a" }}
      />

      <div style={{ display: "flex", gap: "10px" }}>
        <button
          onClick={startSim}
          disabled={running}
          style={{
            padding: "8px 20px",
            background: running ? "#2a3a4a" : "#1a6b3a",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            fontFamily: "monospace",
            fontSize: "12px",
            cursor: running ? "default" : "pointer",
          }}
        >
          {fallen ? "▶ REPLAY" : running ? "TIPPING..." : "▶ RELEASE BAR"}
        </button>
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
        <button
          onClick={() => setShowPhysics((p) => !p)}
          style={{
            padding: "8px 20px",
            background: "#1a2a3a",
            color: "#aac",
            border: "1px solid #3a4a5a",
            borderRadius: "6px",
            fontFamily: "monospace",
            fontSize: "12px",
            cursor: "pointer",
          }}
        >
          {showPhysics ? "HIDE" : "SHOW"} PHYSICS
        </button>
      </div>

      <div
        style={{
          color: "#556",
          fontSize: "10px",
          maxWidth: "600px",
          textAlign: "center",
          lineHeight: "1.5",
        }}
      >
        Steel density ({STEEL.density_kg_m3} kg/m³) → bar mass ({BAR_MASS_KG.toFixed(2)} kg) →
        gravitational torque ({(BAR_MASS_KG * G_ACCEL * D_CM_FROM_PIVOT).toFixed(3)} N·m) →
        angular acceleration → tip. All values from our σ-chain material database.
      </div>
    </div>
  );
}
