import { Board } from './board.js';
import { initPyodide, runCode, stopCode, setCallbacks, updateSensor, isRunning } from './emulator.js';
import { stopTone } from './audio.js';

// ═══ Example Programs ═══
const EXAMPLES = {
  neopixel_rainbow: `from adafruit_circuitplayground import cp
import time

cp.pixels.brightness = 0.3

def wheel(pos):
    """Color wheel: 0-255 input -> (r, g, b) output."""
    if pos < 85:
        return (int(pos * 3), int(255 - pos * 3), 0)
    elif pos < 170:
        pos -= 85
        return (int(255 - pos * 3), 0, int(pos * 3))
    else:
        pos -= 170
        return (0, int(pos * 3), int(255 - pos * 3))

offset = 0
while True:
    for i in range(10):
        color_idx = (i * 256 // 10 + offset) % 256
        cp.pixels[i] = wheel(color_idx)
    offset = (offset + 8) % 256
    time.sleep(0.05)
`,

  button_lights: `from adafruit_circuitplayground import cp
import time

cp.pixels.brightness = 0.3

while True:
    if cp.button_a:
        cp.pixels.fill((255, 0, 0))
        cp.play_tone(262, 0.2)
    elif cp.button_b:
        cp.pixels.fill((0, 0, 255))
        cp.play_tone(330, 0.2)
    else:
        cp.pixels.fill((0, 0, 0))
    
    cp.red_led = cp.button_a or cp.button_b
    time.sleep(0.05)
`,

  temp_monitor: `from adafruit_circuitplayground import cp
import time

cp.pixels.brightness = 0.2

while True:
    temp = cp.temperature
    print(f"Temperature: {temp:.1f} C")
    
    # Map temperature to color: cold=blue, warm=green, hot=red
    if temp < 10:
        color = (0, 0, 255)
    elif temp < 20:
        ratio = (temp - 10) / 10
        color = (0, int(255 * ratio), int(255 * (1 - ratio)))
    elif temp < 30:
        ratio = (temp - 20) / 10
        color = (int(255 * ratio), int(255 * (1 - ratio)), 0)
    else:
        color = (255, 0, 0)
    
    # Number of lit pixels based on temperature
    num_lit = max(1, min(10, int((temp + 10) / 6)))
    for i in range(10):
        cp.pixels[i] = color if i < num_lit else (0, 0, 0)
    
    time.sleep(0.5)
`,

  light_meter: `from adafruit_circuitplayground import cp
import time

cp.pixels.brightness = 0.2

while True:
    light = cp.light
    print(f"Light level: {light}")
    
    # Map 0-1023 to 0-10 pixels
    num_lit = max(0, min(10, int(light / 102.3)))
    
    for i in range(10):
        if i < num_lit:
            brightness = int(128 + 127 * (i / 9))
            cp.pixels[i] = (0, brightness, brightness)
        else:
            cp.pixels[i] = (0, 0, 0)
    
    time.sleep(0.1)
`,

  touch_piano: `from adafruit_circuitplayground import cp
import time

# Musical notes (Hz) mapped to touch pads A1-A7
NOTES = {
    'A1': 262,  # C4
    'A2': 294,  # D4
    'A3': 330,  # E4
    'A4': 349,  # F4
    'A5': 392,  # G4
    'A6': 440,  # A4
    'A7': 494,  # B4
}

COLORS = {
    'A1': (255, 0, 0),
    'A2': (255, 127, 0),
    'A3': (255, 255, 0),
    'A4': (0, 255, 0),
    'A5': (0, 0, 255),
    'A6': (75, 0, 130),
    'A7': (148, 0, 211),
}

cp.pixels.brightness = 0.3

while True:
    touched = False
    for pad, freq in NOTES.items():
        is_touched = getattr(cp, f"touch_{pad}")
        if is_touched:
            cp.pixels.fill(COLORS[pad])
            cp.start_tone(freq)
            touched = True
            break
    
    if not touched:
        cp.pixels.fill((0, 0, 0))
        cp.stop_tone()
    
    time.sleep(0.05)
`,

  bubble_level: `from adafruit_circuitplayground import cp
import time

# Pixel order around the top arc from right to left:
#   0(5:00) 1(4:00) 2(3:00) 3(2:00) 4(1:00) 5(11:00) 6(10:00) 7(9:00) 8(8:00) 9(7:00)
# Pixels 4,5 are at the top (12 o'clock). The "bubble" slides along this arc.

ARC = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
CENTER = 4.5  # midpoint between pixel 4 and 5

GREEN  = (0, 255, 0)
YELLOW = (255, 200, 0)
RED    = (255, 0, 0)

cp.pixels.brightness = 0.5

while True:
    x, y, z = cp.acceleration

    # Map X acceleration to a position on the arc.
    # x ~ 0 when level, +/-9.8 at full tilt.
    # Tilt right (x > 0) -- bubble slides left (toward pixel 9).
    tilt = max(-9.8, min(9.8, x))
    bubble_pos = CENTER + (tilt / 9.8) * CENTER

    # Pick color based on how far from level
    off = abs(tilt)
    if off < 1.0:
        color = GREEN
    elif off < 4.0:
        color = YELLOW
    else:
        color = RED

    for i in range(10):
        dist = abs(i - bubble_pos)
        if dist < 1.0:
            cp.pixels[i] = color
        elif dist < 2.0:
            dim = 1.0 - (dist - 1.0)
            cp.pixels[i] = (int(color[0] * dim * 0.3),
                            int(color[1] * dim * 0.3),
                            int(color[2] * dim * 0.3))
        else:
            cp.pixels[i] = (0, 0, 0)

    level_str = "LEVEL" if abs(tilt) < 1.0 else f"tilt {tilt:+.1f}"
    print(f"X: {x:+6.2f}  bubble: {bubble_pos:.1f}  {level_str}")
    time.sleep(0.05)
`,

  all_sensors: `from adafruit_circuitplayground import cp
import time

cp.pixels.brightness = 0.2

print("=== Sensor Dashboard ===")
print("Reads all sensors every second.\\n")

while True:
    temp = cp.temperature
    light = cp.light
    ax, ay, az = cp.acceleration
    btn_a = cp.button_a
    btn_b = cp.button_b
    sw = cp.switch
    
    print(f"Temp: {temp:.1f}C  Light: {light:4d}  "
          f"Accel: ({ax:.1f}, {ay:.1f}, {az:.1f})  "
          f"BtnA: {btn_a}  BtnB: {btn_b}  SW: {sw}")
    
    # Show acceleration magnitude on NeoPixels
    mag = (ax**2 + ay**2 + az**2) ** 0.5
    num_lit = min(10, int(mag / 2))
    for i in range(10):
        if i < num_lit:
            cp.pixels[i] = (0, int(mag * 10) % 256, 200)
        else:
            cp.pixels[i] = (0, 0, 0)
    
    cp.red_led = btn_a or btn_b
    time.sleep(1.0)
`,
};


