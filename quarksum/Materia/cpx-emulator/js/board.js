const SVG_NS = 'http://www.w3.org/2000/svg';
const BOARD_SIZE = 300;
const CENTER = BOARD_SIZE / 2;
const BOARD_RADIUS = 130;
const PIXEL_RING_RADIUS = 108;
const NUM_PIXELS = 10;

const PIXEL_ANGLES_DEG = [
  150, 120, 90, 60, 30, 330, 300, 270, 240, 210
];

function deg2rad(d) { return d * Math.PI / 180; }

function polarToXY(angleDeg, radius) {
  const rad = deg2rad(angleDeg);
  return {
    x: CENTER + radius * Math.sin(rad),
    y: CENTER - radius * Math.cos(rad)
  };
}

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

export class Board {
  constructor(container) {
    this.container = container;
    this.pixelEls = [];
    this.pixelGlowOuterEls = [];
    this.pixelGlowInnerEls = [];
    this.pixelHighlightEls = [];
    this.pixelLabelEls = [];
    this.pixelColors = Array(NUM_PIXELS).fill([0, 0, 0]);
    this.brightness = 1.0;
    this.redLedOn = false;

    this.onButtonA = null;
    this.onButtonB = null;
    this.onSwitch = null;
    this.switchState = false;

    this._build();
  }

  _build() {
    const svg = svgEl('svg', {
      viewBox: `0 0 ${BOARD_SIZE} ${BOARD_SIZE}`,
      width: BOARD_SIZE,
      height: BOARD_SIZE,
    });

    const defs = svgEl('defs');
    svg.appendChild(defs);

    // Large soft glow for PCB light bleed
    const outerGlow = svgEl('filter', { id: 'glow-outer', x: '-200%', y: '-200%', width: '500%', height: '500%' });
    outerGlow.appendChild(svgEl('feGaussianBlur', { stdDeviation: '16', result: 'blur' }));
    const outerMerge = svgEl('feMerge');
    outerMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    outerMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    outerMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    outerGlow.appendChild(outerMerge);
    defs.appendChild(outerGlow);

    // Tight bright glow around the LED
    const innerGlow = svgEl('filter', { id: 'glow-inner', x: '-150%', y: '-150%', width: '400%', height: '400%' });
    innerGlow.appendChild(svgEl('feGaussianBlur', { stdDeviation: '7', result: 'blur' }));
    const innerMerge = svgEl('feMerge');
    innerMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    innerMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    innerMerge.appendChild(svgEl('feMergeNode', { in: 'SourceGraphic' }));
    innerGlow.appendChild(innerMerge);
    defs.appendChild(innerGlow);

    // Red LED glow
    const redGlow = svgEl('filter', { id: 'glow-red', x: '-200%', y: '-200%', width: '500%', height: '500%' });
    redGlow.appendChild(svgEl('feGaussianBlur', { stdDeviation: '4', result: 'blur' }));
    const redMerge = svgEl('feMerge');
    redMerge.appendChild(svgEl('feMergeNode', { in: 'blur' }));
    redMerge.appendChild(svgEl('feMergeNode', { in: 'SourceGraphic' }));
    redGlow.appendChild(redMerge);
    defs.appendChild(redGlow);

    // Board drop shadow
    const shadowFilter = svgEl('filter', { id: 'board-shadow', x: '-10%', y: '-10%', width: '120%', height: '120%' });
    shadowFilter.appendChild(svgEl('feDropShadow', { dx: '0', dy: '3', stdDeviation: '6', 'flood-color': '#000', 'flood-opacity': '0.6' }));
    defs.appendChild(shadowFilter);

    // PCB
    svg.appendChild(svgEl('circle', {
      cx: CENTER, cy: CENTER, r: BOARD_RADIUS,
      fill: '#1a5c2a', stroke: '#0d3d18', 'stroke-width': '2.5',
      filter: 'url(#board-shadow)'
    }));

    // Copper traces
    svg.appendChild(svgEl('circle', {
      cx: CENTER, cy: CENTER, r: BOARD_RADIUS - 8,
      fill: 'none', stroke: '#2a7a3a', 'stroke-width': '0.8', opacity: '0.4'
    }));
    svg.appendChild(svgEl('circle', {
      cx: CENTER, cy: CENTER, r: 55,
      fill: 'none', stroke: '#2a7a3a', 'stroke-width': '0.5', opacity: '0.3'
    }));

    this._drawUSBConnector(svg);
    this._drawBatteryConnector(svg);
    this._drawGoldPads(svg);
    this._drawNeoPixels(svg, defs);
    this._drawButtons(svg);
    this._drawSlideSwitch(svg);
    this._drawRedLED(svg, defs);
    this._drawPinLabels(svg);
    this._drawCenterLogo(svg);

    this.svg = svg;
    this.container.appendChild(svg);
  }

