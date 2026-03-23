import { startTone, stopTone } from './audio.js';

let pyodide = null;
let running = false;
let stopFlag = false;

// Board state shared between JS and Python
const boardState = {
  buttonA: false,
  buttonB: false,
  switchState: false,
  light: 128,
  temperature: 25.0,
  soundLevel: 0,
  accelX: 0.0,
  accelY: 0.0,
  accelZ: 9.8,
  touchPads: { A1: false, A2: false, A3: false, A4: false, A5: false, A6: false, A7: false },
};

// Callbacks to update the board visuals (set by app.js)
let onSetPixel = null;
let onSetBrightness = null;
let onSetRedLed = null;
let onClearPixels = null;
let onConsoleWrite = null;
let onStartTone = null;
let onStopTone = null;

export function setCallbacks(cbs) {
  onSetPixel = cbs.setPixel;
  onSetBrightness = cbs.setBrightness;
  onSetRedLed = cbs.setRedLed;
  onClearPixels = cbs.clearPixels;
  onConsoleWrite = cbs.consoleWrite;
  onStartTone = cbs.startTone;
  onStopTone = cbs.stopTone;
}

export function updateSensor(key, value) {
  if (key.startsWith('touch_')) {
    const pad = key.replace('touch_', '');
    boardState.touchPads[pad] = value;
  } else {
    boardState[key] = value;
  }
}

export function isRunning() { return running; }

export async function initPyodide(onProgress) {
  onProgress?.('Loading Python runtime...');
  pyodide = await loadPyodide({
    indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/',
  });

  onProgress?.('Setting up emulation modules...');

  // Expose the bridge object to Python via the js module
  window._cpx_bridge = {
    // Sensor getters
    getButtonA: () => boardState.buttonA,
    getButtonB: () => boardState.buttonB,
    getSwitch: () => boardState.switchState,
    getLight: () => boardState.light,
    getTemperature: () => boardState.temperature,
    getSoundLevel: () => boardState.soundLevel,
    getAccelX: () => boardState.accelX,
    getAccelY: () => boardState.accelY,
    getAccelZ: () => boardState.accelZ,
    getTouch: (pad) => boardState.touchPads[pad] || false,

    // Output setters
    setPixel: (index, r, g, b) => { onSetPixel?.(index, r, g, b); },
    setPixelBrightness: (val) => { onSetBrightness?.(val); },
    setRedLed: (on) => { onSetRedLed?.(on); },
    clearPixels: () => { onClearPixels?.(); },
    startTone: (freq) => { startTone(freq); onStartTone?.(freq); },
    stopTone: () => { stopTone(); onStopTone?.(); },

    // Execution control
    shouldStop: () => stopFlag,

    // Console
    consolePrint: (text) => { onConsoleWrite?.(text, 'output'); },
  };

  // Register the CPX emulation Python code
  await pyodide.runPythonAsync(CPX_MODULE_CODE);
  await pyodide.runPythonAsync(TRANSFORMER_CODE);

  onProgress?.('Ready');
  return pyodide;
}

export async function runCode(code) {
  if (!pyodide) throw new Error('Pyodide not initialized');
  if (running) return;

  running = true;
  stopFlag = false;
  window._cpx_stop_flag = false;

  try {
    onClearPixels?.();
    onSetRedLed?.(false);
    stopTone();

    // Transform user code for async execution
    pyodide.globals.set('__raw_user_code', code);
    const transformed = await pyodide.runPythonAsync(`
__transform_user_code(__raw_user_code)
`);

    // Execute the transformed async code
    await pyodide.runPythonAsync(transformed);
    await pyodide.runPythonAsync('await __user_program()');

  } catch (err) {
    const msg = err.message || String(err);
    if (msg.includes('ProgramStopped') || msg.includes('KeyboardInterrupt')) {
      onConsoleWrite?.('\n--- Program stopped ---\n', 'info');
    } else {
      onConsoleWrite?.(`\n${msg}\n`, 'error');
    }
  } finally {
    running = false;
    stopTone();
  }
}

export function stopCode() {
  stopFlag = true;
  window._cpx_stop_flag = true;
}

// ════════════════════════════════════════════════════════════════
// Python: CircuitPython API emulation modules
// ════════════════════════════════════════════════════════════════