// ═══ Initialize Application ═══
let editor = null;
let board = null;

async function init() {
  // Set up CodeMirror editor
  const editorContainer = document.getElementById('editor-container');
  editor = CodeMirror(editorContainer, {
    mode: 'python',
    theme: 'material-darker',
    lineNumbers: true,
    matchBrackets: true,
    autoCloseBrackets: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: false,
    extraKeys: {
      'Ctrl-Enter': () => handleRun(),
      'Cmd-Enter': () => handleRun(),
      'Ctrl-.': () => handleStop(),
      'Cmd-.': () => handleStop(),
      'Tab': (cm) => {
        if (cm.somethingSelected()) {
          cm.indentSelection('add');
        } else {
          cm.replaceSelection('    ', 'end');
        }
      },
      'Ctrl-/': 'toggleComment',
      'Cmd-/': 'toggleComment',
    },
    value: EXAMPLES.neopixel_rainbow,
  });

  // Set up the board visualization
  const boardContainer = document.getElementById('board-container');
  board = new Board(boardContainer);

  // Wire board buttons to emulator state
  board.onButtonA = (pressed) => updateSensor('buttonA', pressed);
  board.onButtonB = (pressed) => updateSensor('buttonB', pressed);
  board.onSwitch = (state) => updateSensor('switchState', state);

  // Set emulator callbacks
  setCallbacks({
    setPixel: (i, r, g, b) => board.setPixel(i, r, g, b),
    setBrightness: (v) => board.setBrightness(v),
    setRedLed: (on) => board.setRedLed(on),
    clearPixels: () => board.clearPixels(),
    consoleWrite: writeToConsole,
    startTone: () => {},
    stopTone: () => {},
  });

  // Wire up UI controls
  document.getElementById('btn-run').addEventListener('click', handleRun);
  document.getElementById('btn-stop').addEventListener('click', handleStop);
  document.getElementById('btn-clear-console').addEventListener('click', clearConsole);
  document.getElementById('examples-select').addEventListener('change', handleExampleSelect);

  // Wire up sensor sliders
  setupSensorInputs();

  // Wire up touch pad buttons
  setupTouchPads();

  // Keyboard shortcuts (global)
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRun();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === '.') {
      e.preventDefault();
      handleStop();
    }
  });

  // Initialize Pyodide
  try {
    setStatus('loading');
    await initPyodide((msg) => {
      document.querySelector('#loading-overlay .loading-content p').textContent = msg;
    });
    setStatus('idle');
    document.getElementById('loading-overlay').classList.add('hidden');
    writeToConsole('CPX Playground ready. Press Run or Ctrl+Enter to start.\n', 'info');
  } catch (err) {
    setStatus('error');
    document.querySelector('#loading-overlay .loading-content p').textContent =
      'Failed to load Python runtime. Try refreshing.';
    console.error('Pyodide init failed:', err);
  }
}

