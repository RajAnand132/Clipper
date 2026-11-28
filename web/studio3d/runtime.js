// PeakCut 3D runtime: builds a world and toon characters from a scene spec (studio/anim3d/director.py) and
// renders any moment of it exactly: renderAt(t). Used by the render worker (headless Chrome) and, later, by the
// live preview in the app. Everything is a function of t and the spec's seed, so a frame always looks the same.
import * as THREE from "three";
import { buildStory, updateStory, storyLook, storyCamera } from "./story.js";
import { applyParts, animateParts } from "./parts.js";
import { KITS, buildSky, TIMES, weatherize } from "./sets.js";

// ====================================================================== small helpers
const clamp01 = x => Math.max(0, Math.min(1, x));
const ease = x => { x = clamp01(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, u) => a + (b - a) * u;
const col = c => new THREE.Color(c);
function rng(seed) { let s = (seed >>> 0) % 2147483646 + 1; return () => (s = (s * 16807) % 2147483647) / 2147483647; }
const matCache = new Map();
function mat(c, r = 0.62, extra = null) {
  const key = extra ? null : `${c}|${r}`;
  if (key && matCache.has(key)) return matCache.get(key);
  const m = new THREE.MeshStandardMaterial({ color: col(c), roughness: r, ...(extra || {}) });
  if (key) matCache.set(key, m);
  return m;
}
function sph(r, m, x = 0, y = 0, z = 0, sx = 1, sy = 1, sz = 1) {
  const o = new THREE.Mesh(new THREE.SphereGeometry(r, 28, 20), m);
  o.position.set(x, y, z); o.scale.set(sx, sy, sz); o.castShadow = true; return o;
}
function cap(r, len, m) { const o = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 14), m); o.castShadow = true; return o; }
function limb(r, len, m, end = null) {
  const g = new THREE.Group();
  const c = cap(r, len, m); c.position.y = -(len / 2 + r * 0.6); g.add(c);
  if (end) { end.position.y = -(len + r * 1.1); g.add(end); }
  return g;
}
function eye(x, y, z, r, iris = 0x1c120c) {
  const g = new THREE.Group(); g.position.set(x, y, z);
  g.add(sph(r, mat(0xffffff, 0.25)));
  g.add(sph(r * 0.6, mat(iris, 0.2), 0, -r * 0.05, r * 0.52));
  g.add(sph(r * 0.2, new THREE.MeshBasicMaterial({ color: 0xffffff }), r * 0.2, r * 0.2, r * 0.92));
  return g;
}
function brow(x, y, z, len, m, side) {
  const b = cap(0.024, len, m); b.rotation.z = Math.PI / 2; b.position.set(x, y, z); b.userData.side = side; return b;
}
function finish(c) { c.root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = false; } }); return c; }

// ====================================================================== toon characters
// Every builder returns the same rig: root > body > head(eyes, brows, mouth), arms[2], legs[2].
function rigBase() { const root = new THREE.Group(), body = new THREE.Group(); root.add(body); return { root, body }; }

function buildHuman(d) {
  const { root, body } = rigBase();
  const child = d.age === "child", old = d.age === "old", fem = d.gender === "f";
  const skin = mat(d.skin || 0xe9b48a, 0.6), top = mat(d.top || 0x2f7fe0, 0.7), bottom = mat(d.bottom || 0x394058, 0.8);
  const hairM = mat(old ? 0xd9d9d9 : (d.hair || 0x2a180e), 0.75), dark = mat(0x2a180e, 0.35), shoe = mat(d.shoes || 0x5a3a24, 0.6);
  const P = child ? { hr: 0.42, tr: 0.3, tl: 0.34, ty: 0.98, hy: 1.68, hip: 0.58, ll: 0.2, lr: 0.1, sh: 1.3, al: 0.34, ar: 0.085 }
                  : { hr: 0.36, tr: 0.33, tl: 0.62, ty: 1.3, hy: 2.12, hip: 0.92, ll: 0.5, lr: 0.12, sh: 1.74, al: 0.56, ar: 0.095 };
  const torso = cap(P.tr, P.tl, top); torso.position.y = P.ty; body.add(torso);
  if (d.emblem !== false) { const e = new THREE.Mesh(new THREE.CircleGeometry(P.tr * 0.35, 5), mat(d.accent || 0xffd23f, 0.5)); e.position.set(0, P.ty + 0.05, P.tr + 0.005); body.add(e); }
  if (fem && d.dress !== false) {   // a skirt over the hips
    const sk = new THREE.Mesh(new THREE.ConeGeometry(P.tr * 1.45, P.tl * 0.75, 24, 1, true), bottom);
    sk.position.y = P.ty - P.tl * 0.42; body.add(sk);
  }
  const head = new THREE.Group(); head.position.set(0, P.hy, 0); body.add(head);
  head.add(sph(P.hr, skin));
  const hs = d.hairStyle || (fem ? "long" : (old ? "short" : "short"));
  if (hs !== "bald") head.add(sph(P.hr * 1.03, hairM, 0, P.hr * 0.14, -P.hr * 0.12, 1, 0.92, 0.95));
  if (hs === "long") { const back = sph(P.hr * 0.95, hairM, 0, -P.hr * 0.55, -P.hr * 0.42, 1.05, 1.35, 0.6); head.add(back); }
  if (hs === "bun") head.add(sph(P.hr * 0.42, hairM, 0, P.hr * 0.95, -P.hr * 0.45));
  if (hs === "spiky") for (let i = -2; i <= 2; i++) { const s = new THREE.Mesh(new THREE.ConeGeometry(P.hr * 0.18, P.hr * 0.5, 6), hairM); s.position.set(i * P.hr * 0.3, P.hr * 0.95, -0.05); s.rotation.z = -i * 0.25; head.add(s); }
  if (d.hat === "cap") {
    const c = mat(d.hatColor || 0xff8a1f, 0.6);
    head.add(sph(P.hr * 1.05, c, 0, P.hr * 0.36, 0, 1, 0.58, 1));
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(P.hr * 0.72, P.hr * 0.72, 0.04, 24), c);
    brim.position.set(0, P.hr * 0.4, P.hr * 0.9); brim.scale.set(1, 1, 0.75); brim.rotation.x = 0.12; head.add(brim);
  } else if (d.hat === "turban") {
    head.add(sph(P.hr * 1.1, mat(d.hatColor || 0xe8a02a, 0.7), 0, P.hr * 0.42, -0.02, 1.05, 0.72, 1.05));
  } else if (d.hat === "crown") {
    const cr = new THREE.Mesh(new THREE.CylinderGeometry(P.hr * 0.6, P.hr * 0.66, P.hr * 0.42, 10, 1, true), mat(0xf6c431, 0.3, { metalness: 0.6, side: THREE.DoubleSide }));
    cr.position.y = P.hr * 0.98; head.add(cr);
  } else if (d.hat === "fedora") {
    const c = mat(d.hatColor || 0x4a3b2e, 0.7);
    const top2 = new THREE.Mesh(new THREE.CylinderGeometry(P.hr * 0.7, P.hr * 0.78, P.hr * 0.55, 20), c); top2.position.y = P.hr * 0.9; head.add(top2);
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(P.hr * 1.25, P.hr * 1.25, 0.04, 24), c); brim.position.y = P.hr * 0.65; head.add(brim);
  }
  for (const s of [-1, 1]) { head.add(sph(P.hr * 0.2, skin, s * P.hr * 0.98, -0.02, 0)); head.add(sph(P.hr * 0.17, mat(0xff8f8f, 0.6), s * P.hr * 0.57, -P.hr * 0.29, P.hr * 0.78, 1, 0.6, 0.4)); }
  const er = child ? 0.1 : 0.075;
  const eyes = [eye(-P.hr * 0.36, P.hr * 0.05, P.hr * 0.84, er), eye(P.hr * 0.36, P.hr * 0.05, P.hr * 0.84, er)]; eyes.forEach(e => head.add(e));
  const by = P.hr * 0.42;
  const brows = [brow(-P.hr * 0.36, by, P.hr * 0.94, P.hr * 0.22, old ? hairM : dark, -1), brow(P.hr * 0.36, by, P.hr * 0.94, P.hr * 0.22, old ? hairM : dark, 1)]; brows.forEach(b => head.add(b));
  if (d.glasses) for (const s of [-1, 1]) { const g = new THREE.Mesh(new THREE.TorusGeometry(er * 1.35, 0.012, 8, 20), mat(0x222222, 0.3)); g.position.set(s * P.hr * 0.36, P.hr * 0.05, P.hr * 0.95); head.add(g); }
  const mouth = sph(child ? 0.06 : 0.05, mat(0x7a2a22, 0.5), 0, -P.hr * 0.43, P.hr * 0.9, 1.5, 0.12, 0.6); head.add(mouth);
  if (old && !fem) head.add(sph(P.hr * 0.55, hairM, 0, -P.hr * 0.62, P.hr * 0.45, 1, 0.8, 0.6));   // beard
  if (d.accessory === "scarf") { const sc = new THREE.Mesh(new THREE.TorusGeometry(P.tr * 0.95, 0.07, 12, 28), mat(d.accColor || 0xd8343c, 0.7)); sc.rotation.x = Math.PI / 2; sc.position.y = P.hy - P.hr * 0.95; body.add(sc); }
  if (d.accessory === "bow") { const bw = mat(d.accColor || 0xff4f9a, 0.5); head.add(sph(P.hr * 0.2, bw, -P.hr * 0.2, P.hr * 0.92, -0.05, 1.2, 0.8, 0.6)); head.add(sph(P.hr * 0.2, bw, P.hr * 0.2, P.hr * 0.92, -0.05, 1.2, 0.8, 0.6)); }
  const arms = [-1, 1].map(s => { const a = limb(P.ar, P.al, top, sph(P.ar * 1.05, skin)); a.position.set(s * (P.tr + P.ar * 0.7), P.sh, 0); a.userData.rest = s * 0.18; a.userData.handY = -(P.al + P.ar * 1.1); body.add(a); return a; });
  const legs = [-1, 1].map(s => { const l = limb(P.lr, P.ll, fem && d.dress !== false ? skin : bottom, sph(P.lr * 1.2, shoe, 0, 0, 0, 1, 0.6, 1.5)); l.position.set(s * P.tr * 0.45, P.hip, 0); root.add(l); return l; });
  if (old) body.rotation.x = 0.06;
  return finish({ root, body, head, eyes, brows, mouth, arms, legs, browY: by, mouthBase: 0.12, headY: P.hy, top: P.hy + P.hr,
                  headR: P.hr, torso: { y: P.ty, r: P.tr, h: P.tl }, hipY: P.hip, neckY: P.hy - P.hr * 0.85, legLen: P.ll, legR: P.lr, armR: P.ar });
}

