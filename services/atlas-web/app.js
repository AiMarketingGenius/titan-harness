// app.js — orb orchestration + WS client + mic stub
// Hermes Phase A sprint scaffold. Wires the orb state machine to the
// Atlas API shim on the same origin. Mic capture is stubbed behind the
// mic button for this sprint — Web Audio AnalyserNode drives the orb's
// live audio level so you can see it react to your voice, but STT
// round-trip through the WS is queued for the next bundle.

import { AtlasOrb } from '/atlas/orb.js';

const canvas       = document.getElementById('orb-canvas');
const microCopy    = document.getElementById('micro-copy');
const stateChip    = document.getElementById('state-chip');
const transcript   = document.getElementById('transcript');
const textForm     = document.getElementById('text-form');
const textInput    = document.getElementById('text-input');
const micBtn       = document.getElementById('mic-btn');
const statusDot    = document.getElementById('status-dot');
const statusText   = document.getElementById('status-text');

const orb = new AtlasOrb(canvas);
orb.setState('idle');

const sid = crypto?.randomUUID?.() ?? ('sid-' + Math.random().toString(36).slice(2));
let ws = null;
let audioCtx = null;
let analyser = null;
let micStream = null;
let rafId = null;

function setStatus(state, text) {
  statusDot.className = 'dot ' + state;
  statusText.textContent = text;
}
function setState(state, copy) {
  orb.setState(state);
  stateChip.textContent = state.toUpperCase();
  if (copy !== undefined) microCopy.textContent = copy;
}
function append(role, text) {
  const el = document.createElement('div');
  el.className = 'msg ' + role;
  el.textContent = text;
  transcript.appendChild(el);
  transcript.scrollTop = transcript.scrollHeight;
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) throw new Error(String(r.status));
    const s = await r.json();
    setStatus('ok', `${s.commit} · ${s.hermes_substrate.phase_a_reviewer_graded}`);
    append('system', `Connected to atlas-api ${s.commit}. Phase A: ${s.hermes_substrate.phase_a_reviewer_graded}. Kokoro: ${s.hermes_substrate.kokoro}.`);
  } catch (e) {
    setStatus('err', 'status endpoint unreachable');
  }
}

function openWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/text/${sid}`);
  ws.addEventListener('open', () => setStatus('ok', 'ws open'));
  ws.addEventListener('close', () => setStatus('err', 'ws closed'));
  ws.addEventListener('message', (ev) => {
    try {
      const m = JSON.parse(ev.data);
      if (m.type === 'reply') {
        setState('speaking', '');
        append('atlas', m.text);
        if (m.violations_blocked?.length) {
          append('system', `[guardrail blocked: ${m.violations_blocked.join(', ')}]`);
        }
        setTimeout(() => setState('idle', 'Ask me anything about AMG'), 900);
      }
    } catch {}
  });
}

textForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = textInput.value.trim();
  if (!q) return;
  append('user', q);
  textInput.value = '';
  setState('thinking', 'Give me a second…');
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'text', text: q }));
  } else {
    setStatus('err', 'ws not connected');
    setState('error');
  }
});

micBtn.addEventListener('click', async () => {
  const pressed = micBtn.getAttribute('aria-pressed') === 'true';
  if (pressed) {
    stopMic();
    micBtn.setAttribute('aria-pressed', 'false');
    setState('idle', 'Ask me anything about AMG');
  } else {
    try {
      await startMic();
      micBtn.setAttribute('aria-pressed', 'true');
      setState('listening', 'Listening…');
    } catch (e) {
      append('system', `[mic error: ${e.message}]`);
    }
  }
});

async function startMic() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('getUserMedia unavailable');
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
  });
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioCtx.createMediaStreamSource(micStream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  const data = new Uint8Array(analyser.frequencyBinCount);
  const loop = () => {
    analyser.getByteFrequencyData(data);
    let sum = 0;
    for (let i = 10; i < 40; i++) sum += data[i];
    const level = Math.min(1, (sum / 30) / 255 * 2);
    orb.setAudioLevel(level);
    rafId = requestAnimationFrame(loop);
  };
  loop();
}
function stopMic() {
  cancelAnimationFrame(rafId); rafId = null;
  if (analyser) { try { analyser.disconnect(); } catch {} analyser = null; }
  if (audioCtx) { try { audioCtx.close(); } catch {} audioCtx = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  orb.setAudioLevel(0);
}

window.addEventListener('load', () => {
  loadStatus();
  openWs();
  setState('idle', 'Ask me anything about AMG');
});
