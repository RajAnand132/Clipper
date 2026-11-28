// PeakCut 3D character parts: costumes, features, held items, poses and effects added to any character.
// A character design (studio/anim3d/characters.py, or the AI designer in studio/concepts.py) lists parts by name:
//   {"parts": [{"part": "cricket_helmet", "color": "#1d4fa0"}, {"part": "leg_pads"}], "hold": "bat", "pose": "zombie",
//    "effect": "ghostly"}
// so any kind of character (a cricketer, a zombie, a fairy, a king, a mermaid, an astronaut…) is built from the same
// four bodies (human, animal, robot, blob) without a fixed list of niches.
import * as THREE from "three";
import { PROPS } from "./story.js";

const M = (c, r = 0.6, extra = {}) => new THREE.MeshStandardMaterial({ color: new THREE.Color(c), roughness: r, ...extra });
const B = (c, extra = {}) => new THREE.MeshBasicMaterial({ color: new THREE.Color(c), ...extra });
function mesh(geo, m, x = 0, y = 0, z = 0) { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; return o; }
const sph = (r, m, x, y, z, sx = 1, sy = 1, sz = 1) => { const o = mesh(new THREE.SphereGeometry(r, 24, 16), m, x, y, z); o.scale.set(sx, sy, sz); return o; };
const metal = c => M(c, 0.3, { metalness: 0.7 });