const CPX_MODULE_CODE = `
import sys
import js

# ── Bridge access ──
_bridge = js.window._cpx_bridge

# ── Custom exception for stopping ──
class ProgramStopped(Exception):
    pass

# ── Emulated: board module ──
class _BoardModule:
    A0 = 'A0'; A1 = 'A1'; A2 = 'A2'; A3 = 'A3'
    A4 = 'A4'; A5 = 'A5'; A6 = 'A6'; A7 = 'A7'
    D4 = 'D4'; D5 = 'D5'; D6 = 'D6'; D7 = 'D7'; D8 = 'D8'
    D13 = 'D13'
    NEOPIXEL = 'NEOPIXEL'
    SPEAKER = 'SPEAKER'
    BUTTON_A = 'BUTTON_A'
    BUTTON_B = 'BUTTON_B'
    SLIDE_SWITCH = 'SLIDE_SWITCH'
    LIGHT = 'LIGHT'
    TEMPERATURE = 'TEMPERATURE'
    ACCELEROMETER_X = 'ACCEL_X'
    ACCELEROMETER_Y = 'ACCEL_Y'
    ACCELEROMETER_Z = 'ACCEL_Z'

sys.modules['board'] = _BoardModule()

# ── Emulated: digitalio module ──
class _DigitalIO:
    class Direction:
        INPUT = 'INPUT'
        OUTPUT = 'OUTPUT'
    class Pull:
        UP = 'UP'
        DOWN = 'DOWN'
    class DigitalInOut:
        def __init__(self, pin):
            self.pin = pin
            self.direction = None
            self.pull = None
            self._value = False
        @property
        def value(self):
            if self.pin == 'BUTTON_A':
                return _bridge.getButtonA()
            elif self.pin == 'BUTTON_B':
                return _bridge.getButtonB()
            elif self.pin == 'SLIDE_SWITCH':
                return _bridge.getSwitch()
            elif self.pin == 'D13':
                return self._value
            return self._value
        @value.setter
        def value(self, v):
            self._value = v
            if self.pin == 'D13':
                _bridge.setRedLed(bool(v))

_digitalio = _DigitalIO()
sys.modules['digitalio'] = _digitalio

# ── Emulated: analogio module ──
class _AnalogIO:
    class AnalogIn:
        def __init__(self, pin):
            self.pin = pin
        @property
        def value(self):
            if self.pin == 'LIGHT':
                return int(_bridge.getLight()) * 64
            elif self.pin == 'TEMPERATURE':
                return int((_bridge.getTemperature() + 40) * 300)
            return 0

sys.modules['analogio'] = _AnalogIO()

# ── Emulated: neopixel module ──
class _NeoPixelModule:
    GRB = 'GRB'
    GRBW = 'GRBW'

    class NeoPixel:
        def __init__(self, pin, n, brightness=1.0, auto_write=True, pixel_order=None):
            self.pin = pin
            self.n = n
            self._brightness = brightness
            self.auto_write = auto_write
            self._pixels = [(0, 0, 0)] * n
            _bridge.setPixelBrightness(brightness)

        def __setitem__(self, index, color):
            if isinstance(index, slice):
                indices = range(*index.indices(self.n))
                if not hasattr(color[0], '__iter__'):
                    color = [color] * len(list(indices))
                for i, c in zip(indices, color):
                    r, g, b = c[0], c[1], c[2]
                    self._pixels[i] = (r, g, b)
                    _bridge.setPixel(i, r, g, b)
            else:
                if index < 0:
                    index = self.n + index
                r, g, b = color[0], color[1], color[2]
                self._pixels[index] = (r, g, b)
                _bridge.setPixel(index, r, g, b)

        def __getitem__(self, index):
            if index < 0:
                index = self.n + index
            return self._pixels[index]

        def __len__(self):
            return self.n

        @property
        def brightness(self):
            return self._brightness

        @brightness.setter
        def brightness(self, val):
            self._brightness = max(0.0, min(1.0, val))
            _bridge.setPixelBrightness(self._brightness)

        def fill(self, color):
            r, g, b = color[0], color[1], color[2]
            for i in range(self.n):
                self._pixels[i] = (r, g, b)
                _bridge.setPixel(i, r, g, b)

        def show(self):
            pass

sys.modules['neopixel'] = _NeoPixelModule()

# ── Emulated: simpleio module ──
class _SimpleIO:
    @staticmethod
    def tone(pin, frequency, duration=0.5):
        import asyncio
        _bridge.startTone(frequency)

sys.modules['simpleio'] = _SimpleIO()

# ── Emulated: adafruit_circuitplayground ──
class _PixelArray:
    def __init__(self):
        self._brightness = 1.0
        self._pixels = [(0, 0, 0)] * 10

    def __setitem__(self, index, color):
        if isinstance(index, slice):
            indices = range(*index.indices(10))
            for i in indices:
                r, g, b = color[0], color[1], color[2]
                self._pixels[i] = (r, g, b)
                _bridge.setPixel(i, r, g, b)
        else:
            if index < 0:
                index = 10 + index
            r, g, b = color[0], color[1], color[2]
            self._pixels[index] = (r, g, b)
            _bridge.setPixel(index, r, g, b)

    def __getitem__(self, index):
        if index < 0:
            index = 10 + index
        return self._pixels[index]

    def __len__(self):
        return 10

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, val):
        self._brightness = max(0.0, min(1.0, val))
        _bridge.setPixelBrightness(self._brightness)

    def fill(self, color):
        r, g, b = color[0], color[1], color[2]
        for i in range(10):
            self._pixels[i] = (r, g, b)
            _bridge.setPixel(i, r, g, b)

    def show(self):
        pass


class CircuitPlayground:
    def __init__(self):
        self._pixels = _PixelArray()
        self._detect_taps = 0

    @property
    def pixels(self):
        return self._pixels

    @property
    def button_a(self):
        return bool(_bridge.getButtonA())

    @property
    def button_b(self):
        return bool(_bridge.getButtonB())

    @property
    def switch(self):
        return bool(_bridge.getSwitch())

    @property
    def temperature(self):
        return float(_bridge.getTemperature())

    @property
    def light(self):
        return int(_bridge.getLight())

    @property
    def acceleration(self):
        return (float(_bridge.getAccelX()), float(_bridge.getAccelY()), float(_bridge.getAccelZ()))

    @property
    def touch_A1(self):
        return bool(_bridge.getTouch('A1'))

    @property
    def touch_A2(self):
        return bool(_bridge.getTouch('A2'))

    @property
    def touch_A3(self):
        return bool(_bridge.getTouch('A3'))

    @property
    def touch_A4(self):
        return bool(_bridge.getTouch('A4'))

    @property
    def touch_A5(self):
        return bool(_bridge.getTouch('A5'))

    @property
    def touch_A6(self):
        return bool(_bridge.getTouch('A6'))

    @property
    def touch_A7(self):
        return bool(_bridge.getTouch('A7'))

    @property
    def red_led(self):
        return bool(_bridge.getRedLed()) if hasattr(_bridge, 'getRedLed') else False

    @red_led.setter
    def red_led(self, val):
        _bridge.setRedLed(bool(val))

    @property
    def detect_taps(self):
        return self._detect_taps

    @detect_taps.setter
    def detect_taps(self, val):
        self._detect_taps = val

    @property
    def tapped(self):
        return False

    def shake(self, shake_threshold=30):
        ax, ay, az = self.acceleration
        magnitude = (ax**2 + ay**2 + az**2) ** 0.5
        return magnitude > shake_threshold

    def loud_sound(self, sound_threshold=200):
        return int(_bridge.getSoundLevel()) > sound_threshold

    def play_tone(self, frequency, duration):
        _bridge.startTone(frequency)

    def start_tone(self, frequency):
        _bridge.startTone(frequency)

    def stop_tone(self):
        _bridge.stopTone()


class _CPXModule:
    def __init__(self):
        self.cp = CircuitPlayground()
        self.CircuitPlayground = CircuitPlayground

_cpx_mod = _CPXModule()
sys.modules['adafruit_circuitplayground'] = _cpx_mod
sys.modules['adafruit_circuitplayground.express'] = _cpx_mod

# Also make 'from adafruit_circuitplayground import cp' work
_cpx_mod.__dict__['cp'] = _cpx_mod.cp

# ── Redirect print to console ──
import io

class _ConsolePrinter(io.TextIOBase):
    def write(self, text):
        if text:
            _bridge.consolePrint(text)
        return len(text) if text else 0

    def flush(self):
        pass

sys.stdout = _ConsolePrinter()
sys.stderr = _ConsolePrinter()

print("CircuitPython emulator ready.")
`;