function buildAnimal(d) {
  const { root, body } = rigBase();
  const fur = mat(d.fur || 0x9a6431, 0.85), light = mat(d.belly || 0xf0cf95, 0.8), dark = mat(0x2a180e, 0.35);
  const bird = d.kind === "bird";
  body.add(sph(0.8, fur, 0, 1.12, 0, 1, 1.12, 0.92));
  body.add(sph(0.56, light, 0, 1.02, 0.38, 1, 1.12, 0.6));
  const head = new THREE.Group(); head.position.set(0, 2.15, 0.06); body.add(head);
  head.add(sph(0.58, fur, 0, 0, 0, 1.06, 0.95, 1));
  const ears = d.ears || "round";
  for (const s of [-1, 1]) {
    if (ears === "round") { head.add(sph(0.18, fur, s * 0.42, 0.44, -0.02)); head.add(sph(0.1, light, s * 0.42, 0.44, 0.08, 1, 1, 0.5)); }
    if (ears === "big_round") { head.add(sph(0.3, fur, s * 0.5, 0.45, -0.05, 1, 1, 0.45)); head.add(sph(0.2, mat(0xf3a7b5, 0.7), s * 0.5, 0.45, 0.04, 1, 1, 0.3)); }
    if (ears === "long") { const e = cap(0.12, 0.62, fur); e.position.set(s * 0.22, 0.85, -0.05); e.rotation.z = -s * 0.15; head.add(e); const i = cap(0.06, 0.5, mat(0xf3a7b5, 0.7)); i.position.set(s * 0.22, 0.85, 0.05); i.rotation.z = -s * 0.15; head.add(i); }
    if (ears === "pointy") { const e = new THREE.Mesh(new THREE.ConeGeometry(0.17, 0.38, 4), fur); e.position.set(s * 0.33, 0.55, 0); e.rotation.z = -s * 0.25; head.add(e); }
    if (ears === "floppy") { const e = sph(0.22, mat(d.earColor || d.fur || 0x7a4a26, 0.85), s * 0.58, 0.02, -0.02, 0.55, 1.25, 0.8); e.rotation.z = s * 0.3; head.add(e); }
    if (ears === "elephant") { const e = sph(0.48, fur, s * 0.66, 0.05, -0.1, 0.25, 1.1, 1); head.add(e); }
    if (ears === "small") head.add(sph(0.1, fur, s * 0.36, 0.48, 0));
    if (ears === "horns") { head.add(sph(0.13, fur, s * 0.5, 0.28, 0)); const h = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.25, 8), mat(0xf3ead6, 0.5)); h.position.set(s * 0.28, 0.58, 0); h.rotation.z = -s * 0.3; head.add(h); }
  }
  const sn = d.snout || "bear";
  let mouthZ = 0.53, mouthY = -0.29;
  if (sn === "bear" || sn === "dog") {
    head.add(sph(0.27, light, 0, -0.12, 0.46, 1.18, 0.85, sn === "dog" ? 1.25 : 0.9));
    head.add(sph(0.095, dark, 0, -0.02, sn === "dog" ? 0.78 : 0.71, 1.35, 1, 1));
    if (sn === "dog") mouthZ = 0.6;
  } else if (sn === "cat" || sn === "small") {
    head.add(sph(0.13, light, -0.1, -0.16, 0.5)); head.add(sph(0.13, light, 0.1, -0.16, 0.5));
    head.add(sph(0.06, mat(0xf07a8a, 0.5), 0, -0.06, 0.58, 1.3, 0.8, 1));
    mouthZ = 0.55; mouthY = -0.3;
    if (d.whiskers !== false && sn === "cat") for (const s of [-1, 1]) for (const k of [-1, 1]) { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.42), dark); w.rotation.z = Math.PI / 2 + k * 0.12; w.position.set(s * 0.3, -0.14 + k * 0.04, 0.5); head.add(w); }
  } else if (sn === "pig") {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.19, 0.16, 20), mat(d.belly || 0xf4a6b0, 0.6)); s.rotation.x = Math.PI / 2; s.position.set(0, -0.1, 0.6); head.add(s);
    for (const x of [-0.06, 0.06]) head.add(sph(0.035, dark, x, -0.1, 0.68));
  } else if (sn === "trunk") {
    let y = -0.15, z = 0.5;
    for (let i = 0; i < 4; i++) { const t = sph(0.14 - i * 0.02, fur, 0, y, z); head.add(t); y -= 0.16; z += 0.06 - i * 0.03; }
    mouthY = -0.32; mouthZ = 0.42;
  } else if (sn === "beak") {
    const b = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.3, 12), mat(0xffa21f, 0.45)); b.rotation.x = Math.PI / 2; b.position.set(0, -0.1, 0.66); head.add(b);
    mouthY = -0.2; mouthZ = 0.6;
  } else if (sn === "croc") {   // a long flat snout with teeth
    head.add(sph(0.3, fur, 0, -0.16, 0.62, 0.95, 0.42, 1.7));
    for (const s of [-1, 1]) for (let k = 0; k < 5; k++) { const tt = new THREE.Mesh(new THREE.ConeGeometry(0.025, 0.07, 4), mat(0xffffff, 0.4)); tt.position.set(s * 0.2, -0.24, 0.45 + k * 0.1); tt.rotation.x = Math.PI; head.add(tt); }
    for (const s of [-1, 1]) head.add(sph(0.035, dark, s * 0.07, -0.08, 1.1));
    mouthY = -0.26; mouthZ = 0.95;
  } else if (sn === "long") {   // horse, donkey, camel
    head.add(sph(0.3, light, 0, -0.24, 0.5, 0.9, 0.85, 1.4));
    for (const s of [-1, 1]) head.add(sph(0.04, dark, s * 0.09, -0.2, 0.9));
    mouthY = -0.42; mouthZ = 0.72;
  } else if (sn === "monkey") {
    head.add(sph(0.4, light, 0, -0.08, 0.3, 1.1, 0.95, 0.8));
    head.add(sph(0.05, dark, -0.05, -0.05, 0.62)); head.add(sph(0.05, dark, 0.05, -0.05, 0.62));
  }
  if (d.mane) { const m = mat(d.mane, 0.9); for (let i = 0; i < 14; i++) { const a = (i / 14) * Math.PI * 2; head.add(sph(0.24, m, Math.cos(a) * 0.62, Math.sin(a) * 0.6, -0.12)); } }
  const er = d.bigEyes ? 0.13 : 0.105;
  const eyes = [eye(-0.2, 0.14, 0.45, er), eye(0.2, 0.14, 0.45, er)]; eyes.forEach(e => head.add(e));
  const brows = [brow(-0.2, 0.31, 0.5, 0.12, dark, -1), brow(0.2, 0.31, 0.5, 0.12, dark, 1)]; brows.forEach(b => head.add(b));
  const mouth = sph(0.085, mat(0x5c1c14, 0.5), 0, mouthY, mouthZ, 1.5, 0.12, 0.6); head.add(mouth);
  if (d.accessory === "scarf") { const s = new THREE.Mesh(new THREE.TorusGeometry(0.44, 0.11, 14, 36), mat(d.accColor || 0xd8343c, 0.7)); s.rotation.x = Math.PI / 2; s.position.y = 1.78; body.add(s); }
  if (d.accessory === "bow") { const bw = mat(d.accColor || 0xff4f9a, 0.5); head.add(sph(0.13, bw, -0.14, 0.52, 0.12, 1.2, 0.8, 0.6)); head.add(sph(0.13, bw, 0.14, 0.52, 0.12, 1.2, 0.8, 0.6)); }
  if (d.accessory === "bandana") { const s = new THREE.Mesh(new THREE.TorusGeometry(0.44, 0.08, 10, 30), mat(d.accColor || 0xf2c12e, 0.6)); s.rotation.x = Math.PI / 2; s.position.y = 1.8; body.add(s); }
  if (d.accessory === "hat") { const c = mat(d.accColor || 0x2f7fe0, 0.6); head.add(sph(0.6, c, 0, 0.3, 0, 1, 0.5, 1)); }
  if (d.pattern === "stripes") for (let k = 0; k < 4; k++) { const b = new THREE.Mesh(new THREE.TorusGeometry(0.78 - Math.abs(k - 1.5) * 0.06, 0.05, 6, 24), mat(d.patternColor || 0x2a1a10, 0.8)); b.rotation.x = Math.PI / 2; b.position.y = 0.72 + k * 0.28; b.scale.set(1, 0.92, 1); body.add(b); }
  if (d.pattern === "spots") { const R2 = rng(7); for (let k = 0; k < 12; k++) { const a = R2() * Math.PI * 2, y = 0.7 + R2() * 0.9; const sp = sph(0.1 + R2() * 0.06, mat(d.patternColor || 0x5a3a1a, 0.8), Math.sin(a) * 0.78, y, Math.cos(a) * 0.72, 1, 1, 0.3); sp.lookAt(0, y, 0); body.add(sp); } }
  if (d.pattern === "scales") { const R2 = rng(9); for (let k = 0; k < 18; k++) { const a = Math.PI * (0.6 + R2() * 0.8), y = 0.7 + R2() * 0.9; body.add(sph(0.07, mat(d.patternColor || 0x2f6a2a, 0.5), Math.sin(a) * 0.8, y, Math.cos(a) * 0.74)); } }
  const tail = d.tail || "short";
  if (tail === "short") body.add(sph(0.16, fur, 0, 0.75, -0.82));
  if (tail === "bushy") { const t = sph(0.32, fur, 0, 1.15, -0.95, 0.8, 1.4, 0.8); t.rotation.x = 0.4; body.add(t); body.add(sph(0.16, light, 0, 1.6, -1.05)); }
  if (tail === "long") { const t = cap(0.07, 0.9, fur); t.position.set(0, 0.9, -0.95); t.rotation.x = -0.9; body.add(t); }
  if (tail === "curly") { const t = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.04, 8, 16), fur); t.position.set(0, 0.85, -0.85); body.add(t); }
  if (tail === "dragon") { for (let k = 0; k < 5; k++) { body.add(sph(0.26 - k * 0.045, fur, 0, 0.7 - k * 0.1, -0.85 - k * 0.3)); const sp = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.16, 4), mat(d.patternColor || 0xd8343c, 0.5)); sp.position.set(0, 0.95 - k * 0.12, -0.85 - k * 0.3); body.add(sp); } }
  if (tail === "fish") { const t = sph(0.3, fur, 0, 0.9, -0.95, 0.25, 1, 0.8); body.add(t); }
  if (tail === "flat") { const t = sph(0.32, mat(d.patternColor || 0x5a3a22, 0.7), 0, 0.5, -0.95, 0.9, 0.18, 1.3); t.rotation.x = 0.3; body.add(t); }
  const armM = bird ? fur : fur;
  const arms = [-1, 1].map(s => {
    const a = bird ? (() => { const g = new THREE.Group(); const w = sph(0.42, armM, 0, -0.38, 0, 0.35, 1, 0.85); g.add(w); return g; })()
                   : limb(0.18, 0.58, armM, sph(0.16, light));
    a.position.set(s * 0.8, 1.62, 0.05); a.userData.rest = s * (bird ? 0.12 : 0.28); a.userData.handY = -(0.58 + 0.18 * 1.1); body.add(a);
    if (d.arms === false) a.visible = false;
    return a;
  });
  const footM = bird ? mat(0xffa21f, 0.5) : light;
  const legs = [-1, 1].map(s => { const l = limb(bird ? 0.07 : 0.21, 0.24, bird ? footM : fur, sph(0.18, footM, 0, 0, 0.08, 1, 0.55, 1.3)); l.position.set(s * 0.37, 0.62, 0); root.add(l); if (d.legs === false) l.visible = false; return l; });
  if (d.legs === false) body.position.y = -0.45;   // a snake or a fish rests on the ground
  return finish({ root, body, head, eyes, brows, mouth, arms, legs, browY: 0.31, mouthBase: 0.12, headY: 2.15, top: 2.75,
                  headR: 0.58, torso: { y: 1.12, r: 0.8, h: 0.9 }, hipY: 0.62, neckY: 1.78, legLen: 0.24, legR: 0.21, armR: 0.18, noLegs: d.legs === false });
}

