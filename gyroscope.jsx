import { useState, useEffect, useRef, useCallback } from "react";

// ── Material: Steel Flywheel ────────────────────────────────────
// Same iron properties from local_library.interface.mechanical
const STEEL = {
  name: "Steel (Iron, BCC)",
  density_kg_m3: 7874,
  youngs_modulus_gpa: 212.2,
};

// ── Gyroscope Geometry ──────────────────────────────────────────
const DISK_RADIUS_M = 0.06;     // 6cm radius flywheel
const DISK_THICKNESS_M = 0.02;  // 2cm thick
const DISK_VOLUME = Math.PI * DISK_RADIUS_M ** 2 * DISK_THICKNESS_M;
const DISK_MASS_KG = STEEL.density_kg_m3 * DISK_VOLUME;

// Axle
const AXLE_LENGTH_M = 0.15;    // 15cm axle
const PIVOT_OFFSET_M = 0.10;   // disk center 10cm from pivot

// Moment of inertia: I = ½mr² (solid disk about its axis)
const I_SPIN = 0.5 * DISK_MASS_KG * DISK_RADIUS_M ** 2;

// Spin rate
const SPIN_RPM = 6000;
const SPIN_RAD_S = SPIN_RPM * 2 * Math.PI / 60;

// Angular momentum: L = Iω
const L_ANGULAR = I_SPIN * SPIN_RAD_S;

const G = 9.80665;

// Gravitational torque: τ = mgr (tries to topple)
const TORQUE_GRAVITY = DISK_MASS_KG * G * PIVOT_OFFSET_M;

// Precession rate: Ω = τ/L = mgr/(Iω)
const PRECESSION_RAD_S = TORQUE_GRAVITY / L_ANGULAR;
const PRECESSION_RPM = PRECESSION_RAD_S * 60 / (2 * Math.PI);

// Nutation frequency (fast wobble): ω_nut ≈ Iω/(I_perp)
// I_perp ≈ m × r² (tilting moment about pivot)
const I_PERP = DISK_MASS_KG * PIVOT_OFFSET_M ** 2 + I_SPIN / 2;

const W = 700;
const H = 520;

// 3D projection helpers
function project(x, y, z, cx, cy, scale, viewAngle) {
  // Simple isometric-ish projection
  const cosA = Math.cos(viewAngle);
  const sinA = Math.sin(viewAngle);
  const rx = x * cosA - z * sinA;
  const rz = x * sinA + z * cosA;
  const depth = 1 + rz * 0.001;
  return {
    px: cx + rx * scale / depth,
    py: cy - y * scale / depth + rz * 0.15 * scale / depth,
    depth: rz,
  };
}