// ---------------------------------------------------------------- on the head (R = head radius, origin = head centre)
const HEAD = {
  helmet: (R, c, c2) => { const g = new THREE.Group(); g.add(mesh(new THREE.SphereGeometry(R * 1.1, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), M(c || "#2f7fe0", 0.35), 0, R * 0.05, 0));
    const brim = mesh(new THREE.CylinderGeometry(R * 0.7, R * 0.7, 0.03, 20, 1, false, -Math.PI / 2, Math.PI), M(c || "#2f7fe0", 0.35), 0, R * 0.1, R * 0.55); g.add(brim); return g; },
  cricket_helmet: (R, c, c2) => { const g = HEAD.helmet(R, c || "#1d4fa0");
    for (let k = 0; k < 4; k++) { const bar = mesh(new THREE.TorusGeometry(R * 0.95, 0.012, 6, 24, Math.PI * 0.75), metal(c2 || "#c9ced6"), 0, -R * (0.18 + k * 0.14), 0); bar.rotation.set(Math.PI / 2, 0, Math.PI * 0.125); g.add(bar); }
    return g; },
  hard_hat: (R, c) => { const g = HEAD.helmet(R, c || "#f2c12e"); g.add(mesh(new THREE.CylinderGeometry(R * 1.25, R * 1.25, 0.03, 24), M(c || "#f2c12e", 0.4), 0, R * 0.08, 0)); return g; },
  space_helmet: (R) => mesh(new THREE.SphereGeometry(R * 1.45, 28, 20), M("#cfe8ff", 0.05, { transparent: true, opacity: 0.28, metalness: 0.3 }), 0, -R * 0.05, 0),
  witch_hat: (R, c) => { const g = new THREE.Group(); const m = M(c || "#3a2a5a", 0.7);
    const cone = mesh(new THREE.ConeGeometry(R * 0.75, R * 2.1, 20), m, 0, R * 1.75, -R * 0.05); cone.rotation.z = 0.18; g.add(cone);
    g.add(mesh(new THREE.CylinderGeometry(R * 1.6, R * 1.6, 0.04, 28), m, 0, R * 0.72, 0)); return g; },
  wizard_hat: (R, c) => { const g = HEAD.witch_hat(R, c || "#2f4fb0"); for (let k = 0; k < 4; k++) g.add(mesh(new THREE.OctahedronGeometry(R * 0.09), B("#ffe066"), Math.sin(k * 2) * R * 0.4, R * (1.1 + k * 0.3), R * 0.45)); return g; },
  top_hat: (R, c) => { const m = M(c || "#222222", 0.5); const g = new THREE.Group();
    g.add(mesh(new THREE.CylinderGeometry(R * 0.62, R * 0.62, R * 1.0, 24), m, 0, R * 1.25, 0)); g.add(mesh(new THREE.CylinderGeometry(R * 1.05, R * 1.05, 0.04, 28), m, 0, R * 0.76, 0)); return g; },
  chef_hat: (R) => { const g = new THREE.Group(); const m = M("#ffffff", 0.8);
    g.add(mesh(new THREE.CylinderGeometry(R * 0.7, R * 0.75, R * 0.5, 20), m, 0, R * 0.95, 0)); for (const [x, z] of [[-0.3, 0], [0.3, 0], [0, 0.3], [0, -0.3], [0, 0]]) g.add(sph(R * 0.42, m, x * R, R * 1.35, z * R)); return g; },
  police_cap: (R, c, c2) => { const g = new THREE.Group(); const m = M(c || "#1f2a44", 0.5);
    g.add(mesh(new THREE.CylinderGeometry(R * 1.05, R * 0.9, R * 0.45, 24), m, 0, R * 0.78, 0));
    const v = mesh(new THREE.CylinderGeometry(R * 0.65, R * 0.65, 0.03, 20, 1, false, -Math.PI / 2, Math.PI), M("#111111", 0.3), 0, R * 0.58, R * 0.55); g.add(v);
    g.add(mesh(new THREE.CircleGeometry(R * 0.14, 6), metal(c2 || "#f2c14e"), 0, R * 0.8, R * 1.04)); return g; },
  beret: (R, c) => sph(R * 0.95, M(c || "#c0392b", 0.8), R * 0.15, R * 0.75, 0, 1.1, 0.35, 1.05),
  beanie: (R, c) => { const g = new THREE.Group(); g.add(mesh(new THREE.SphereGeometry(R * 1.07, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), M(c || "#d8343c", 0.9), 0, R * 0.1, 0)); g.add(sph(R * 0.2, M("#ffffff", 0.9), 0, R * 1.2, 0)); return g; },
  crown: (R, c) => { const g = new THREE.Group(); const m = M(c || "#f2c14e", 0.25, { metalness: 0.8 });
    g.add(mesh(new THREE.CylinderGeometry(R * 0.5, R * 0.55, R * 0.3, 20, 1, true), m, 0, R * 1.0, 0));
    for (let k = 0; k < 5; k++) { const a = k * 1.2566; g.add(mesh(new THREE.ConeGeometry(R * 0.08, R * 0.24, 6), m, Math.cos(a) * R * 0.5, R * 1.25, Math.sin(a) * R * 0.5)); }
    return g; },
  tiara: (R, c) => { const g = new THREE.Group(); const t = mesh(new THREE.TorusGeometry(R * 0.85, 0.025, 8, 24, Math.PI), metal(c || "#e8e8f0"), 0, R * 0.68, 0); t.rotation.x = -0.35; g.add(t);
    g.add(mesh(new THREE.OctahedronGeometry(R * 0.13), B("#ff6fa5"), 0, R * 1.0, R * 0.62)); return g; },
  headband: (R, c) => { const t = mesh(new THREE.TorusGeometry(R * 1.0, R * 0.08, 8, 28), M(c || "#d8343c", 0.7), 0, R * 0.4, 0); t.rotation.x = Math.PI / 2 - 0.15; return t; },
  horns: (R, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const h = mesh(new THREE.ConeGeometry(R * 0.13, R * 0.6, 12), M(c || "#b0261e", 0.5), s * R * 0.45, R * 0.95, 0); h.rotation.z = -s * 0.45; g.add(h); } return g; },
  antlers: (R, c) => { const g = new THREE.Group(), m = M(c || "#8a5a2b", 0.8);
    for (const s of [-1, 1]) { const a = mesh(new THREE.CylinderGeometry(0.03, 0.04, R * 0.9, 6), m, s * R * 0.5, R * 1.15, 0); a.rotation.z = -s * 0.5; g.add(a);
      for (const k of [0.3, 0.6]) { const b = mesh(new THREE.CylinderGeometry(0.025, 0.03, R * 0.35, 6), m, s * R * (0.55 + k * 0.4), R * (0.95 + k * 0.6), 0); b.rotation.z = s * 0.6; g.add(b); } }
    return g; },
  halo: (R, c) => { const t = mesh(new THREE.TorusGeometry(R * 0.6, 0.035, 8, 28), B(c || "#ffe066"), 0, R * 1.35, 0); t.rotation.x = Math.PI / 2; return t; },
  hood: (R, c) => sph(R * 1.22, M(c || "#3a3a4a", 0.85, { side: THREE.DoubleSide }), 0, R * 0.12, -R * 0.2, 1, 1.05, 1.05),
  cat_ears: (R, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const e = mesh(new THREE.ConeGeometry(R * 0.25, R * 0.5, 4), M(c || "#2a2a2a", 0.6), s * R * 0.55, R * 0.9, 0); e.rotation.z = -s * 0.3; g.add(e); } return g; },
  bunny_ears: (R, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const e = sph(R * 0.2, M(c || "#ffffff", 0.7), s * R * 0.35, R * 1.45, 0, 0.7, 2.6, 0.5); e.rotation.z = -s * 0.15; g.add(e); } return g; },
  antenna: (R, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const a = mesh(new THREE.CylinderGeometry(0.015, 0.015, R * 0.8, 6), M("#222222"), s * R * 0.3, R * 1.25, 0); a.rotation.z = -s * 0.3; g.add(a); g.add(sph(R * 0.1, B(c || "#ff6fa5"), s * R * 0.42, R * 1.62, 0)); } return g; },
  mohawk: (R, c) => { const g = new THREE.Group(); for (let k = -2; k <= 2; k++) g.add(mesh(new THREE.ConeGeometry(R * 0.12, R * 0.6, 6), M(c || "#d8343c", 0.7), 0, R * 1.05 - Math.abs(k) * 0.03, k * R * 0.28)); return g; },
  ponytail: (R, c) => sph(R * 0.3, M(c || "#2a180e", 0.75), 0, R * 0.1, -R * 1.05, 0.8, 1.6, 0.8),
  beard: (R, c) => sph(R * 0.6, M(c || "#3b2414", 0.85), 0, -R * 0.6, R * 0.45, 1, 0.9, 0.6),
  long_beard: (R, c) => sph(R * 0.55, M(c || "#e8e8e8", 0.85), 0, -R * 0.95, R * 0.45, 1, 1.6, 0.6),
  mustache: (R, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const m = sph(R * 0.17, M(c || "#2a180e", 0.8), s * R * 0.16, -R * 0.3, R * 0.95, 1.3, 0.45, 0.5); m.rotation.z = s * 0.3; g.add(m); } return g; },
  eyepatch: (R) => { const g = new THREE.Group(); g.add(mesh(new THREE.CircleGeometry(R * 0.2, 16), M("#111111"), R * 0.36, R * 0.05, R * 1.0));
    const s = mesh(new THREE.TorusGeometry(R * 1.02, 0.012, 6, 28), M("#111111"), 0, R * 0.2, 0); s.rotation.set(Math.PI / 2, 0.35, 0); g.add(s); return g; },
  mask: (R, c) => { const m = mesh(new THREE.CylinderGeometry(R * 1.03, R * 1.03, R * 0.3, 28, 1, true, -Math.PI * 0.4, Math.PI * 0.8), M(c || "#111111", 0.5, { side: THREE.DoubleSide }), 0, R * 0.06, 0); return m; },
  face_mask: (R, c) => mesh(new THREE.CylinderGeometry(R * 1.02, R * 1.02, R * 0.5, 28, 1, true, -Math.PI * 0.42, Math.PI * 0.84), M(c || "#9fd3ff", 0.7, { side: THREE.DoubleSide }), 0, -R * 0.38, 0),
  sunglasses: (R) => { const g = new THREE.Group(); for (const s of [-1, 1]) g.add(mesh(new THREE.CircleGeometry(R * 0.2, 20), M("#111111", 0.1, { metalness: 0.5 }), s * R * 0.36, R * 0.06, R * 0.99));
    g.add(mesh(new THREE.BoxGeometry(R * 0.3, 0.02, 0.02), M("#111111"), 0, R * 0.1, R * 0.99)); return g; },
  fangs: (R) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const f = mesh(new THREE.ConeGeometry(R * 0.05, R * 0.18, 6), M("#ffffff", 0.3), s * R * 0.1, -R * 0.53, R * 0.88); f.rotation.x = Math.PI; g.add(f); } return g; },
  flower: (R, c) => { const g = new THREE.Group(); for (let k = 0; k < 5; k++) g.add(sph(R * 0.1, M(c || "#ff6fa5", 0.5), R * 0.75 + Math.cos(k * 1.26) * R * 0.12, R * 0.55 + Math.sin(k * 1.26) * R * 0.12, R * 0.3)); g.add(sph(R * 0.07, M("#ffd23f"), R * 0.75, R * 0.55, R * 0.33)); return g; },
  bandage_head: (R) => { const g = new THREE.Group(); for (let k = 0; k < 4; k++) { const t = mesh(new THREE.TorusGeometry(R * 1.02, R * 0.07, 6, 28), M("#efe6d2", 0.95), 0, R * (0.5 - k * 0.32), 0); t.rotation.set(Math.PI / 2 + (k % 2 ? 0.12 : -0.12), 0, 0); g.add(t); } return g; },
  third_eye: (R, c) => sph(R * 0.1, B(c || "#ff3b30"), 0, R * 0.42, R * 0.95, 0.7, 1.2, 0.5),
  bindi: (R, c) => sph(R * 0.05, M(c || "#d8343c", 0.4), 0, R * 0.28, R * 0.99, 1, 1, 0.3),
};