  _drawUSBConnector(svg) {
    const g = svgEl('g');
    g.appendChild(svgEl('rect', {
      x: CENTER - 14, y: 4, width: 28, height: 14, rx: 2,
      fill: '#808080', stroke: '#606060', 'stroke-width': '1'
    }));
    g.appendChild(svgEl('rect', {
      x: CENTER - 10, y: 7, width: 20, height: 8, rx: 1,
      fill: '#505050'
    }));
    const label = svgEl('text', {
      x: CENTER, y: 30, 'text-anchor': 'middle',
      'font-size': '7', fill: '#ffffff', opacity: '0.4',
      'font-family': 'sans-serif'
    });
    label.textContent = 'USB';
    g.appendChild(label);
    svg.appendChild(g);
  }

  _drawBatteryConnector(svg) {
    svg.appendChild(svgEl('rect', {
      x: CENTER - 10, y: BOARD_SIZE - 20, width: 20, height: 10, rx: 2,
      fill: '#e0e0e0', stroke: '#b0b0b0', 'stroke-width': '0.5'
    }));
    const label = svgEl('text', {
      x: CENTER, y: BOARD_SIZE - 24, 'text-anchor': 'middle',
      'font-size': '6', fill: '#ffffff', opacity: '0.3',
      'font-family': 'sans-serif'
    });
    label.textContent = 'BATT';
    svg.appendChild(label);
  }

  _drawNeoPixels(svg, defs) {
    for (let i = 0; i < NUM_PIXELS; i++) {
      const { x, y } = polarToXY(PIXEL_ANGLES_DEG[i], PIXEL_RING_RADIUS);

      // Layer 1: Outer glow — large soft PCB light bleed
      const outerGlow = svgEl('circle', {
        cx: x, cy: y, r: 36,
        filter: 'url(#glow-outer)',
        class: 'px-glow-outer'
      });
      outerGlow.style.fill = 'transparent';
      outerGlow.style.opacity = '0';
      this.pixelGlowOuterEls.push(outerGlow);
      svg.appendChild(outerGlow);

      // Layer 2: Inner glow — bright halo tight around LED
      const innerGlow = svgEl('circle', {
        cx: x, cy: y, r: 18,
        filter: 'url(#glow-inner)',
        class: 'px-glow-inner'
      });
      innerGlow.style.fill = 'transparent';
      innerGlow.style.opacity = '0';
      this.pixelGlowInnerEls.push(innerGlow);
      svg.appendChild(innerGlow);

      // Layer 3: LED housing (the physical black circle with the LED inside)
      svg.appendChild(svgEl('circle', {
        cx: x, cy: y, r: 9.5,
        fill: '#1e1e1e', stroke: '#3a3a3a', 'stroke-width': '0.8'
      }));

      // Layer 4: LED body — the main color surface
      const pixel = svgEl('circle', {
        cx: x, cy: y, r: 7.5,
        class: 'px-led'
      });
      pixel.style.fill = '#111';
      pixel.dataset.index = i;
      this.pixelEls.push(pixel);
      svg.appendChild(pixel);

      // Layer 5: White hot center — simulates the bright die
      const highlight = svgEl('circle', {
        cx: x, cy: y, r: 3,
        class: 'px-highlight'
      });
      highlight.style.fill = '#fff';
      highlight.style.opacity = '0';
      this.pixelHighlightEls.push(highlight);
      svg.appendChild(highlight);

      // Layer 6: Tiny specular reflection dot
      svg.appendChild(svgEl('circle', {
        cx: x - 2, cy: y - 2, r: 1.2,
        fill: '#fff', opacity: '0.08', 'pointer-events': 'none'
      }));

      // Layer 7: Number label — visible when off, hidden when lit
      const numLabel = svgEl('text', {
        x: x, y: y + 3, 'text-anchor': 'middle',
        'font-size': '6.5', 'font-family': 'monospace',
        'pointer-events': 'none',
        class: 'px-label'
      });
      numLabel.style.fill = '#555';
      numLabel.style.opacity = '0.7';
      numLabel.textContent = i;
      this.pixelLabelEls.push(numLabel);
      svg.appendChild(numLabel);
    }
  }