function buildRobot(d) {
  const { root, body } = rigBase();
  const m = mat(d.body || 0x9fb4c8, 0.35, { metalness: 0.5 }), acc = mat(d.accent || 0x2fb7ff, 0.4), dark = mat(0x1d2430, 0.4);
  const torso = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1.1, 0.8), m); torso.position.y = 1.15; body.add(torso);
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.35, 0.02), acc); panel.position.set(0, 1.2, 0.41); body.add(panel);
  const head = new THREE.Group(); head.position.set(0, 2.1, 0); body.add(head);
  head.add(new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.75, 0.75), m));
  const screen = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.55, 0.02), dark); screen.position.z = 0.38; head.add(screen);
  const glow = new THREE.MeshBasicMaterial({ color: col(d.accent || 0x2fb7ff) });
  const mkEye = x => { const g = new THREE.Group(); g.position.set(x, 0.07, 0.4); g.add(new THREE.Mesh(new THREE.CircleGeometry(0.09, 20), glow)); return g; };
  const eyes = [mkEye(-0.18), mkEye(0.18)]; eyes.forEach(e => head.add(e));
  const brows = [-1, 1].map(s => { const b = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.03, 0.01), glow); b.position.set(s * 0.18, 0.22, 0.4); b.userData.side = s; head.add(b); return b; });
  const mouth = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.2, 0.01), glow); mouth.position.set(0, -0.14, 0.4); head.add(mouth);
  const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.3), dark); ant.position.y = 0.52; head.add(ant); head.add(sph(0.07, acc, 0, 0.7, 0));
  const arms = [-1, 1].map(s => { const a = limb(0.12, 0.6, m, sph(0.15, acc)); a.position.set(s * 0.68, 1.6, 0); a.userData.rest = s * 0.15; a.userData.handY = -(0.6 + 0.12 * 1.1); body.add(a); return a; });
  const legs = [-1, 1].map(s => { const l = limb(0.15, 0.25, m, new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.14, 0.42), dark)); l.position.set(s * 0.3, 0.62, 0); root.add(l); return l; });
  return finish({ root, body, head, eyes, brows, mouth, arms, legs, browY: 0.22, mouthBase: 0.25, headY: 2.1, top: 2.6, robot: true,
                  headR: 0.48, torso: { y: 1.15, r: 0.55, h: 1.1 }, hipY: 0.62, neckY: 1.72, legLen: 0.25, legR: 0.15, armR: 0.12 });
}

