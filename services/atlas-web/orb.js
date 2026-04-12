// orb.js — Hermes Phase A sprint orb
// Three.js sphere with simplex-noise vertex displacement, Fresnel edge glow,
// and a 5-state machine wired to the rest of the app via window.AtlasOrb.

import * as THREE from 'three';

const VERT = /* glsl */ `
uniform float uTime;
uniform float uAudioLevel;
uniform float uState; // 0 idle, 1 listening, 2 thinking, 3 speaking, 4 error

varying vec3 vNormal;
varying vec3 vView;

// cheap 3d noise (not true simplex, but good enough for the sprint)
float hash(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,45.164))) * 43758.5453); }
float noise(vec3 p){
  vec3 i = floor(p); vec3 f = fract(p);
  f = f*f*(3.0-2.0*f);
  float n000 = hash(i);
  float n100 = hash(i+vec3(1,0,0));
  float n010 = hash(i+vec3(0,1,0));
  float n110 = hash(i+vec3(1,1,0));
  float n001 = hash(i+vec3(0,0,1));
  float n101 = hash(i+vec3(1,0,1));
  float n011 = hash(i+vec3(0,1,1));
  float n111 = hash(i+vec3(1,1,1));
  vec4 n0 = mix(vec4(n000,n100,n010,n110), vec4(n001,n101,n011,n111), f.z);
  vec2 n1 = mix(n0.xy, n0.zw, f.y);
  return mix(n1.x, n1.y, f.x);
}

void main(){
  float breath = 1.0 + sin(uTime * 0.8) * 0.012;
  float activity = uAudioLevel;
  float n = noise(position * 1.8 + uTime * 0.35);
  float disp = n * (0.03 + activity * 0.22);
  if (uState > 1.5 && uState < 2.5) {
    disp += sin(uTime * 1.2 + position.y * 3.0) * 0.04;
  }
  vec3 pos = position * breath + normal * disp;
  vec4 mv = modelViewMatrix * vec4(pos, 1.0);
  vNormal = normalize(normalMatrix * normal);
  vView   = normalize(-mv.xyz);
  gl_Position = projectionMatrix * mv;
}
`;

const FRAG = /* glsl */ `
uniform vec3  uCore;
uniform vec3  uGlow;
uniform float uState;
uniform float uAudioLevel;

varying vec3 vNormal;
varying vec3 vView;

void main(){
  float fresnel = pow(1.0 - max(dot(vNormal, vView), 0.0), 3.0);
  vec3 base = mix(uCore, uGlow, fresnel);
  float intensity = 0.35 + uAudioLevel * 0.75;
  if (uState > 3.5) {
    base = mix(base, vec3(0.6, 0.12, 0.12), 0.6); // error
    intensity = 0.35;
  }
  gl_FragColor = vec4(base * intensity, 1.0);
}
`;

export class AtlasOrb {
  constructor(canvas) {
    this.canvas = canvas;
    this.state = 'idle';
    this.audioLevel = 0;
    this.targetLevel = 0;
    this._initThree();
    this._resize();
    window.addEventListener('resize', () => this._resize());
    requestAnimationFrame((t) => this._tick(t));
  }

  _initThree() {
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    this.camera.position.z = 3.0;

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const geo = new THREE.SphereGeometry(1, 96, 96);
    this.uniforms = {
      uTime:       { value: 0 },
      uAudioLevel: { value: 0 },
      uState:      { value: 0 },
      uCore:       { value: new THREE.Color('#0A0F1E').convertSRGBToLinear() },
      uGlow:       { value: new THREE.Color('#2563EB').convertSRGBToLinear() },
    };
    const mat = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: this.uniforms,
      transparent: true,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.scene.add(this.mesh);
  }

  _resize() {
    const w = this.canvas.clientWidth * window.devicePixelRatio;
    const h = this.canvas.clientHeight * window.devicePixelRatio;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  _tick(t) {
    const ts = t * 0.001;
    this.uniforms.uTime.value = ts;

    // easing toward target level
    this.audioLevel += (this.targetLevel - this.audioLevel) * 0.15;
    this.uniforms.uAudioLevel.value = this.audioLevel;

    // rotation per state
    const rot = {
      idle:      0.003,
      listening: 0.008,
      thinking:  0.005,
      speaking:  0.006,
      error:     0.0,
    }[this.state] ?? 0.003;
    this.mesh.rotation.y += rot;
    this.mesh.rotation.x += rot * 0.3;

    this.renderer.render(this.scene, this.camera);
    requestAnimationFrame((nt) => this._tick(nt));
  }

  setState(state) {
    this.state = state;
    const stateId = { idle: 0, listening: 1, thinking: 2, speaking: 3, error: 4 }[state] ?? 0;
    this.uniforms.uState.value = stateId;
    const glowByState = { idle: '#2563EB', listening: '#2563EB', thinking: '#7C3AED', speaking: '#2563EB', error: '#EF4444' };
    this.uniforms.uGlow.value = new THREE.Color(glowByState[state] ?? '#2563EB').convertSRGBToLinear();
    this.canvas.classList.remove('idle', 'listening', 'thinking', 'speaking', 'error');
    this.canvas.classList.add(state);
  }

  setAudioLevel(level) {
    this.targetLevel = Math.max(0, Math.min(1, level));
  }
}