// ═══ Event Handlers ═══

async function handleRun() {
  if (isRunning()) return;
  const code = editor.getValue();
  if (!code.trim()) return;

  clearConsole();
  setStatus('running');
  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-stop').disabled = false;

  await runCode(code);

  setStatus('idle');
  document.getElementById('btn-run').disabled = false;
  document.getElementById('btn-stop').disabled = true;
}

function handleStop() {
  if (!isRunning()) return;
  stopCode();
  stopTone();
}

function handleExampleSelect(e) {
  const key = e.target.value;
  if (key && EXAMPLES[key]) {
    editor.setValue(EXAMPLES[key]);
    e.target.value = '';
  }
}

// ═══ Sensor Inputs ═══

function setupSensorInputs() {
  const mappings = [
    { id: 'sensor-light', key: 'light', display: 'val-light', format: (v) => v },
    { id: 'sensor-temp', key: 'temperature', display: 'val-temp', format: (v) => `${parseFloat(v).toFixed(1)}\u00B0C` },
    { id: 'sensor-sound', key: 'soundLevel', display: 'val-sound', format: (v) => v },
    { id: 'sensor-accel-x', key: 'accelX', display: 'val-accel-x', format: (v) => parseFloat(v).toFixed(1) },
    { id: 'sensor-accel-y', key: 'accelY', display: 'val-accel-y', format: (v) => parseFloat(v).toFixed(1) },
    { id: 'sensor-accel-z', key: 'accelZ', display: 'val-accel-z', format: (v) => parseFloat(v).toFixed(1) },
  ];

  for (const { id, key, display, format } of mappings) {
    const input = document.getElementById(id);
    const displayEl = document.getElementById(display);
    input.addEventListener('input', () => {
      const val = parseFloat(input.value);
      updateSensor(key, val);
      displayEl.textContent = format(input.value);
    });
  }
}

function setupTouchPads() {
  document.querySelectorAll('.touch-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const pad = btn.dataset.pad;
      btn.classList.toggle('active');
      const active = btn.classList.contains('active');
      updateSensor(`touch_${pad}`, active);
    });
  });
}

// ═══ Console ═══

function writeToConsole(text, type = 'output') {
  const consoleEl = document.getElementById('console-output');
  const span = document.createElement('span');
  if (type === 'error') span.className = 'error';
  else if (type === 'info') span.className = 'info';
  else if (type === 'warning') span.className = 'warning';
  span.textContent = text;
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

function clearConsole() {
  document.getElementById('console-output').innerHTML = '';
}

// ═══ Status ═══

function setStatus(status) {
  const el = document.getElementById('status-indicator');
  el.className = `status-badge status-${status}`;
  const labels = { idle: 'Idle', loading: 'Loading', running: 'Running', error: 'Error' };
  el.textContent = labels[status] || status;
}

// ═══ Start ═══
document.addEventListener('DOMContentLoaded', init);