// ---------------------------------------------------------------- on the body (T = {y: chest height, r: radius, h: height, hip, neck})
const BODY = {
  cape: (T, c, c2) => { const m = M(c || "#c0392b", 0.7, { side: THREE.DoubleSide });
    const k = mesh(new THREE.CylinderGeometry(T.r * 1.05, T.r * 1.9, T.neck - T.hip * 0.25, 24, 1, true, Math.PI * 0.62, Math.PI * 0.76), m, 0, (T.neck + T.hip * 0.25) / 2, -T.r * 0.12); return k; },
  coat: (T, c) => mesh(new THREE.CylinderGeometry(T.r * 1.1, T.r * 1.35, T.neck - T.hip * 0.5, 24, 1, true, Math.PI * 0.12, Math.PI * 1.76), M(c || "#f4f4f4", 0.75, { side: THREE.DoubleSide }), 0, (T.neck + T.hip * 0.5) / 2 - 0.05, 0),
  lab_coat: (T, c) => BODY.coat(T, c || "#fbfbfb"),
  robe: (T, c) => mesh(new THREE.CylinderGeometry(T.r * 1.05, T.r * 1.8, T.neck - 0.05, 28, 1, true), M(c || "#8e5bd8", 0.75, { side: THREE.DoubleSide }), 0, T.neck / 2 + 0.03, 0),
  gown: (T, c) => mesh(new THREE.ConeGeometry(T.r * 2.1, T.hip * 1.15, 28, 1, true), M(c || "#ff6fa5", 0.6, { side: THREE.DoubleSide }), 0, T.hip * 0.62, 0),
  saree: (T, c, c2) => { const g = new THREE.Group(); g.add(BODY.gown(T, c || "#d8343c")); const s = mesh(new THREE.TorusGeometry(T.r * 1.05, T.r * 0.16, 8, 24), M(c2 || "#f2c14e", 0.6), 0, T.y, 0); s.rotation.set(Math.PI / 2 - 0.9, 0.3, 0); g.add(s); return g; },
  vest: (T, c) => mesh(new THREE.CylinderGeometry(T.r * 1.06, T.r * 1.08, T.h * 0.8, 24, 1, true, Math.PI * 0.18, Math.PI * 1.64), M(c || "#394058", 0.7, { side: THREE.DoubleSide }), 0, T.y, 0),
  jersey_number: (T, c) => { const g = new THREE.Group(); g.add(mesh(new THREE.CircleGeometry(T.r * 0.4, 20), M(c || "#1d4fa0", 0.6), 0, T.y + 0.05, T.r * 1.0)); return g; },
  apron: (T, c) => mesh(new THREE.BoxGeometry(T.r * 1.3, T.h * 1.1, 0.03), M(c || "#ffffff", 0.8), 0, T.y - T.h * 0.2, T.r * 0.98),
  belt: (T, c) => { const t = mesh(new THREE.TorusGeometry(T.r * 1.02, 0.05, 8, 24), M(c || "#3b2414", 0.5), 0, T.y - T.h * 0.45, 0); t.rotation.x = Math.PI / 2; return t; },
  tie: (T, c) => { const g = new THREE.Group(); const k = mesh(new THREE.ConeGeometry(T.r * 0.16, T.h * 0.7, 4), M(c || "#d8343c", 0.5), 0, T.y - T.h * 0.05, T.r * 1.02); k.rotation.x = Math.PI; g.add(k); return g; },
  bow_tie: (T, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) { const b = mesh(new THREE.ConeGeometry(T.r * 0.14, T.r * 0.3, 4), M(c || "#d8343c", 0.5), s * T.r * 0.14, T.neck - 0.08, T.r * 0.9); b.rotation.z = s * Math.PI / 2; g.add(b); } return g; },
  badge: (T, c) => mesh(new THREE.CircleGeometry(T.r * 0.16, 6), metal(c || "#f2c14e"), -T.r * 0.45, T.y + T.h * 0.15, T.r * 1.03),
  medal: (T, c) => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(T.r * 0.14, T.r * 0.14, 0.02, 16), metal(c || "#f2c14e"), 0, T.y, T.r * 1.03)); g.children[0].rotation.x = Math.PI / 2; return g; },
  necklace: (T, c) => { const t = mesh(new THREE.TorusGeometry(T.r * 0.6, 0.03, 8, 24), metal(c || "#f2c14e"), 0, T.neck - 0.12, T.r * 0.25); t.rotation.x = Math.PI / 2 - 0.5; return t; },
  sash: (T, c) => { const t = mesh(new THREE.TorusGeometry(T.r * 1.03, T.r * 0.12, 8, 28), M(c || "#f2c14e", 0.6), 0, T.y, 0); t.rotation.set(Math.PI / 2, 0.75, 0); return t; },
  armor: (T, c) => sph(T.r * 1.05, metal(c || "#9aa4b4"), 0, T.y + 0.05, T.r * 0.12, 1.05, 0.85, 1.0),
  backpack: (T, c) => { const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(T.r * 1.3, T.h * 1.1, T.r * 0.7), M(c || "#d8343c", 0.7), 0, T.y, -T.r * 1.1)); return g; },
  oxygen_tank: (T, c) => { const g = new THREE.Group(); for (const s of [-1, 1]) g.add(mesh(new THREE.CylinderGeometry(T.r * 0.28, T.r * 0.28, T.h * 1.3, 16), metal(c || "#c7cdd6"), s * T.r * 0.32, T.y, -T.r * 1.05)); return g; },
  spacesuit: (T, c) => mesh(new THREE.CylinderGeometry(T.r * 1.15, T.r * 1.2, T.neck - T.hip * 0.4, 24), M(c || "#f4f4f4", 0.6), 0, (T.neck + T.hip * 0.4) / 2, 0),
  wings_feather: (T, c) => wingPair(T, c || "#ffffff", "feather"),
  wings_bat: (T, c) => wingPair(T, c || "#2a1a2e", "bat"),
  wings_fairy: (T, c) => wingPair(T, c || "#bfe9ff", "fairy"),
  wings_butterfly: (T, c) => wingPair(T, c || "#ff8ad8", "fairy"),
  shell: (T, c) => sph(T.r * 1.25, M(c || "#3f7a3a", 0.6), 0, T.y, -T.r * 0.75, 1.1, 1.1, 0.75),
  spikes: (T, c) => { const g = new THREE.Group(); for (let k = 0; k < 5; k++) { const s = mesh(new THREE.ConeGeometry(T.r * 0.16, T.r * 0.45, 4), M(c || "#d8343c", 0.5), 0, T.neck - k * (T.h * 0.32), -T.r * 1.0); s.rotation.x = -0.7; g.add(s); } return g; },
  stethoscope: (T, c) => { const g = new THREE.Group(); const t = mesh(new THREE.TorusGeometry(T.r * 0.55, 0.025, 6, 24, Math.PI * 1.3), M(c || "#222222", 0.4), 0, T.neck - 0.18, T.r * 0.4); t.rotation.set(Math.PI / 2 - 0.4, 0, -Math.PI * 0.15); g.add(t);
    g.add(mesh(new THREE.CylinderGeometry(T.r * 0.12, T.r * 0.12, 0.04, 14), metal("#c7cdd6"), T.r * 0.25, T.y - T.h * 0.1, T.r * 1.03)); return g; },
  scarf: (T, c) => { const t = mesh(new THREE.TorusGeometry(T.r * 0.85, 0.08, 10, 26), M(c || "#d8343c", 0.7), 0, T.neck - 0.08, 0); t.rotation.x = Math.PI / 2; return t; },
  rags: (T, c) => { const g = new THREE.Group(); for (let k = 0; k < 8; k++) { const a = (k / 8) * Math.PI * 2; const p = mesh(new THREE.PlaneGeometry(T.r * 0.35, T.r * 0.5), M(c || "#6b5a48", 0.9, { side: THREE.DoubleSide }), Math.sin(a) * T.r * 1.0, T.y - T.h * 0.62, Math.cos(a) * T.r * 1.0); p.rotation.y = a; p.rotation.z = (k % 2 ? 0.3 : -0.25); g.add(p); } return g; },
  ribs: (T) => { const g = new THREE.Group(); for (let k = 0; k < 4; k++) { const t = mesh(new THREE.TorusGeometry(T.r * (0.9 - k * 0.05), 0.035, 6, 20, Math.PI), M("#f4f1e6", 0.6), 0, T.y + T.h * 0.3 - k * T.h * 0.22, T.r * 0.12); t.rotation.set(-Math.PI / 2, 0, 0); g.add(t); } return g; },
  wraps: (T) => { const g = new THREE.Group(); for (let k = 0; k < 6; k++) { const t = mesh(new THREE.TorusGeometry(T.r * 1.02, T.r * 0.08, 6, 24), M("#efe6d2", 0.95), 0, T.y + T.h * 0.45 - k * T.h * 0.2, 0); t.rotation.set(Math.PI / 2 + (k % 2 ? 0.15 : -0.15), 0, 0); g.add(t); } return g; },
  devil_tail: (T, c) => { const g = new THREE.Group(); const m = M(c || "#b0261e", 0.5); const t = mesh(new THREE.CylinderGeometry(0.03, 0.04, T.h * 1.6, 6), m, 0, T.hip * 0.85, -T.r * 1.3); t.rotation.x = -1.0; g.add(t);
    const tip = mesh(new THREE.ConeGeometry(0.1, 0.2, 4), m, 0, T.hip * 0.85 + T.h * 0.55, -T.r * 1.3 - T.h * 0.65); g.add(tip); return g; },
  fish_tail: (T, c) => { const g = new THREE.Group(); const m = M(c || "#1fa2a0", 0.4); const cone = mesh(new THREE.ConeGeometry(T.r * 0.95, T.hip * 1.1, 20), m, 0, T.hip * 0.45, 0); cone.rotation.x = Math.PI; g.add(cone);
    for (const s of [-1, 1]) { const f = sph(T.r * 0.45, m, s * T.r * 0.35, 0.08, T.r * 0.2, 1.2, 0.25, 0.8); f.rotation.z = s * 0.4; g.add(f); } return g; },
  jetpack: (T, c) => { const g = BODY.oxygen_tank(T, c || "#9aa4b4"); for (const s of [-1, 1]) { const f = mesh(new THREE.ConeGeometry(T.r * 0.2, T.r * 0.4, 12), B("#ffa62b"), s * T.r * 0.32, T.y - T.h * 0.85, -T.r * 1.05); f.rotation.x = Math.PI; g.add(f); } return g; },
  garland: (T, c) => { const g = new THREE.Group(); for (let k = 0; k < 14; k++) { const a = Math.PI * (0.15 + k / 13 * 0.7); g.add(sph(0.06, M(k % 2 ? (c || "#ff8a1f") : "#f2c12e", 0.6), Math.cos(a) * T.r * 0.85, T.neck - 0.1 - Math.sin(a) * T.h * 0.6, T.r * 0.75)); } return g; },
};

