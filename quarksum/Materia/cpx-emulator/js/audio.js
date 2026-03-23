let audioCtx = null;
let currentOsc = null;
let currentGain = null;

function getAudioCtx() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

export function startTone(frequency) {
  stopTone();
  const ctx = getAudioCtx();
  currentOsc = ctx.createOscillator();
  currentGain = ctx.createGain();
  currentOsc.type = 'square';
  currentOsc.frequency.setValueAtTime(frequency, ctx.currentTime);
  currentGain.gain.setValueAtTime(0.15, ctx.currentTime);
  currentOsc.connect(currentGain);
  currentGain.connect(ctx.destination);
  currentOsc.start();
}

export function stopTone() {
  if (currentOsc) {
    try { currentOsc.stop(); } catch {}
    currentOsc.disconnect();
    currentOsc = null;
  }
  if (currentGain) {
    currentGain.disconnect();
    currentGain = null;
  }
}

export async function playTone(frequency, durationSec) {
  startTone(frequency);
  await new Promise(resolve => setTimeout(resolve, durationSec * 1000));
  stopTone();
}