function buildCritter(d) {
  const { root, body } = rigBase();
  const m = mat(d.body || 0xf4f1ea, 0.6), acc = mat(d.accent || 0x2c4a2a, 0.7), dark = mat(0x2a180e, 0.35);
  const head = new THREE.Group(); head.position.set(0, 1.05, 0); body.add(head);
  head.add(sph(0.85, m, 0, 0, 0, 1, 0.95, 0.9));
  if (d.band !== false) { const b = new THREE.Mesh(new THREE.CylinderGeometry(0.66, 0.72, 0.5, 28, 1, true), acc); b.position.y = -0.48; head.add(b); }
  if (d.ears) for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.34, 10), m); e.position.set(s * 0.45, 0.78, 0); e.rotation.z = -s * 0.3; head.add(e); }
  const eyes = [eye(-0.27, 0.15, 0.7, 0.14), eye(0.27, 0.15, 0.7, 0.14)]; eyes.forEach(e => head.add(e));
  const brows = [brow(-0.27, 0.38, 0.74, 0.14, dark, -1), brow(0.27, 0.38, 0.74, 0.14, dark, 1)]; brows.forEach(b => head.add(b));
  for (const s of [-1, 1]) head.add(sph(0.1, mat(0xff8f8f, 0.6), s * 0.48, -0.08, 0.6, 1, 0.6, 0.4));
  const mouth = sph(0.09, mat(0x7a2a22, 0.5), 0, -0.16, 0.76, 1.5, 0.12, 0.6); head.add(mouth);
  const arms = [-1, 1].map(s => { const a = limb(0.09, 0.28, m); a.position.set(s * 0.8, 1.0, 0.1); a.userData.rest = s * 0.5; a.userData.handY = -(0.28 + 0.09 * 1.1); body.add(a); return a; });
  const legs = [-1, 1].map(s => { const l = limb(0.1, 0.12, m, sph(0.13, dark, 0, 0, 0.05, 1, 0.6, 1.3)); l.position.set(s * 0.32, 0.3, 0); root.add(l); return l; });
  return finish({ root, body, head, eyes, brows, mouth, arms, legs, browY: 0.38, mouthBase: 0.12, headY: 1.05, top: 1.9,
                  headR: 0.85, torso: { y: 0.95, r: 0.78, h: 0.8 }, hipY: 0.3, neckY: 1.15, legLen: 0.12, legR: 0.1, armR: 0.09 });
}

function buildCharacter(d) {
  const c = d.type === "human" ? buildHuman(d) : d.type === "robot" ? buildRobot(d) : (d.type === "critter" || d.type === "blob") ? buildCritter(d) : buildAnimal(d);
  applyParts(c, d);   // costumes, features, held item, pose, effect (parts.js)
  const s = d.scale || 1;
  c.root.scale.setScalar(s); c.scale = s;
  return c;
}

// ====================================================================== worlds
function skyTexture(top, mid, bottom) {
  const cv = document.createElement("canvas"); cv.width = 4; cv.height = 512;
  const g = cv.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, top); gr.addColorStop(0.55, mid); gr.addColorStop(1, bottom);
  g.fillStyle = gr; g.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const MOODS = {
  day:    { sky: ["#5aa8f0", "#a9d6ff", "#ffe6bf"], fog: 0xe9e2c8, hemi: [0xdfefff, 0x6b5a2e, 1.15], sun: [0xffe2b8, 2.8], sunPos: [-7, 13, 9], exp: 1.05 },
  sunset: { sky: ["#3f4f9a", "#f08a5d", "#ffd39a"], fog: 0xf0b48a, hemi: [0xffd2b0, 0x5a3a2e, 1.0], sun: [0xffa860, 2.6], sunPos: [-12, 5, 6], exp: 1.0 },
  night:  { sky: ["#0b1233", "#22306a", "#46508a"], fog: 0x1f2a55, hemi: [0x8fa4ff, 0x1c2238, 1.1], sun: [0xb8c8ff, 2.0], sunPos: [6, 12, 7], exp: 1.45 },
  dark:   { sky: ["#10131c", "#262c3e", "#4a5064"], fog: 0x2a3040, hemi: [0x9aa8c4, 0x18181c, 0.95], sun: [0xc8d4ec, 1.7], sunPos: [5, 10, 6], exp: 1.45 },
  space:  { sky: ["#000004", "#0a0628", "#26103a"], fog: 0x1a0d2e, hemi: [0xb0a0ff, 0x201030, 0.7], sun: [0xffffff, 2.2], sunPos: [-6, 9, 8], exp: 1.05 },
};