function wingPair(T, c, kind) {
  const g = new THREE.Group(); g.userData.flap = true;
  const m = M(c, kind === "fairy" ? 0.2 : 0.7, { side: THREE.DoubleSide, transparent: kind === "fairy", opacity: kind === "fairy" ? 0.65 : 1 });
  for (const s of [-1, 1]) {
    const w = new THREE.Group(); w.position.set(s * T.r * 0.55, T.y + T.h * 0.3, -T.r * 0.7); w.userData.side = s;
    let shape;
    if (kind === "bat") { shape = new THREE.Shape(); shape.moveTo(0, 0); shape.lineTo(1.1, 0.5); shape.lineTo(1.0, -0.1); shape.lineTo(0.75, 0.05); shape.lineTo(0.55, -0.25); shape.lineTo(0.35, -0.05); shape.lineTo(0, -0.3); shape.lineTo(0, 0); }
    else { shape = new THREE.Shape(); shape.moveTo(0, 0); shape.bezierCurveTo(0.4, 0.9, 1.1, 0.8, 1.0, 0.25); shape.bezierCurveTo(0.9, -0.2, 0.4, -0.5, 0, -0.15); }
    // spread out to the sides (not flat behind the back), big enough to read from the front
    const p = new THREE.Mesh(new THREE.ShapeGeometry(shape), m); p.scale.set(s * T.r * 2.4, T.r * 2.4, 1); p.rotation.y = s * 0.2; p.userData.side = s; w.add(p); g.add(w);
  }
  return g;
}