  _drawButtons(svg) {
    // Button A
    const btnAG = svgEl('g', { class: 'board-button', cursor: 'pointer' });
    btnAG.appendChild(svgEl('circle', {
      cx: CENTER - 65, cy: CENTER, r: 16,
      fill: '#1a1a1a', stroke: '#555', 'stroke-width': '1.5'
    }));
    this.btnACircle = svgEl('circle', {
      cx: CENTER - 65, cy: CENTER, r: 12,
      fill: '#2a2a2a', stroke: '#666', 'stroke-width': '1'
    });
    btnAG.appendChild(this.btnACircle);
    const labelA = svgEl('text', {
      x: CENTER - 65, y: CENTER - 22, 'text-anchor': 'middle',
      'font-size': '8', fill: '#aaa', 'font-family': 'sans-serif', 'font-weight': 'bold'
    });
    labelA.textContent = 'A';
    btnAG.appendChild(labelA);
    svg.appendChild(btnAG);

    btnAG.addEventListener('mousedown', (e) => { e.preventDefault(); this._pressButton('A', true); });
    btnAG.addEventListener('mouseup', () => this._pressButton('A', false));
    btnAG.addEventListener('mouseleave', () => this._pressButton('A', false));
    btnAG.addEventListener('touchstart', (e) => { e.preventDefault(); this._pressButton('A', true); });
    btnAG.addEventListener('touchend', () => this._pressButton('A', false));

    // Button B
    const btnBG = svgEl('g', { class: 'board-button', cursor: 'pointer' });
    btnBG.appendChild(svgEl('circle', {
      cx: CENTER + 65, cy: CENTER, r: 16,
      fill: '#1a1a1a', stroke: '#555', 'stroke-width': '1.5'
    }));
    this.btnBCircle = svgEl('circle', {
      cx: CENTER + 65, cy: CENTER, r: 12,
      fill: '#2a2a2a', stroke: '#666', 'stroke-width': '1'
    });
    btnBG.appendChild(this.btnBCircle);
    const labelB = svgEl('text', {
      x: CENTER + 65, y: CENTER - 22, 'text-anchor': 'middle',
      'font-size': '8', fill: '#aaa', 'font-family': 'sans-serif', 'font-weight': 'bold'
    });
    labelB.textContent = 'B';
    btnBG.appendChild(labelB);
    svg.appendChild(btnBG);

    btnBG.addEventListener('mousedown', (e) => { e.preventDefault(); this._pressButton('B', true); });
    btnBG.addEventListener('mouseup', () => this._pressButton('B', false));
    btnBG.addEventListener('mouseleave', () => this._pressButton('B', false));
    btnBG.addEventListener('touchstart', (e) => { e.preventDefault(); this._pressButton('B', true); });
    btnBG.addEventListener('touchend', () => this._pressButton('B', false));
  }