function buildWorld(scene, w, seed) {
  const R = rng(seed || 7);
  const preset = w.preset || "forest_green";
  const kit = KITS[preset];   // the set kits (sets.js); the older worlds below stay as they were
  // light from the time of day (dawn … midnight) and the weather; horror "dark" and space keep their own looks
  const useTime = w.time && TIMES[w.time] && !["dark", "space"].includes(w.mood);
  const mood = weatherize(useTime ? TIMES[w.time] : (MOODS[w.mood] || MOODS.day), w.weather || "clear");
  const indoor = preset === "room" || !!(kit && kit.indoor);
  scene.background = skyTexture(...mood.sky);
  scene.fog = new THREE.Fog(mood.fog, indoor ? 30 : (mood.fogNear ?? (w.mood === "dark" ? 10 : 22)), indoor ? 80 : (mood.fogFar ?? (w.mood === "dark" ? 38 : 70)));
  scene.add(new THREE.HemisphereLight(mood.hemi[0], mood.hemi[1], mood.hemi[2]));
  const sun = new THREE.DirectionalLight(mood.sun[0], mood.sun[1]);
  sun.position.set(...mood.sunPos); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.radius = 4;
  Object.assign(sun.shadow.camera, { left: -14, right: 14, top: 14, bottom: -14, near: 1, far: 60 });
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, w.mood === "night" || w.mood === "dark" ? 0.5 : 0.35); fill.position.set(4, 4, 12); scene.add(fill);
  const particles = [];
  const addParticles = (n, colors, kind) => {
    const geo = kind === "snow" ? new THREE.SphereGeometry(0.035, 6, 4) : kind === "firefly" ? new THREE.SphereGeometry(0.03, 6, 4) : new THREE.PlaneGeometry(0.14, 0.1);
    for (let i = 0; i < n; i++) {
      const m = kind === "firefly" ? new THREE.MeshBasicMaterial({ color: 0xfff27a }) : kind === "snow" ? new THREE.MeshBasicMaterial({ color: 0xffffff }) :
        mat(colors[i % colors.length], 0.8, { side: THREE.DoubleSide });
      const p = new THREE.Mesh(geo, m);
      p.userData = { kind, x: (R() - 0.5) * 24, z: (R() - 0.5) * 12 - 2, y0: R() * 7, sp: 0.3 + R() * 0.5, ph: R() * 6 };
      scene.add(p); particles.push(p);
    }
  };
  const groundColor = (kit && kit.ground) || { forest_autumn: 0x8aab4a, forest_green: 0x6fae4a, village: 0x8fb35a, beach: 0xf0d9a0, snow: 0xf4f7fb, stadium: 0x5aa63f,
                        night: 0x2c4a33, room: 0xb07a4a, space: 0x6c4a8a, farm: 0x86b04c }[preset] || 0x6fae4a;
  if (!indoor) {
    const ground = new THREE.Mesh(new THREE.CircleGeometry(95, 64), mat(groundColor, 0.95));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  }
  const keepClear = (x, z) => Math.abs(x) < 7 && z > -4.5 && z < 6;
  const tree = (x, z, s, palette, pine = false) => {
    const t = new THREE.Group();
    if (pine) {
      const tr = new THREE.Mesh(new THREE.CylinderGeometry(0.14 * s, 0.2 * s, 0.9 * s, 10), mat(0x5a3a22, 0.9)); tr.position.y = 0.45 * s; t.add(tr);
      for (let k = 0; k < 3; k++) { const c = new THREE.Mesh(new THREE.ConeGeometry((1.2 - k * 0.3) * s, 1.3 * s, 14), mat(palette[k % palette.length], 0.85)); c.position.y = (1.3 + k * 0.75) * s; t.add(c); }
      if (preset === "snow") { const sc = new THREE.Mesh(new THREE.ConeGeometry(0.55 * s, 0.5 * s, 14), mat(0xffffff, 0.8)); sc.position.y = 3.05 * s; t.add(sc); }
    } else {
      const tr = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.26 * s, 2.2 * s, 12), mat(0x6e4224, 0.9)); tr.position.y = 1.1 * s; t.add(tr);
      const c0 = palette[Math.floor(R() * palette.length)];
      for (let k = 0; k < 4; k++) { const c = sph((0.8 + R() * 0.5) * s, mat(c0, 0.8), (R() - 0.5) * 1.1 * s, (2.6 + R() * 0.9) * s, (R() - 0.5) * 1.0 * s); t.add(c); }
    }
    t.position.set(x, 0, z); t.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); scene.add(t);
  };
  const forest = (palette, n = 55, pine = false) => {
    for (let i = 0; i < n; i++) { const x = (R() - 0.5) * 60, z = -5 - R() * 35; if (!keepClear(x, z)) tree(x, z, 0.8 + R() * 0.7, palette, pine); }
    for (const [x, z, s] of [[-7, -3, 1.1], [6.5, -3.5, 1.2], [9.5, 1.5, 1.0], [-10, 1.2, 0.9]]) tree(x, z, s, palette, pine);
  };
  const tufts = (n, c = 0x4f8f34) => { for (let i = 0; i < n; i++) { const g = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.32, 5), mat(c, 0.9)); g.position.set((R() - 0.5) * 26, 0.15, (R() - 0.5) * 12 - 1); g.rotation.z = (R() - 0.5) * 0.4; scene.add(g); } };
  const rocks = n => { for (let i = 0; i < n; i++) { const r = new THREE.Mesh(new THREE.DodecahedronGeometry(0.25 + R() * 0.3), mat(0x9a9488, 0.9)); r.position.set((R() - 0.5) * 18, 0.1, (R() - 0.5) * 6 - 2); r.castShadow = r.receiveShadow = true; scene.add(r); } };
  const flowers = n => { for (let i = 0; i < n; i++) { const f = sph(0.08, mat([0xff5c8a, 0xffd23f, 0xffffff, 0xb57bff][i % 4], 0.6), (R() - 0.5) * 20, 0.12, (R() - 0.5) * 10 - 1); scene.add(f); } };
  const mushrooms = n => { for (let i = 0; i < n; i++) { const m = new THREE.Group(); const st = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.07, 0.22, 10), mat(0xf5ecd8)); st.position.y = 0.11; const cp = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), mat(0xd23a2e, 0.5)); cp.position.y = 0.2; m.add(st, cp); m.position.set((R() - 0.5) * 14, 0, (R() - 0.2) * 4); m.traverse(o => { if (o.isMesh) o.castShadow = true; }); scene.add(m); } };
  const hills = c => { for (let i = 0; i < 7; i++) { const h = sph(9 + R() * 6, mat(c, 1), -40 + i * 13, -5, -42 - R() * 8, 1, 0.6, 1); h.castShadow = false; scene.add(h); } };
  const house = (x, z, rot, wall, roof) => {
    const g = new THREE.Group();
    const b = new THREE.Mesh(new THREE.BoxGeometry(2.6, 2, 2.2), mat(wall, 0.85)); b.position.y = 1; g.add(b);
    const r = new THREE.Mesh(new THREE.ConeGeometry(2.1, 1.3, 4), mat(roof, 0.7)); r.position.y = 2.65; r.rotation.y = Math.PI / 4; g.add(r);
    const door = new THREE.Mesh(new THREE.BoxGeometry(0.6, 1.1, 0.05), mat(0x6e4224, 0.7)); door.position.set(0, 0.55, 1.11); g.add(door);
    for (const s of [-1, 1]) { const wdw = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.05), mat(0x9fd3ff, 0.2)); wdw.position.set(s * 0.85, 1.25, 1.11); g.add(wdw); }
    g.position.set(x, 0, z); g.rotation.y = rot; g.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; } }); scene.add(g);
  };

  const K = { scene, R, mat, sph, w, tree, forest, tufts, rocks, flowers, mushrooms, hills, house, addParticles, keepClear };
  if (kit) {
    kit.build(K);
  } else if (preset === "forest_autumn" || preset === "forest_green" || preset === "night" || preset === "farm") {
    const pal = preset === "forest_autumn" ? [0xe8742c, 0xf2a23a, 0xd8542b, 0xf0c24a, 0x6fa33f]
      : preset === "night" ? [0x1f3d2a, 0x24452f, 0x2f5a3a] : [0x4f9a3a, 0x6cb648, 0x3f8a34, 0x8cc35a];
    hills(preset === "night" ? 0x1e3326 : 0x9bbf63);
    forest(pal, preset === "farm" ? 25 : 55);
    tufts(preset === "night" ? 90 : 160, preset === "night" ? 0x2a5a30 : 0x4f8f34);
    rocks(8); mushrooms(preset === "night" ? 4 : 9);
    if (preset !== "night") flowers(20);
    if (preset === "farm") { house(-8, -6, 0.4, 0xc0392b, 0x6e2c1f); for (let i = -6; i <= 6; i++) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.9, 0.1), mat(0xd9b98a)); p.position.set(i * 1.2, 0.45, -4.6); scene.add(p); } const rail = new THREE.Mesh(new THREE.BoxGeometry(14.6, 0.08, 0.06), mat(0xd9b98a)); rail.position.set(0, 0.7, -4.6); scene.add(rail); }
    const log = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.36, 2.6, 18), mat(0x7a4b28, 0.9)); log.rotation.z = Math.PI / 2; log.rotation.y = 0.35; log.position.set(4.6, 0.32, -2.2); log.castShadow = true; scene.add(log);
    if (preset === "forest_autumn") addParticles(140, [0xe8742c, 0xf2a23a, 0xd8542b, 0xf0c24a], "leaf");
    if (preset === "forest_green" || preset === "farm") addParticles(40, [0x9fdc6a, 0xc8f08a], "leaf");
    if (preset === "night") {
      addParticles(60, [], "firefly");
      const moon = sph(2.2, new THREE.MeshBasicMaterial({ color: 0xfff6d8 }), -18, 22, -60); moon.castShadow = false; scene.add(moon);
    }
  } else if (preset === "stadium") {
    // a cricket ground: mown field, pitch with stumps, boundary rope, stands full of people, floodlights
    for (let k = 0; k < 7; k++) { const ring = new THREE.Mesh(new THREE.RingGeometry(4 + k * 4, 6 + k * 4, 64), mat(k % 2 ? 0x5aa63f : 0x67b84a, 0.95)); ring.rotation.x = -Math.PI / 2; ring.position.y = 0.006; ring.receiveShadow = true; scene.add(ring); }
    const pitch = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 18), mat(0xcdb98a, 1)); pitch.rotation.x = -Math.PI / 2; pitch.position.set(0, 0.014, -11); pitch.receiveShadow = true; scene.add(pitch);
    for (const z of [-3.2, -18.8]) {
      const crease = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 0.06), mat(0xffffff, 0.6)); crease.rotation.x = -Math.PI / 2; crease.position.set(0, 0.02, z + (z > -10 ? -1.2 : 1.2)); scene.add(crease);
      for (const x of [-0.2, 0, 0.2]) { const st = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.72, 8), mat(0xf4e9c8, 0.5)); st.position.set(x, 0.36, z); st.castShadow = true; scene.add(st); }
      const bail = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.03, 0.04), mat(0xf4e9c8, 0.5)); bail.position.set(0, 0.73, z); scene.add(bail);
    }
    const rope = new THREE.Mesh(new THREE.TorusGeometry(30, 0.08, 6, 96), mat(0xffffff, 0.6)); rope.rotation.x = Math.PI / 2; rope.position.y = 0.08; scene.add(rope);
    const crowdM = [0x2f7fe0, 0xd8343c, 0xf2c12e, 0xffffff, 0x1d4fa0, 0xff8a1f, 0x3f9a3a].map(c => mat(c, 0.8));
    for (let tier = 0; tier < 4; tier++) {
      const r0 = 34 + tier * 2.4, h = 0.9 + tier * 1.4;
      const step = new THREE.Mesh(new THREE.CylinderGeometry(r0 + 2.4, r0 + 2.4, 1.2, 64, 1, true, Math.PI * 0.05, Math.PI * 1.9), mat(0x8a94a6, 0.9, { side: THREE.DoubleSide })); step.position.y = h - 0.6; scene.add(step);
      for (let k = 0; k < 120; k++) { const a = Math.PI * (0.55 + 0.9 * (k / 120)) + Math.PI * 0.5, rr = r0 + 1.2 + (R() - 0.5) * 1.2; const fan = sph(0.32, crowdM[(k + tier) % crowdM.length], Math.cos(a) * rr, h + 0.3, Math.sin(a) * rr * -1, 1, 1.3, 1); fan.castShadow = false; fan.position.z = -Math.abs(fan.position.z); scene.add(fan); }
    }
    const pav = new THREE.Group(); pav.add(new THREE.Mesh(new THREE.BoxGeometry(14, 6, 4), mat(0xb7553a, 0.8))); const proof = new THREE.Mesh(new THREE.BoxGeometry(15, 0.5, 4.6), mat(0x3a4a5a, 0.7)); proof.position.y = 3.2; pav.add(proof);
    for (let k = -2; k <= 2; k++) { const win = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.4), mat(0xf3e3c3, 0.4)); win.position.set(k * 2.6, 0.6, 2.01); pav.add(win); }
    pav.position.set(0, 3, -46); scene.add(pav);
    for (const [x, z] of [[-30, -30], [30, -30], [-38, 4], [38, 4]]) {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.45, 22, 10), mat(0x9aa4b4, 0.5)); pole.position.set(x, 11, z); scene.add(pole);
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(4, 2.2, 0.5), new THREE.MeshBasicMaterial({ color: 0xfffbe0 })); lamp.position.set(x, 22.5, z); lamp.lookAt(0, 0, 0); scene.add(lamp);
    }
  } else if (preset === "village") {
    hills(0x9bbf63);
    const walls = [0xf3d7a6, 0xf0b9a0, 0xd9e7f5, 0xfff1c9], roofs = [0xc0392b, 0x8e4a2c, 0x2e6fb0, 0xd35400];
    [[-9, -6, 0.3], [-4, -9, 0.1], [3.5, -9.5, -0.1], [9, -6, -0.35], [-14, -2, 0.7], [14, -2, -0.7]].forEach(([x, z, r], i) => house(x, z, r, walls[i % 4], roofs[i % 4]));
    forest([0x4f9a3a, 0x6cb648, 0xe8a23a], 30);
    const path = new THREE.Mesh(new THREE.PlaneGeometry(3, 40), mat(0xd9c08a, 1)); path.rotation.x = -Math.PI / 2; path.position.set(0, 0.012, -10); path.receiveShadow = true; scene.add(path);
    const well = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.8, 18), mat(0x9a9488, 0.9)); well.position.set(-5, 0.4, -2.5); well.castShadow = true; scene.add(well);
    tufts(80); flowers(30); addParticles(25, [0xffffff, 0xfff0a0], "leaf");
  } else if (preset === "beach") {
    const sea = new THREE.Mesh(new THREE.PlaneGeometry(200, 60), mat(0x2fa7d6, 0.25, { metalness: 0.1 })); sea.rotation.x = -Math.PI / 2; sea.position.set(0, 0.03, -38); sea.userData.sea = true; scene.add(sea);
    const foam = new THREE.Mesh(new THREE.PlaneGeometry(200, 1.2), mat(0xffffff, 0.6)); foam.rotation.x = -Math.PI / 2; foam.position.set(0, 0.04, -8.4); foam.userData.foam = true; scene.add(foam);
    for (const [x, z, s] of [[-8, -3, 1.2], [8.5, -4, 1.1], [-12, 0, 1.0], [12, 1, 1.3]]) {
      const g = new THREE.Group();
      for (let k = 0; k < 6; k++) { const seg = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 0.6, 10), mat(0x9a6a3a, 0.9)); seg.position.set(k * 0.07, 0.3 + k * 0.55, 0); g.add(seg); }
      for (let k = 0; k < 7; k++) { const lf = sph(0.9, mat(0x3f9a3a, 0.7), 0.4, 3.5, 0, 1.3, 0.12, 0.38); lf.rotation.y = (k / 7) * Math.PI * 2; lf.position.set(0.4 + Math.cos((k / 7) * Math.PI * 2) * 0.8, 3.35, Math.sin((k / 7) * Math.PI * 2) * 0.8); g.add(lf); }
      g.position.set(x, 0, z); g.scale.setScalar(s); g.traverse(o => { if (o.isMesh) o.castShadow = true; }); scene.add(g);
    }
    for (let i = 0; i < 10; i++) { const sh = sph(0.1, mat([0xffc2d1, 0xffffff, 0xf2d0a0][i % 3], 0.5), (R() - 0.5) * 18, 0.05, (R() - 0.5) * 8, 1, 0.5, 1); scene.add(sh); }
    rocks(5);
  } else if (preset === "snow") {
    hills(0xe9eef5);
    forest([0x2f6b46, 0x3a7a52], 50, true);
    rocks(6);
    const sm = new THREE.Group(); sm.add(sph(0.6, mat(0xffffff, 0.8), 0, 0.55, 0)); sm.add(sph(0.42, mat(0xffffff, 0.8), 0, 1.4, 0)); sm.add(sph(0.3, mat(0xffffff, 0.8), 0, 2.05, 0));
    const nose = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.3, 10), mat(0xff8a1f, 0.5)); nose.rotation.x = Math.PI / 2; nose.position.set(0, 2.05, 0.38); sm.add(nose);
    sm.position.set(-5.5, 0, -2.5); sm.traverse(o => { if (o.isMesh) o.castShadow = true; }); scene.add(sm);
    addParticles(220, [], "snow");
  } else if (preset === "space") {
    for (let i = 0; i < 300; i++) { const s = sph(0.08 + R() * 0.1, new THREE.MeshBasicMaterial({ color: 0xffffff }), (R() - 0.5) * 160, 5 + R() * 60, -60 - R() * 30); s.castShadow = false; scene.add(s); }
    const planet = sph(9, mat(0xf08a5d, 0.7), 26, 20, -70); planet.castShadow = false; scene.add(planet);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(13, 0.6, 8, 60), mat(0xffd39a, 0.6)); ring.position.copy(planet.position); ring.rotation.x = 1.2; scene.add(ring);
    for (let i = 0; i < 18; i++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.9 + R() * 1.4, 1.2 + R() * 1.6, 0.25, 18, 1, true), mat(0x4e3468, 0.9)); c.position.set((R() - 0.5) * 50, 0.08, -6 - R() * 30); scene.add(c); }
    rocks(10);
    const rocket = new THREE.Group(); const b = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.7, 3.2, 20), mat(0xf4f4f4, 0.4)); b.position.y = 2.1; rocket.add(b);
    const n = new THREE.Mesh(new THREE.ConeGeometry(0.6, 1.2, 20), mat(0xe74c3c, 0.4)); n.position.y = 4.3; rocket.add(n);
    for (let k = 0; k < 3; k++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.1, 1, 0.8), mat(0xe74c3c, 0.4)); f.position.set(Math.cos(k * 2.1) * 0.65, 0.8, Math.sin(k * 2.1) * 0.65); f.rotation.y = -k * 2.1; rocket.add(f); }
    rocket.position.set(-7.5, 0, -4); rocket.traverse(o => { if (o.isMesh) o.castShadow = true; }); scene.add(rocket);
    addParticles(50, [], "firefly");
  } else if (indoor) {
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), mat(0xb07a4a, 0.8)); floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
    const wallM = mat(w.wall || 0xf3e3c3, 0.95);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(30, 9), wallM); back.position.set(0, 4.5, -5); back.receiveShadow = true; scene.add(back);
    for (const s of [-1, 1]) { const side = new THREE.Mesh(new THREE.PlaneGeometry(20, 9), wallM); side.position.set(s * 11, 4.5, 3); side.rotation.y = -s * Math.PI / 2; scene.add(side); }
    const win = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.2), new THREE.MeshBasicMaterial({ color: w.mood === "night" ? 0x1b2650 : 0x9fd3ff })); win.position.set(-3.5, 3.6, -4.98); scene.add(win);
    const frame = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.12, 0.1), mat(0xffffff)); frame.position.set(-3.5, 3.6, -4.9); scene.add(frame);
    const rug = new THREE.Mesh(new THREE.CircleGeometry(3.2, 40), mat(0xd8543b, 0.9)); rug.rotation.x = -Math.PI / 2; rug.position.set(0, 0.01, 0.5); rug.receiveShadow = true; scene.add(rug);
    const sofa = new THREE.Group(); const seat = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.6, 1.2), mat(0x2f7fe0, 0.8)); seat.position.y = 0.5; sofa.add(seat);
    const backr = new THREE.Mesh(new THREE.BoxGeometry(3.6, 1.0, 0.35), mat(0x2f7fe0, 0.8)); backr.position.set(0, 1.1, -0.45); sofa.add(backr);
    sofa.position.set(4.5, 0, -3.6); sofa.traverse(o => { if (o.isMesh) { o.castShadow = o.receiveShadow = true; } }); scene.add(sofa);
    const table = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 0.08, 24), mat(0x7a4b28, 0.6)); table.position.set(-4.5, 1.0, -2.5); table.castShadow = true; scene.add(table);
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 1, 10), mat(0x7a4b28, 0.6)); leg.position.set(-4.5, 0.5, -2.5); scene.add(leg);
    const lamp = new THREE.PointLight(0xffd8a0, 1.2, 14); lamp.position.set(-4.5, 3.2, -2); scene.add(lamp);
    for (let i = 0; i < 3; i++) { const pic = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.8), mat([0xf2a23a, 0x6cb648, 0xb57bff][i], 0.6)); pic.position.set(1.5 + i * 1.6, 3.6, -4.97); scene.add(pic); }
  }
  if (!indoor && preset !== "space") buildSky(K, mood);   // clouds, sun or moon, stars (sets.js)
  return { particles, sun, preset, exp: mood.exp };
}