export default function Gyroscope() {
  const canvasRef = useRef(null);
  const [spinRate, setSpinRate] = useState(SPIN_RAD_S);
  const [precAngle, setPrecAngle] = useState(0);
  const [spinAngle, setSpinAngle] = useState(0);
  const [tiltAngle, setTiltAngle] = useState(Math.PI / 12); // slight initial tilt
  const [nutPhase, setNutPhase] = useState(0);
  const [running, setRunning] = useState(true);
  const [showVectors, setShowVectors] = useState(true);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const lastRef = useRef(null);
  const animRef = useRef(null);

  const stateRef = useRef({
    spinRate: SPIN_RAD_S,
    precAngle: 0,
    spinAngle: 0,
    tiltAngle: Math.PI / 12,
    nutPhase: 0,
    time: 0,
  });

  useEffect(() => {
    if (!running) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }
    lastRef.current = null;
    const s = stateRef.current;

    const tick = (ts) => {
      if (!lastRef.current) lastRef.current = ts;
      const dtReal = (ts - lastRef.current) / 1000;
      lastRef.current = ts;
      const dt = Math.min(dtReal, 0.04);

      // Spin decays slowly (friction)
      s.spinRate *= (1 - 0.003 * dt);

      // Precession rate depends on current spin
      const L = I_SPIN * s.spinRate;
      const prec = L > 0.001 ? TORQUE_GRAVITY / L : 0;

      // Nutation: small fast oscillation
      const nutFreq = L > 0.001 ? L / I_PERP : 0;
      s.nutPhase += nutFreq * dt;
      const nutAmplitude = 0.015 / (1 + s.spinRate / 100); // smaller at high spin

      s.precAngle += prec * dt;
      s.spinAngle += s.spinRate * dt;
      s.tiltAngle = Math.PI / 12 + nutAmplitude * Math.sin(s.nutPhase);
      s.time += dt;

      // When spin gets too low, it topples
      if (s.spinRate < 5) {
        s.tiltAngle = Math.min(Math.PI / 2, s.tiltAngle + dt * 2);
      }

      setSpinRate(s.spinRate);
      setPrecAngle(s.precAngle);
      setSpinAngle(s.spinAngle);
      setTiltAngle(s.tiltAngle);
      setTimeElapsed(s.time);

      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [running]);

  const reset = useCallback(() => {
    stateRef.current = {
      spinRate: SPIN_RAD_S,
      precAngle: 0,
      spinAngle: 0,
      tiltAngle: Math.PI / 12,
      nutPhase: 0,
      time: 0,
    };
    setSpinRate(SPIN_RAD_S);
    setPrecAngle(0);
    setSpinAngle(0);
    setTiltAngle(Math.PI / 12);
    setTimeElapsed(0);
    setRunning(true);
  }, []);

  // ── Render ──────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    ctx.clearRect(0, 0, W, H);

    // Background
    const bg = ctx.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, "#12101a");
    bg.addColorStop(1, "#1a1828");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    const cx = 320;
    const cy = 280;
    const sc = 600;
    const viewAng = -0.4;

    // ── Support pedestal ──────────────────────────────────────
    ctx.fillStyle = "#3a3a4a";
    ctx.beginPath();
    ctx.moveTo(cx - 15, cy);
    ctx.lineTo(cx + 15, cy);
    ctx.lineTo(cx + 25, cy + 120);
    ctx.lineTo(cx - 25, cy + 120);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#5a5a6a";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Base
    ctx.fillStyle = "#2a2a3a";
    ctx.beginPath();
    ctx.ellipse(cx, cy + 120, 45, 12, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Pivot point
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffd93d";
    ctx.fill();

    // ── Gyroscope ─────────────────────────────────────────────
    // The axle extends from pivot, tilted and precessing
    const precCos = Math.cos(precAngle);
    const precSin = Math.sin(precAngle);
    const tiltCos = Math.cos(tiltAngle);
    const tiltSin = Math.sin(tiltAngle);

    // Axle direction in 3D (precession around Y, tilt from vertical)
    const axleDir = {
      x: tiltSin * precCos,
      y: tiltCos,
      z: tiltSin * precSin,
    };

    // Disk center position
    const diskCenter3D = {
      x: axleDir.x * PIVOT_OFFSET_M,
      y: axleDir.y * PIVOT_OFFSET_M,
      z: axleDir.z * PIVOT_OFFSET_M,
    };

    const diskProj = project(diskCenter3D.x, diskCenter3D.y, diskCenter3D.z, cx, cy, sc, viewAng);

    // Axle line
    const pivotProj = project(0, 0, 0, cx, cy, sc, viewAng);
    const axleEndProj = project(
      axleDir.x * AXLE_LENGTH_M,
      axleDir.y * AXLE_LENGTH_M,
      axleDir.z * AXLE_LENGTH_M,
      cx, cy, sc, viewAng
    );

    ctx.beginPath();
    ctx.moveTo(pivotProj.px, pivotProj.py);
    ctx.lineTo(axleEndProj.px, axleEndProj.py);
    ctx.strokeStyle = "#8a8a9a";
    ctx.lineWidth = 4;
    ctx.stroke();

    // ── Spinning disk ─────────────────────────────────────────
    // Draw as ellipse (projected circle)
    const diskSize = DISK_RADIUS_M * sc * 0.85;

    // Ellipse axes depend on viewing angle of the disk plane
    // The disk normal is along the axle
    const normalScreen = {
      x: axleEndProj.px - pivotProj.px,
      y: axleEndProj.py - pivotProj.py,
    };
    const nLen = Math.sqrt(normalScreen.x ** 2 + normalScreen.y ** 2);
    const diskTiltAngle = nLen > 0 ? Math.atan2(normalScreen.y, normalScreen.x) : 0;

    // Foreshortening: how much we see the disk edge-on
    const foreshorten = Math.abs(Math.cos(precAngle - viewAng));
    const minorAxis = Math.max(diskSize * 0.15, diskSize * foreshorten * 0.6);

    ctx.save();
    ctx.translate(diskProj.px, diskProj.py);
    ctx.rotate(diskTiltAngle + Math.PI / 2);

    // Disk shadow
    ctx.beginPath();
    ctx.ellipse(3, 3, diskSize, minorAxis, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0,0,0,0.3)";
    ctx.fill();

    // Disk body
    const diskGrad = ctx.createRadialGradient(0, 0, diskSize * 0.1, 0, 0, diskSize);
    diskGrad.addColorStop(0, "#c0c8d0");
    diskGrad.addColorStop(0.5, "#8a9aaa");
    diskGrad.addColorStop(0.8, "#6a7a8a");
    diskGrad.addColorStop(1, "#4a5a6a");
    ctx.beginPath();
    ctx.ellipse(0, 0, diskSize, minorAxis, 0, 0, Math.PI * 2);
    ctx.fillStyle = diskGrad;
    ctx.fill();
    ctx.strokeStyle = "#5a6a7a";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Spin indicator lines on disk
    const numLines = 6;
    for (let i = 0; i < numLines; i++) {
      const a = spinAngle + (i * Math.PI * 2) / numLines;
      const lx = Math.cos(a) * diskSize * 0.85;
      const ly = Math.sin(a) * minorAxis * 0.85;
      const lx2 = Math.cos(a) * diskSize * 0.4;
      const ly2 = Math.sin(a) * minorAxis * 0.4;
      ctx.beginPath();
      ctx.moveTo(lx2, ly2);
      ctx.lineTo(lx, ly);
      ctx.strokeStyle = "rgba(255,255,255,0.15)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Center hub
    ctx.beginPath();
    ctx.ellipse(0, 0, diskSize * 0.15, minorAxis * 0.15, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#aab";
    ctx.fill();

    ctx.restore();

    // ── Vector arrows ─────────────────────────────────────────
    if (showVectors) {
      // Angular momentum L (along spin axis, away from pivot)
      const Lscale = 80;
      const Lend = project(
        axleDir.x * 0.2,
        axleDir.y * 0.2,
        axleDir.z * 0.2,
        cx, cy, sc, viewAng
      );
      ctx.beginPath();
      ctx.moveTo(diskProj.px, diskProj.py);
      const lArrowX = diskProj.px + (Lend.px - pivotProj.px) * 1.5;
      const lArrowY = diskProj.py + (Lend.py - pivotProj.py) * 1.5;
      ctx.lineTo(lArrowX, lArrowY);
      ctx.strokeStyle = "#4a9eff";
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.fillStyle = "#4a9eff";
      ctx.font = "bold 12px monospace";
      ctx.textAlign = "left";
      ctx.fillText("L", lArrowX + 5, lArrowY - 5);

      // Gravity (down from disk center)
      ctx.beginPath();
      ctx.moveTo(diskProj.px, diskProj.py);
      ctx.lineTo(diskProj.px, diskProj.py + 40);
      ctx.strokeStyle = "#ff6b6b";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(diskProj.px - 4, diskProj.py + 34);
      ctx.lineTo(diskProj.px, diskProj.py + 40);
      ctx.lineTo(diskProj.px + 4, diskProj.py + 34);
      ctx.stroke();
      ctx.fillStyle = "#ff6b6b";
      ctx.fillText("mg", diskProj.px + 8, diskProj.py + 40);

      // Precession direction (tangential)
      const precTangent = {
        x: -precSin,
        y: 0,
        z: precCos,
      };
      const pEnd = project(
        diskCenter3D.x + precTangent.x * 0.04,
        diskCenter3D.y,
        diskCenter3D.z + precTangent.z * 0.04,
        cx, cy, sc, viewAng
      );
      ctx.beginPath();
      ctx.moveTo(diskProj.px, diskProj.py);
      ctx.lineTo(pEnd.px, pEnd.py);
      ctx.strokeStyle = "#6bff6b";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#6bff6b";
      ctx.fillText("Ω", pEnd.px + 5, pEnd.py);
    }

    // ── Precession trace (circle on ground) ───────────────────
    ctx.beginPath();
    const traceR = 55;
    ctx.ellipse(cx, cy + 80, traceR, traceR * 0.25, 0, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(74, 158, 255, 0.15)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 5]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Trace dot showing current precession position
    const traceX = cx + Math.cos(precAngle) * traceR;
    const traceY = cy + 80 + Math.sin(precAngle) * traceR * 0.25;
    ctx.beginPath();
    ctx.arc(traceX, traceY, 3, 0, Math.PI * 2);
    ctx.fillStyle = "#4a9eff";
    ctx.fill();

    // ── Physics Panel ─────────────────────────────────────────
    const panelX = W - 250;
    const panelY = 10;
    const panelW = 240;
    const panelH = 295;

    ctx.fillStyle = "rgba(10, 10, 20, 0.88)";
    ctx.fillRect(panelX, panelY, panelW, panelH);
    ctx.strokeStyle = "#3a3a5a";
    ctx.lineWidth = 1;
    ctx.strokeRect(panelX, panelY, panelW, panelH);

    let ly = panelY + 18;
    const lx = panelX + 10;
    const gap = 15;

    ctx.fillStyle = "#ffd93d";
    ctx.font = "bold 11px monospace";
    ctx.textAlign = "left";
    ctx.fillText("GYROSCOPE — Steel Flywheel", lx, ly); ly += gap + 3;

    ctx.fillStyle = "#aaaacc";
    ctx.font = "10px monospace";
    ctx.fillText(`ρ = ${STEEL.density_kg_m3} kg/m³`, lx, ly); ly += gap;
    ctx.fillText(`r = ${DISK_RADIUS_M * 100} cm,  t = ${DISK_THICKNESS_M * 100} cm`, lx, ly); ly += gap;
    ctx.fillText(`m = ${DISK_MASS_KG.toFixed(3)} kg`, lx, ly); ly += gap;
    ctx.fillText(`I = ½mr² = ${(I_SPIN * 1e6).toFixed(2)} × 10⁻⁶ kg·m²`, lx, ly); ly += gap;

    ly += 5;
    ctx.fillStyle = "#8888dd";
    const currentRPM = spinRate * 60 / (2 * Math.PI);
    const currentL = I_SPIN * spinRate;
    const currentPrec = currentL > 0.001 ? TORQUE_GRAVITY / currentL : 0;
    const currentPrecRPM = currentPrec * 60 / (2 * Math.PI);
    ctx.fillText(`ω = ${currentRPM.toFixed(0)} RPM`, lx, ly); ly += gap;
    ctx.fillText(`L = Iω = ${(currentL * 1000).toFixed(3)} × 10⁻³ N·m·s`, lx, ly); ly += gap;

    ly += 5;
    ctx.fillStyle = "#dd8888";
    ctx.fillText(`τ_grav = mgr = ${TORQUE_GRAVITY.toFixed(4)} N·m`, lx, ly); ly += gap;

    ly += 3;
    ctx.fillStyle = "#88dd88";
    ctx.fillText(`Ω_prec = τ/L`, lx, ly); ly += gap;
    ctx.fillText(`       = ${currentPrecRPM.toFixed(2)} RPM`, lx, ly); ly += gap;

    ly += 5;
    ctx.fillStyle = "#aaa";
    ctx.fillText(`t = ${timeElapsed.toFixed(1)} s`, lx, ly); ly += gap;

    // Spin decay bar
    const barX = panelX + 10;
    const barY = panelY + panelH - 12;
    const barW = panelW - 20;
    ctx.fillStyle = "#2a2a3a";
    ctx.fillRect(barX, barY, barW, 6);
    const spinFrac = spinRate / SPIN_RAD_S;
    ctx.fillStyle = spinFrac > 0.5 ? "#4a6aff" : spinFrac > 0.2 ? "#aa6a2a" : "#aa2a2a";
    ctx.fillRect(barX, barY, barW * spinFrac, 6);

    // Low spin warning
    if (spinRate < 50) {
      ctx.fillStyle = "rgba(255, 80, 80, 0.12)";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#ff6b6b";
      ctx.font = "bold 14px monospace";
      ctx.textAlign = "center";
      ctx.fillText("SPIN DECAYING — TOPPLING IMMINENT", W / 2, 25);
    }
  }, [spinRate, precAngle, spinAngle, tiltAngle, showVectors, timeElapsed]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      fontFamily: "monospace",
      background: "#08080f",
      padding: "20px",
      borderRadius: "12px",
      gap: "12px",
    }}>
      <div style={{ color: "#ffd93d", fontSize: "14px", fontWeight: "bold" }}>
        GYROSCOPE — Angular Momentum vs Gravity
      </div>
      <div style={{ color: "#7a7a9a", fontSize: "11px" }}>
        L = Iω resists toppling | Precession: Ω = mgr/(Iω) | Steel flywheel from our material database
      </div>

      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        style={{ borderRadius: "8px", border: "1px solid #2a2a3a" }}
      />

      <div style={{ display: "flex", gap: "10px" }}>
        <button onClick={reset} style={{
          padding: "8px 20px", background: "#3a2a4a", color: "#ddf",
          border: "none", borderRadius: "6px", fontFamily: "monospace",
          fontSize: "12px", cursor: "pointer",
        }}>
          ↺ SPIN UP
        </button>
        <button onClick={() => setRunning(r => !r)} style={{
          padding: "8px 20px", background: running ? "#4a2a2a" : "#2a4a2a",
          color: "#fff", border: "none", borderRadius: "6px",
          fontFamily: "monospace", fontSize: "12px", cursor: "pointer",
        }}>
          {running ? "⏸ PAUSE" : "▶ RESUME"}
        </button>
        <button onClick={() => setShowVectors(v => !v)} style={{
          padding: "8px 20px", background: "#1a2a3a", color: "#aac",
          border: "1px solid #3a4a5a", borderRadius: "6px",
          fontFamily: "monospace", fontSize: "12px", cursor: "pointer",
        }}>
          {showVectors ? "HIDE" : "SHOW"} VECTORS
        </button>
      </div>

      <div style={{
        color: "#556", fontSize: "10px", maxWidth: "640px",
        textAlign: "center", lineHeight: "1.5",
      }}>
        Gravity pulls down (τ = mgr = {TORQUE_GRAVITY.toFixed(4)} N·m).
        Angular momentum says "not today" (L = {(L_ANGULAR * 1000).toFixed(3)} × 10⁻³ N·m·s).
        Instead of falling, it precesses at Ω = {PRECESSION_RPM.toFixed(2)} RPM.
        Watch the spin decay — when L gets small enough, gravity wins.
      </div>
    </div>
  );
}