  _drawSlideSwitch(svg) {
    const sx = CENTER - 45;
    const sy = 42;
    const g = svgEl('g', { cursor: 'pointer' });

    g.appendChild(svgEl('rect', {
      x: sx - 12, y: sy - 5, width: 24, height: 10, rx: 5,
      fill: '#444', stroke: '#555', 'stroke-width': '0.5'
    }));

    this.switchKnob = svgEl('rect', {
      x: sx - 10, y: sy - 3, width: 10, height: 6, rx: 3,
      fill: '#e0e0e0', stroke: '#aaa', 'stroke-width': '0.5'
    });
    g.appendChild(this.switchKnob);

    const label = svgEl('text', {
      x: sx, y: sy + 14, 'text-anchor': 'middle',
      'font-size': '6', fill: '#888', 'font-family': 'sans-serif'
    });
    label.textContent = 'SWITCH';
    g.appendChild(label);
    svg.appendChild(g);

    g.addEventListener('click', () => {
      this.switchState = !this.switchState;
      this._updateSwitchVisual();
      if (this.onSwitch) this.onSwitch(this.switchState);
    });
  }

  _drawRedLED(svg, defs) {
    const rx = CENTER + 20;
    const ry = CENTER + 50;

    // Glow layer (hidden when off)
    this.redLedGlow = svgEl('circle', {
      cx: rx, cy: ry, r: 10,
      filter: 'url(#glow-red)',
      class: 'red-led-glow'
    });
    this.redLedGlow.style.fill = '#ff2200';
    this.redLedGlow.style.opacity = '0';
    svg.appendChild(this.redLedGlow);

    // Housing
    svg.appendChild(svgEl('circle', {
      cx: rx, cy: ry, r: 5,
      fill: '#2a0000', stroke: '#444', 'stroke-width': '0.5'
    }));

    // LED surface
    this.redLedEl = svgEl('circle', { cx: rx, cy: ry, r: 4, class: 'red-led' });
    this.redLedEl.style.fill = '#3a0808';
    this.redLedEl.style.opacity = '1';
    svg.appendChild(this.redLedEl);

    // Highlight
    this.redLedHighlight = svgEl('circle', { cx: rx - 1, cy: ry - 1, r: 1.5 });
    this.redLedHighlight.style.fill = '#fff';
    this.redLedHighlight.style.opacity = '0';
    svg.appendChild(this.redLedHighlight);

    const label = svgEl('text', {
      x: rx, y: ry + 11, 'text-anchor': 'middle',
      'font-size': '5', fill: '#666', 'font-family': 'monospace'
    });
    label.textContent = 'D13';
    svg.appendChild(label);
  }

  _drawPinLabels(svg) {
    const pins = [
      { angle: 155, label: 'A0' },
      { angle: 125, label: 'A1' },
      { angle: 95, label: 'A2' },
      { angle: 65, label: 'A3' },
      { angle: 35, label: 'A4' },
      { angle: 325, label: 'A5' },
      { angle: 295, label: 'A6' },
      { angle: 265, label: 'A7' },
      { angle: 205, label: 'GND' },
      { angle: 185, label: '3.3V' },
    ];

    for (const pin of pins) {
      const { x, y } = polarToXY(pin.angle, BOARD_RADIUS + 4);
      const txt = svgEl('text', {
        x, y: y + 2, 'text-anchor': 'middle',
        'font-size': '5', fill: '#888', 'font-family': 'monospace',
        'pointer-events': 'none'
      });
      txt.textContent = pin.label;
      svg.appendChild(txt);
    }
  }

  _drawCenterLogo(svg) {
    const line1 = svgEl('text', {
      x: CENTER, y: CENTER - 6, 'text-anchor': 'middle',
      'font-size': '9', fill: '#fff', opacity: '0.25',
      'font-family': 'sans-serif', 'font-weight': 'bold'
    });
    line1.textContent = 'CIRCUIT';
    svg.appendChild(line1);

    const line2 = svgEl('text', {
      x: CENTER, y: CENTER + 5, 'text-anchor': 'middle',
      'font-size': '9', fill: '#fff', opacity: '0.25',
      'font-family': 'sans-serif', 'font-weight': 'bold'
    });
    line2.textContent = 'PLAYGROUND';
    svg.appendChild(line2);

    const line3 = svgEl('text', {
      x: CENTER, y: CENTER + 16, 'text-anchor': 'middle',
      'font-size': '7', fill: '#fff', opacity: '0.15',
      'font-family': 'sans-serif'
    });
    line3.textContent = 'EXPRESS';
    svg.appendChild(line3);
  }