function updateWorld(world, t) {
  for (const p of world.particles) {
    const d = p.userData;
    if (d.kind === "firefly") {
      p.position.set(d.x + Math.sin(t * 0.6 + d.ph) * 1.2, 0.6 + (d.y0 % 3) + Math.sin(t * 0.9 + d.ph) * 0.4, d.z + Math.cos(t * 0.5 + d.ph) * 0.8);
      p.visible = Math.sin(t * 2 + d.ph * 3) > -0.3;
    } else {
      const y = 7 - ((d.y0 + t * d.sp * (d.kind === "snow" ? 0.8 : 1)) % 7);
      p.position.set(d.x + Math.sin(t * 0.9 + d.ph) * 0.6, y, d.z + Math.cos(t * 0.7 + d.ph) * 0.3);
      if (d.kind === "leaf") p.rotation.set(t * 2 + d.ph, t * 1.3, t * 1.7 + d.ph);
    }
  }
}

// ====================================================================== performance (actions, faces, camera)
function blinkAmt(t, seed) { const period = 2.7 + seed * 0.9, ph = (t + seed * 1.3) % period; return ph < 0.14 ? 0.05 + 0.95 * Math.abs(ph - 0.07) / 0.07 : 1; }

let S = null;   // the live scene

window.setup = async (spec) => {
  matCache.clear();
  const W = spec.w || 1920, H = spec.h || 1080;
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
  document.body.innerHTML = ""; document.body.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const world = buildWorld(scene, spec.world || {}, (spec.world && spec.world.seed) || spec.seed || 1);   // a named place keeps its layout
  renderer.toneMappingExposure = world.exp || (MOODS[(spec.world || {}).mood] || MOODS.day).exp;
  const cast = {};
  (spec.cast || []).forEach((c, i) => {
    const ch = buildCharacter(c.design || {});
    ch.id = c.id; ch.x = c.x; ch.z = c.z || 0; ch.restYaw = c.yaw || 0; ch.enter = c.enter || null; ch.seed = 0.2 + i * 0.7;
    ch.root.position.set(ch.x, 0, ch.z);
    if (c.night_rim) {   // moonlit rim from behind + a soft key from the front, so faces read in the dark
      const rim = new THREE.PointLight(0xa8c0ff, 6, 7, 1.6); rim.position.set(0, 3.2, -1.6); ch.root.add(rim);
      const key = new THREE.PointLight(0xffe2c0, 3.5, 7, 1.6); key.position.set(0.8, 2.4, 2.6); ch.root.add(key);
    }
    scene.add(ch.root); cast[c.id] = ch;
  });
  const camera = new THREE.PerspectiveCamera(spec.fov || 36, W / H, 0.1, 300);
  const story = buildStory(scene, spec, cast);   // what the narration talks about (story.js)
  S = { spec, renderer, scene, world, cast, camera, W, H, story };
  renderer.render(scene, camera);
  return { ok: true, gpu: (() => { const gl = renderer.getContext(); const x = gl.getExtension("WEBGL_debug_renderer_info"); return x ? gl.getParameter(x.UNMASKED_RENDERER_WEBGL) : ""; })() };
};