// ════════════════════════════════════════════════════════════════
// Python: AST transformer for async execution
// ════════════════════════════════════════════════════════════════

const TRANSFORMER_CODE = `
import ast
import asyncio
import js

class ProgramStopped(Exception):
    pass

async def __yield_control():
    if js.window._cpx_stop_flag:
        raise ProgramStopped("Program stopped by user")
    await asyncio.sleep(0)

async def __async_sleep(duration):
    if js.window._cpx_stop_flag:
        raise ProgramStopped("Program stopped by user")
    if duration <= 0:
        await asyncio.sleep(0)
        return
    elapsed = 0.0
    step = min(duration, 0.05)
    while elapsed < duration:
        if js.window._cpx_stop_flag:
            raise ProgramStopped("Program stopped by user")
        await asyncio.sleep(step)
        elapsed += step

async def __async_play_tone(freq, dur):
    if js.window._cpx_stop_flag:
        raise ProgramStopped("Program stopped by user")
    _bridge = js.window._cpx_bridge
    _bridge.startTone(freq)
    await __async_sleep(dur)
    _bridge.stopTone()


class _CPXTransformer(ast.NodeTransformer):
    """Transforms user code to be async-compatible:
    - Inserts yield points in loops
    - Replaces time.sleep() with async sleep
    - Replaces cp.play_tone() with async version
    """

    def visit_While(self, node):
        self.generic_visit(node)
        yield_stmt = ast.parse("await __yield_control()").body[0]
        ast.copy_location(yield_stmt, node)
        ast.fix_missing_locations(yield_stmt)
        node.body.insert(0, yield_stmt)
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        yield_stmt = ast.parse("await __yield_control()").body[0]
        ast.copy_location(yield_stmt, node)
        ast.fix_missing_locations(yield_stmt)
        node.body.insert(0, yield_stmt)
        return node

    def visit_Expr(self, node):
        self.generic_visit(node)
        if isinstance(node.value, ast.Call):
            call = node.value
            # time.sleep(x) -> await __async_sleep(x)
            if self._is_call(call, 'time', 'sleep'):
                new_call = ast.Call(
                    func=ast.Name(id='__async_sleep', ctx=ast.Load()),
                    args=call.args, keywords=call.keywords
                )
                node.value = ast.Await(value=new_call)
                ast.fix_missing_locations(node)
            # sleep(x) bare call
            elif isinstance(call.func, ast.Name) and call.func.id == 'sleep':
                new_call = ast.Call(
                    func=ast.Name(id='__async_sleep', ctx=ast.Load()),
                    args=call.args, keywords=call.keywords
                )
                node.value = ast.Await(value=new_call)
                ast.fix_missing_locations(node)
            # cp.play_tone(freq, dur)
            elif self._is_call(call, 'cp', 'play_tone'):
                new_call = ast.Call(
                    func=ast.Name(id='__async_play_tone', ctx=ast.Load()),
                    args=call.args, keywords=call.keywords
                )
                node.value = ast.Await(value=new_call)
                ast.fix_missing_locations(node)
        return node

    def _is_call(self, call, obj_name, method_name):
        return (isinstance(call.func, ast.Attribute) and
                call.func.attr == method_name and
                isinstance(call.func.value, ast.Name) and
                call.func.value.id == obj_name)


def __transform_user_code(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SyntaxError(f"Syntax error on line {e.lineno}: {e.msg}")

    transformer = _CPXTransformer()
    tree = transformer.visit(tree)

    # Wrap all top-level code in an async function
    async_func = ast.AsyncFunctionDef(
        name='__user_program',
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None,
            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=tree.body if tree.body else [ast.parse("pass").body[0]],
        decorator_list=[],
        returns=None,
        type_comment=None
    )
    ast.copy_location(async_func, tree.body[0] if tree.body else ast.parse("pass").body[0])

    new_tree = ast.Module(body=[async_func], type_ignores=[])
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)
`;