  _drawGoldPads(svg) {
    const padAngles = [155, 125, 95, 65, 35, 325, 295, 265, 205, 185];
    for (const angle of padAngles) {
      const { x, y } = polarToXY(angle, BOARD_RADIUS - 3);
      svg.appendChild(svgEl('circle', {
        cx: x, cy: y, r: 6,
        fill: '#c9a84c', opacity: '0.3', stroke: '#b8963c', 'stroke-width': '0.3'
      }));
    }
  }

  _pressButton(btn, pressed) {
    if (btn === 'A') {
      this.btnACircle.setAttribute('fill', pressed ? '#555' : '#2a2a2a');
      if (this.onButtonA) this.onButtonA(pressed);
    } else {
      this.btnBCircle.setAttribute('fill', pressed ? '#555' : '#2a2a2a');
      if (this.onButtonB) this.onButtonB(pressed);
    }
  }

  _updateSwitchVisual() {
    const sx = CENTER - 45;
    this.switchKnob.setAttribute('x', this.switchState ? sx : sx - 10);
  }

  setPixel(index, r, g, b) {
    if (index < 0 || index >= NUM_PIXELS) return;
    this.pixelColors[index] = [r, g, b];
    this._renderPixel(index);
  }

  setBrightness(val) {
    this.brightness = Math.max(0, Math.min(1, val));
    for (let i = 0; i < NUM_PIXELS; i++) this._renderPixel(i);
  }

  setRedLed(on) {
    this.redLedOn = on;
    if (on) {
      this.redLedEl.style.fill = '#ff2200';
      this.redLedEl.style.opacity = '1';
      this.redLedGlow.style.opacity = '0.8';
      this.redLedHighlight.style.opacity = '0.4';
    } else {
      this.redLedEl.style.fill = '#3a0808';
      this.redLedEl.style.opacity = '1';
      this.redLedGlow.style.opacity = '0';
      this.redLedHighlight.style.opacity = '0';
    }
  }

  clearPixels() {
    for (let i = 0; i < NUM_PIXELS; i++) {
      this.pixelColors[i] = [0, 0, 0];
      this._renderPixel(i);
    }
  }

  _renderPixel(index) {
    const [r, g, b] = this.pixelColors[index];
    const br = this.brightness;

    // Dimmed color for the LED surface
    const ar = Math.round(r * br);
    const ag = Math.round(g * br);
    const ab = Math.round(b * br);

    const isOff = ar === 0 && ag === 0 && ab === 0;

    // Use the FULL undimmed color for glow so lights stay vivid even at low brightness
    const glowColor = `rgb(${r},${g},${b})`;

    // Luminance from the full color (not dimmed) drives glow intensity
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

    // Brighter LED surface: blend toward full color so it doesn't look muddy
    const ledR = Math.round(ar + (r - ar) * 0.4);
    const ledG = Math.round(ag + (g - ag) * 0.4);
    const ledB = Math.round(ab + (b - ab) * 0.4);
    const ledColor = `rgb(${ledR},${ledG},${ledB})`;

    // --- Outer glow: large soft PCB light bleed ---
    const outerEl = this.pixelGlowOuterEls[index];
    outerEl.style.fill = isOff ? 'transparent' : glowColor;
    outerEl.style.opacity = isOff ? '0' : String(Math.min(0.75, lum * 1.2 + 0.15));

    // --- Inner glow: bright halo around the LED ---
    const innerEl = this.pixelGlowInnerEls[index];
    innerEl.style.fill = isOff ? 'transparent' : glowColor;
    innerEl.style.opacity = isOff ? '0' : String(Math.min(0.95, lum * 1.5 + 0.2));

    // --- LED body ---
    const ledEl = this.pixelEls[index];
    ledEl.style.fill = isOff ? '#111' : ledColor;

    // --- White center hotspot ---
    const hlEl = this.pixelHighlightEls[index];
    hlEl.style.opacity = isOff ? '0' : String(Math.min(0.85, lum * 1.1 + 0.15));

    // --- Number label: visible when off, hidden when lit ---
    const labelEl = this.pixelLabelEls[index];
    labelEl.style.opacity = isOff ? '0.6' : '0';
  }
}