function speaking(t, who) {
  for (const w of S.spec.words || []) if (w.who === who && t >= w.s && t <= w.e) {
    const u = (t - w.s) / Math.max(0.05, w.e - w.s), syl = Math.max(1, Math.round([...w.w].length / 2.4));
    return 0.3 + 0.7 * Math.abs(Math.sin(Math.PI * syl * u));
  }
  return 0;
}
const active = (t, who, type) => (S.spec.actions || []).find(a => a.who === who && a.type === type && t >= a.t0 && t <= a.t1);
const emotionAt = (t, who) => { const e = (S.spec.emotions || []).find(a => a.who === who && t >= a.t0 && t <= a.t1); return e ? e.emo : ""; };
const speakerAt = t => { const l = (S.spec.lines || []).find(l => t >= l.s - 0.05 && t <= l.e + 0.2); return l ? l.who : null; };

function resetPose(c) {
  c.body.position.set(0, 0, 0); c.body.rotation.set(c.robot ? 0 : c.body.rotation.x * 0, 0, 0); c.head.rotation.set(0, 0, 0);
  c.arms.forEach(a => a.rotation.set(0, 0, a.userData.rest)); c.legs.forEach(l => l.rotation.set(0, 0, 0));
  c.root.position.y = 0; c.body.scale.set(1, 1, 1);
}
function walkPose(c, ph, amt) {
  c.legs[0].rotation.x = Math.sin(ph) * 0.75 * amt; c.legs[1].rotation.x = -Math.sin(ph) * 0.75 * amt;
  c.arms[0].rotation.x = -Math.sin(ph) * 0.7 * amt; c.arms[1].rotation.x = Math.sin(ph) * 0.7 * amt;
  c.body.position.y = Math.abs(Math.sin(ph)) * 0.07 * amt; c.body.rotation.z = Math.sin(ph) * 0.05 * amt;
}
function faceFor(c, t, emo) {
  const open = speaking(t, c.id);
  const sur = emo === "surprised" || emo === "scared", happy = emo === "happy" || emo === "excited", sad = emo === "sad", angry = emo === "angry";
  const s = sur ? 1.22 : sad ? 0.9 : 1, b = blinkAmt(t, c.seed);
  c.eyes.forEach(e => e.scale.set(s, s * (angry ? 0.75 : 1) * b, s));
  c.brows.forEach(br => {
    const side = br.userData.side || 1;
    br.position.y = c.browY + (sur ? 0.07 : happy ? 0.03 : sad ? 0.01 : angry ? -0.03 : 0);
    if (!c.robot) br.rotation.z = Math.PI / 2 + side * (sur ? 0.2 : sad ? -0.3 : angry ? 0.35 : 0.08);
  });
  const o = sur ? Math.max(open, 0.5) : open;
  if (c.robot) c.mouth.scale.set(happy ? 1.2 : 1, c.mouthBase + o * 1.6, 1);
  else c.mouth.scale.set(sur ? 0.9 : happy && !open ? 1.8 : 1.5 - o * 0.4, c.mouthBase + o * 0.95, 0.6);
  return open;
}
function yawTo(c, x, z) { return Math.atan2(x - c.root.position.x, z - c.root.position.z); }