// ---------------------------------------------------------------- held in the right hand
const HOLD = {
  bat: () => { const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(0.16, 0.62, 0.05), M("#e8c98a", 0.6), 0, -0.45, 0)); g.add(mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.32, 10), M("#2a2a2a", 0.6), 0, 0, 0)); return g; },
  hockey_stick: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.9, 8), M("#c98a4b"), 0, -0.3, 0)); g.add(mesh(new THREE.BoxGeometry(0.25, 0.08, 0.05), M("#c98a4b"), 0.1, -0.75, 0)); return g; },
  racket: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.3, 8), M("#2a2a2a"), 0, -0.05, 0)); const h = mesh(new THREE.TorusGeometry(0.16, 0.02, 8, 20), M("#d8343c"), 0, -0.36, 0); g.add(h); return g; },
  sword: () => { const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(0.06, 0.8, 0.02), metal("#d6dbe3"), 0, 0.45, 0)); g.add(mesh(new THREE.BoxGeometry(0.26, 0.05, 0.06), metal("#f2c14e"), 0, 0.05, 0)); g.add(mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 8), M("#5a3a22"), 0, -0.05, 0)); return g; },
  wand: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.015, 0.02, 0.45, 8), M("#3b2414"), 0, 0.2, 0)); g.add(mesh(new THREE.OctahedronGeometry(0.07), B("#ffe066"), 0, 0.46, 0)); return g; },
  staff: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.035, 0.04, 1.5, 8), M("#6b4423"), 0, 0.2, 0)); g.add(sph(0.11, B("#7ad0ff"), 0, 0.98, 0)); return g; },
  broom: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 1.4, 8), M("#8a5a2b"), 0, 0.1, 0)); g.add(mesh(new THREE.ConeGeometry(0.16, 0.4, 12), M("#d9b45a", 0.9), 0, -0.75, 0)); return g; },
  trident: () => { const g = new THREE.Group(), m = metal("#c7cdd6"); g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 1.5, 8), m, 0, 0.2, 0)); for (const x of [-0.1, 0, 0.1]) g.add(mesh(new THREE.ConeGeometry(0.03, 0.2, 6), m, x, 1.0, 0)); return g; },
  spear: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 1.5, 8), M("#8a5a2b"), 0, 0.2, 0)); g.add(mesh(new THREE.ConeGeometry(0.05, 0.22, 8), metal("#c7cdd6"), 0, 1.05, 0)); return g; },
  shield: () => { const s = mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.05, 24), metal("#c0392b"), 0, -0.2, 0.1); s.rotation.x = Math.PI / 2; const g = new THREE.Group(); g.add(s); return g; },
  microphone: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.025, 0.02, 0.22, 10), M("#2a2a2a"), 0, 0.05, 0)); g.add(sph(0.06, metal("#c7cdd6"), 0, 0.2, 0)); return g; },
  trophy: () => { const g = new THREE.Group(), m = metal("#f2c14e"); g.add(mesh(new THREE.CylinderGeometry(0.14, 0.06, 0.2, 16), m, 0, 0.18, 0)); g.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.12, 8), m, 0, 0.03, 0)); g.add(mesh(new THREE.BoxGeometry(0.12, 0.04, 0.12), m, 0, -0.04, 0)); return g; },
  torch: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.03, 0.04, 0.5, 8), M("#6b4423"), 0, 0.1, 0)); g.add(mesh(new THREE.ConeGeometry(0.07, 0.2, 10), B("#ffa62b"), 0, 0.45, 0)); const l = new THREE.PointLight(0xffa62b, 1.5, 4); l.position.y = 0.5; g.add(l); return g; },
  flashlight: () => { const g = new THREE.Group(); const f = mesh(new THREE.CylinderGeometry(0.04, 0.05, 0.28, 12), M("#2a2a2a"), 0, 0, 0.1); f.rotation.x = Math.PI / 2; g.add(f); g.add(mesh(new THREE.CircleGeometry(0.04, 12), B("#fff6c0"), 0, 0, 0.245)); return g; },
  magnifier: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.22, 8), M("#3b2414"), 0, 0.05, 0)); const r = mesh(new THREE.TorusGeometry(0.09, 0.015, 8, 18), metal("#c7cdd6"), 0, 0.25, 0); g.add(r); g.add(mesh(new THREE.CircleGeometry(0.09, 18), M("#cfe8ff", 0.05, { transparent: true, opacity: 0.4 }), 0, 0.25, 0)); return g; },
  flute: () => { const f = mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.6, 8), M("#c98a4b"), 0, 0, 0.1); f.rotation.z = Math.PI / 2; const g = new THREE.Group(); g.add(f); return g; },
  gun_toy: () => { const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(0.06, 0.1, 0.3), M("#ff8a1f"), 0, 0, 0.1)); g.add(mesh(new THREE.BoxGeometry(0.05, 0.14, 0.06), M("#2f7fe0"), 0, -0.08, 0)); return g; },
  paintbrush: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.35, 8), M("#c98a4b"), 0, 0.12, 0)); g.add(mesh(new THREE.ConeGeometry(0.035, 0.1, 8), M("#d8343c"), 0, 0.33, 0)); return g; },
  briefcase: () => { const g = new THREE.Group(); g.add(mesh(new THREE.BoxGeometry(0.4, 0.3, 0.1), M("#5a3a22"), 0, -0.25, 0)); return g; },
  stick: () => { const g = new THREE.Group(); g.add(mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.0, 8), M("#8a5a2b"), 0, -0.3, 0)); return g; },
};

