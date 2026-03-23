# CPX Playground

A browser-based development tool for writing Python code and testing it against an emulated **Adafruit Circuit Playground Express** (CPX).

No hardware required — everything runs in your browser using [Pyodide](https://pyodide.org/) (CPython compiled to WebAssembly).

## Quick Start

The app needs to be served over HTTP (not opened as a `file://` URL) because Pyodide loads WebAssembly modules.

**Using Python's built-in server:**

```bash
cd cpx-emulator
python3 -m http.server 8000
```

Then open **http://localhost:8000** in your browser.

**Using Node.js:**

```bash
npx serve cpx-emulator
```

## Features

- **Full code editor** with Python syntax highlighting, auto-indent, and bracket matching (CodeMirror)
- **Visual board emulator** — SVG rendering of the CPX with interactive NeoPixels, buttons, and LED
- **Sensor simulation** — adjust light, temperature, accelerometer, and sound level via sliders
- **Touch pad emulation** — toggle capacitive touch inputs A1–A7
- **Audio output** — `play_tone()` and `start_tone()` produce sound via the Web Audio API
- **Console output** — `print()` statements appear in the console panel
- **Example programs** — dropdown menu with ready-to-run demos
- **Keyboard shortcuts** — Ctrl/Cmd+Enter to run, Ctrl/Cmd+. to stop

## Supported CircuitPython API

The emulator supports the most commonly used CircuitPython modules:

### `adafruit_circuitplayground`

```python
from adafruit_circuitplayground import cp

cp.pixels[0] = (255, 0, 0)     # Set NeoPixel color
cp.pixels.fill((0, 255, 0))    # Fill all pixels
cp.pixels.brightness = 0.3     # Set brightness (0.0–1.0)
cp.button_a                    # True when Button A is pressed
cp.button_b                    # True when Button B is pressed
cp.switch                      # Slide switch state
cp.temperature                 # Temperature in °C
cp.light                       # Light level (0–1023)
cp.acceleration                # (x, y, z) in m/s²
cp.touch_A1 ... cp.touch_A7   # Capacitive touch pads
cp.red_led = True              # Control the red D13 LED
cp.play_tone(440, 1.0)         # Play tone (frequency Hz, duration sec)
cp.start_tone(440)             # Start continuous tone
cp.stop_tone()                 # Stop tone
cp.shake()                     # Detect shake
cp.loud_sound()                # Detect loud sound
```

### Other modules

| Module | Support |
|--------|---------|
| `board` | Pin definitions (A0–A7, D4–D13, etc.) |
| `digitalio` | `DigitalInOut`, `Direction`, `Pull` |
| `analogio` | `AnalogIn` for light and temperature |
| `neopixel` | `NeoPixel` class for LED strip control |
| `time` | `time.sleep()` works correctly in the emulator |
| `simpleio` | `tone()` function |

## How It Works

1. **Pyodide** loads a full CPython interpreter as WebAssembly in the browser
2. Custom Python modules emulate CircuitPython hardware APIs, bridging to JavaScript for display and audio
3. User code is **AST-transformed** before execution:
   - `while`/`for` loops get yield points so the browser stays responsive
   - `time.sleep()` becomes async to avoid freezing the UI
   - `cp.play_tone()` becomes async for accurate duration timing
4. The transformed code runs as an async function via `pyodide.runPythonAsync()`

## Project Structure

```
cpx-emulator/
├── index.html          # Main page
├── css/
│   └── style.css       # Dark theme styles
├── js/
│   ├── app.js          # App init, editor, event handling
│   ├── board.js        # SVG board rendering
│   ├── audio.js        # Web Audio API tone generation
│   └── emulator.js     # Pyodide setup, CPX API, AST transformer
└── README.md
```

## Browser Compatibility

Works in modern browsers with WebAssembly support:
- Chrome 89+
- Firefox 89+
- Safari 15+
- Edge 89+

## Limitations

- Only a subset of CircuitPython is emulated (the most commonly used APIs)
- `play_file()` is not supported (no filesystem audio)
- IR transmitter/receiver is not emulated
- Some advanced `neopixel` features (RGBW, pixel order) are simplified
- The emulator runs on the main thread; very tight loops without `time.sleep()` may affect UI responsiveness