function animateCharacter(c, t) {
  resetPose(c);
  const emo = emotionAt(t, c.id), spk = speakerAt(t);
  // where, and which way it faces
  let yaw = c.restYaw;
  if (c.enter && t < c.enter.t1) {
    const u = clamp01((t - c.enter.t0) / (c.enter.t1 - c.enter.t0));
    c.root.position.x = lerp(c.enter.from_x, c.x, ease(u));
    if (t >= c.enter.t0) { walkPose(c, t * 11, u < 0.88 ? 1 : (1 - u) / 0.12); yaw = c.enter.from_x < c.x ? Math.PI / 2 : -Math.PI / 2; }
    else { c.root.visible = false; }
  } else {
    c.root.visible = true; c.root.position.x = c.x;
    if (c.enter) { const u = clamp01((t - c.enter.t1) / 0.45); yaw = lerp(c.enter.from_x < c.x ? Math.PI / 2 : -Math.PI / 2, c.restYaw, ease(u)); }
  }
  if (c.enter && t >= c.enter.t0) c.root.visible = true;
  c.root.rotation.y = yaw;
  c.body.scale.y = 1 + Math.sin(t * 2.2 + c.seed) * 0.012;   // breathing
  const open = faceFor(c, t, emo);
  // listening: look at the speaker
  if (spk && spk !== c.id && S.cast[spk]) {
    const o = S.cast[spk]; const want = yawTo(c, o.root.position.x, o.root.position.z) - c.root.rotation.y;
    c.head.rotation.y = Math.max(-0.6, Math.min(0.6, want));
  }
  // talking: nod and gesture
  if (spk === c.id) {
    c.head.rotation.x = Math.sin(t * 7) * 0.05 * (open > 0 ? 1 : 0.3);
    c.arms[0].rotation.x = -0.35 + Math.sin(t * 4.5 + c.seed) * 0.25;
    c.arms[1].rotation.x = -0.15 + Math.sin(t * 3.7 + 1) * 0.12;
    c.body.rotation.x = 0.04;
  }
  let a;
  if ((a = active(t, c.id, "wave"))) { const u = t - a.t0; c.arms[1].rotation.z = 2.5 + Math.sin(u * 11) * 0.35; c.arms[1].rotation.x = 0; }
  if ((a = active(t, c.id, "jump"))) { const jt = (t - a.t0) % 0.62; c.root.position.y = Math.max(0, Math.sin(Math.PI * jt / 0.5)) * 0.45; c.arms[0].rotation.z = -2.4; c.arms[1].rotation.z = 2.4; }
  if ((a = active(t, c.id, "bounce"))) { c.root.position.y = Math.abs(Math.sin((t - a.t0) * 7)) * 0.12; }
  if ((a = active(t, c.id, "nod"))) { c.head.rotation.x = Math.sin((t - a.t0) * 9) * 0.16; }
  if ((a = active(t, c.id, "point"))) { c.arms[1].rotation.x = -1.45; c.arms[1].rotation.z = 0.15; }
  if ((a = active(t, c.id, "look_around"))) { c.head.rotation.y = Math.sin((t - a.t0) * 1.8) * 0.6; }
  if ((a = active(t, c.id, "dance"))) { const u = t - a.t0; c.body.rotation.z = Math.sin(u * 6) * 0.15; c.arms[0].rotation.z = -1.6 + Math.sin(u * 6) * 0.6; c.arms[1].rotation.z = 1.6 + Math.sin(u * 6) * 0.6; c.root.position.y = Math.abs(Math.sin(u * 6)) * 0.1; }
  if ((a = active(t, c.id, "think"))) { c.arms[1].rotation.x = -2.2; c.arms[1].rotation.z = 0.6; c.head.rotation.z = 0.12; }
  if ((a = active(t, c.id, "shrug"))) { c.arms[0].rotation.z = -0.9; c.arms[1].rotation.z = 0.9; c.body.position.y += 0.03; }
  if (emo === "sad") { c.head.rotation.x = 0.28; c.body.rotation.x = 0.08; }
  if (emo === "angry") { c.arms[0].rotation.z = -0.55; c.arms[1].rotation.z = 0.55; c.body.rotation.x = 0.1; c.root.position.y += Math.abs(Math.sin(t * 9)) * 0.03; }
  if (emo === "scared") { c.root.position.x += Math.sin(t * 40) * 0.02; c.body.rotation.x = -0.08; c.arms[0].rotation.x = -1.2; c.arms[1].rotation.x = -1.2; }
  if (emo === "surprised" && spk !== c.id) c.body.rotation.x = -0.08;
  animateParts(c, t, (S.spec.actions || []).some(x => x.who === c.id && t >= x.t0 && t <= x.t1));
  const L = storyLook(S.story, t, c);   // looking at what the story shows: a thing, or up at the sky
  if (L) {
    const want = Math.max(-0.9, Math.min(0.9, L.yaw - c.root.rotation.y));
    c.head.rotation.y = lerp(c.head.rotation.y, want, L.u);
    c.head.rotation.x = lerp(c.head.rotation.x, L.pitch, L.u);
    if (L.pitch < -0.3) c.body.rotation.x = lerp(c.body.rotation.x, -0.12, L.u);
  }
}

function headPos(c) { return new THREE.Vector3(c.root.position.x, (c.headY * c.scale) + c.root.position.y, c.root.position.z); }

function placeCamera(t) {
  const cam = S.camera, shots = S.spec.shots || [];
  const sh = shots.find(s => t >= s.t0 && t < s.t1) || shots[shots.length - 1] || { kind: "wide", t0: 0, t1: 1 };
  const u = clamp01((t - sh.t0) / Math.max(0.1, sh.t1 - sh.t0));
  const ids = Object.keys(S.cast).filter(id => S.cast[id].root.visible || (S.cast[id].enter && t >= S.cast[id].enter.t0 - 0.5));
  const chars = (ids.length ? ids : Object.keys(S.cast)).map(id => S.cast[id]);
  const hfov = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * cam.aspect);
  const fitDist = halfW => halfW / Math.tan(hfov / 2);
  if (!chars.length) { cam.position.set(0, 2.5, 9); cam.lookAt(0, 1.5, 0); return; }
  const xs = chars.map(c => c.root.position.x), minX = Math.min(...xs), maxX = Math.max(...xs);
  const cx = (minX + maxX) / 2, topY = Math.max(...chars.map(c => c.top * c.scale));
  if (storyCamera(S.story, sh, u, cam, cx, S.cast)) return;
  const tgt = S.cast[sh.target], oth = S.cast[sh.other];
  if ((sh.kind === "close" || sh.kind === "ots") && tgt) {
    const hp = headPos(tgt);
    const side = oth ? Math.sign(oth.root.position.x - tgt.root.position.x) || 1 : (tgt.root.position.x <= cx ? 1 : -1);
    if (sh.kind === "close") {
      const d = Math.max(2.6, fitDist(1.0 * tgt.scale + 0.4));
      cam.position.set(hp.x + side * d * 0.42 + u * side * 0.15, hp.y + 0.12, hp.z + d * 0.9 - u * 0.35);
      cam.lookAt(hp.x, hp.y - 0.18 * tgt.scale, hp.z);
    } else {
      const op = headPos(oth || tgt);
      cam.position.set(op.x + side * 0.9 + (op.x - hp.x) * 0.35, op.y + 0.25, op.z + 2.6 - u * 0.3);
      cam.lookAt(hp.x, hp.y - 0.15, hp.z);
    }
  } else if (sh.kind === "two" && tgt && oth) {
    const a = headPos(tgt), b = headPos(oth), mx = (a.x + b.x) / 2, half = Math.abs(a.x - b.x) / 2 + 1.4;
    const d = fitDist(half);
    cam.position.set(mx, Math.max(a.y, b.y) * 0.8 + 0.4, d - u * 0.5);
    cam.lookAt(mx, Math.max(a.y, b.y) * 0.62, 0);
  } else {
    const half = (maxX - minX) / 2 + 2.2;
    let d = Math.max(6.5, fitDist(half));
    let y = topY * 0.55 + 1.2, dz = -u * 0.8, dx = 0;
    if (sh.kind === "establish") { d *= 1.35; y += 0.8; dz = -u * 1.6; dx = lerp(-1.2, 0, ease(u)); }
    if (sh.kind === "pull") { dz = u * 3.5; y += u * 1.2; }
    cam.position.set(cx + dx, y, d + dz);
    cam.lookAt(cx, topY * 0.45, 0);
  }
}

window.renderAt = (t) => {
  updateWorld(S.world, t);
  updateStory(S.story, t);   // things first (characters look at them), then again so thought bubbles follow heads
  for (const id in S.cast) animateCharacter(S.cast[id], t);
  updateStory(S.story, t);
  placeCamera(t);
  S.renderer.render(S.scene, S.camera);
  return S.renderer.domElement.toDataURL("image/jpeg", 0.9);
};
window.peakcut3dReady = true;