// ---------------------------------------------------------------- putting it together
// c: the built rig (runtime.js). It carries headR, torso {y, r, h}, hipY and neckY for the anchors.
export function applyParts(c, d) {
  const R = c.headR || 0.4;
  const T = { y: c.torso?.y ?? 1.2, r: c.torso?.r ?? 0.4, h: c.torso?.h ?? 0.7, hip: c.hipY ?? 0.8, neck: c.neckY ?? 1.7 };
  c.flappers = [];
  for (const p of d.parts || []) {
    const name = String(p.part || p).toLowerCase();
    try {
      if (HEAD[name]) c.head.add(HEAD[name](R, p.color, p.color2));
      else if (BODY[name]) {
        const o = BODY[name](T, p.color, p.color2);
        if (name === "fish_tail") { c.root.add(o); c.legs.forEach(l => { l.visible = false; }); c.noLegs = true; }
        else c.body.add(o);
        if (o.userData && o.userData.flap) c.flappers.push(o);
      } else if (name === "leg_pads" || name === "pads") {
        c.legs.forEach(l => l.add(mesh(new THREE.BoxGeometry(0.2, (c.legLen || 0.5) * 0.9, 0.08), M(p.color || "#ffffff", 0.8), 0, -(c.legLen || 0.5) * 0.55, (c.legR || 0.11) * 1.1)));
      } else if (name === "boots") {
        c.legs.forEach(l => l.add(mesh(new THREE.CylinderGeometry((c.legR || 0.11) * 1.3, (c.legR || 0.11) * 1.35, (c.legLen || 0.5) * 0.55, 14), M(p.color || "#2a2a2a", 0.5), 0, -(c.legLen || 0.5) * 0.85, 0)));
      } else if (name === "gloves") {
        c.arms.forEach(a => a.add(sph((c.armR || 0.1) * 1.3, M(p.color || "#ffffff", 0.6), 0, a.userData.handY ?? -0.7, 0)));
      }
    } catch (e) { console.warn("part", name, e); }
  }
  // something in the right hand
  if (d.hold) {
    try {
      let item = HOLD[d.hold] ? HOLD[d.hold]() : null;
      if (!item && PROPS[d.hold]) { const b = PROPS[d.hold](); item = b.g; item.scale.setScalar(0.42 / Math.max(0.5, b.size)); }
      if (item) { const hand = c.arms[1]; item.position.set(0, (hand.userData.handY ?? -0.7), 0.06); hand.add(item); c.holding = item;
        item.traverse(o => { if (o.isLight) { o.intensity *= 0.3; o.distance = Math.min(o.distance || 3, 2.5); } }); }   // a lamp in the hand glows, it does not light up the whole body
    } catch (e) { console.warn("hold", d.hold, e); }
  }
  // the whole look
  if (d.effect === "ghostly" || d.effect === "shadowy" || d.opacity) {
    c.root.traverse(o => {
      if (!o.isMesh || !o.material || o.material.isMeshBasicMaterial) return;
      o.material = o.material.clone();
      if (d.effect === "ghostly" || d.opacity) { o.material.transparent = true; o.material.opacity = d.opacity || 0.62; o.material.emissive = new THREE.Color(d.glowColor || "#9fb8ff"); o.material.emissiveIntensity = 0.45; o.castShadow = false; }
      if (d.effect === "shadowy") { o.material.color.multiplyScalar(0.25); }
    });
    if (d.effect === "ghostly") { const l = new THREE.PointLight(new THREE.Color(d.glowColor || "#9fb8ff"), 2.5, 5); l.position.y = (c.headY || 2) * 0.8; c.root.add(l); }
  }
  if (d.effect === "glowing") {   // a soft light around the character; its own colours stay as designed
    const l = new THREE.PointLight(new THREE.Color(d.glowColor || "#ffe9a0"), 1.6, 3.5); l.position.set(0, (c.headY || 2) * 0.7, 0.9); c.root.add(l);
  }
  if (d.eyes === "glowing" || d.effect === "shadowy") {
    const g = B(d.eyeColor || "#ff3b30");
    c.eyes.forEach(e => e.traverse(o => { if (o.isMesh) o.material = g; }));
  }
  if (d.pose === "float" || d.effect === "ghostly") { c.float = true; if (d.type !== "blob") c.legs.forEach(l => { l.visible = false; }); }
  c.pose = d.pose || "";
  return c;
}

// called every frame after the normal animation: poses that last, wings that flap, floating
export function animateParts(c, t, busy) {
  if (c.pose === "zombie" && !busy) { c.arms.forEach(a => { a.rotation.x = -1.45; a.rotation.z *= 0.3; }); c.head.rotation.z = Math.sin(t * 1.3) * 0.12; c.body.rotation.z = Math.sin(t * 0.9) * 0.04; }
  if (c.pose === "hunched") { c.body.rotation.x += 0.16; c.head.rotation.x -= 0.1; }
  if (c.pose === "proud") { c.body.rotation.x -= 0.05; c.head.rotation.x -= 0.06; }
  if (c.pose === "hands_on_hips" && !busy) c.arms.forEach((a, i) => { a.rotation.z = (i ? 1 : -1) * 0.9; a.rotation.x = 0.4; });
  if (c.float) c.root.position.y += 0.35 + Math.sin(t * 1.6 + (c.seed || 0)) * 0.12;
  for (const w of c.flappers || []) w.children.forEach(x => { x.rotation.y = x.userData.side * (0.15 + Math.sin(t * 6) * 0.3); });
  if (c.holding && !busy) { c.arms[1].rotation.x = Math.min(c.arms[1].rotation.x, -0.35); }
}

export const PART_NAMES = [...Object.keys(HEAD), ...Object.keys(BODY), "leg_pads", "boots", "gloves"];
export const HOLD_NAMES = Object.keys(HOLD);
