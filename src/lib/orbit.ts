/**
 * Procedural "orbit" — the object the hero scrubs through.
 *
 * A handful of rings, each tilted differently, tumbling as one body. Drawn as
 * thin low-alpha polylines with depth-cued intensity, so it reads as
 * something machined and lit from one side rather than a wireframe demo.
 *
 * Pure function of (progress, size, palette): no state, no time. That is what
 * makes it scrubbable — the same inputs always draw the same frame, forwards
 * or back. The palette is read from the canvas's CSS custom properties on
 * every draw, so a theme change only needs a redraw, not a re-plumb.
 */

export type FrameRenderer = (
  ctx: CanvasRenderingContext2D,
  progress: number,
  width: number,
  height: number,
) => void;

type Rgb = readonly [number, number, number];

type Ring = {
  radius: number;
  tiltX: number;
  tiltZ: number;
  /** Relative intensity, 0–1. One ring is the "lit" one. */
  weight: number;
  segments: number;
};

const RINGS: Ring[] = [
  { radius: 1.0, tiltX: 0.0, tiltZ: 0.0, weight: 1.0, segments: 220 },
  { radius: 0.86, tiltX: 1.05, tiltZ: 0.35, weight: 0.42, segments: 200 },
  { radius: 0.72, tiltX: 0.55, tiltZ: -0.9, weight: 0.34, segments: 180 },
  { radius: 0.58, tiltX: -1.25, tiltZ: 0.6, weight: 0.28, segments: 160 },
  { radius: 0.44, tiltX: 0.3, tiltZ: 1.4, weight: 0.22, segments: 140 },
];

const CAMERA_DISTANCE = 3.2;

/** Fallbacks matching the dark theme, used if a token can't be parsed. */
const FALLBACK_LIT: Rgb = [216, 207, 192];
const FALLBACK_BODY: Rgb = [234, 238, 244];
const FALLBACK_GROUND: Rgb = [0, 0, 0];

function hexToRgb(value: string): Rgb | null {
  const hex = value.trim().replace(/^#/, "");
  const full =
    hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
  if (!/^[0-9a-f]{6}$/i.test(full)) return null;
  const n = Number.parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function readPalette(canvas: HTMLCanvasElement) {
  const style = getComputedStyle(canvas);
  const token = (name: string, fallback: Rgb) =>
    hexToRgb(style.getPropertyValue(name)) ?? fallback;
  return {
    lit: token("--lit", FALLBACK_LIT),
    body: token("--foreground", FALLBACK_BODY),
    ground: token("--background", FALLBACK_GROUND),
  };
}

const rgba = (c: Rgb, alpha: number) =>
  `rgba(${c[0]},${c[1]},${c[2]},${alpha.toFixed(3)})`;

function rotate(
  x: number,
  y: number,
  z: number,
  ax: number,
  ay: number,
  az: number,
): [number, number, number] {
  // X
  let cy = Math.cos(ax),
    sy = Math.sin(ax);
  const y1 = y * cy - z * sy;
  const z1 = y * sy + z * cy;
  // Y
  cy = Math.cos(ay);
  sy = Math.sin(ay);
  const x2 = x * cy + z1 * sy;
  const z2 = -x * sy + z1 * cy;
  // Z
  cy = Math.cos(az);
  sy = Math.sin(az);
  const x3 = x2 * cy - y1 * sy;
  const y3 = x2 * sy + y1 * cy;
  return [x3, y3, z2];
}

export const renderOrbit: FrameRenderer = (ctx, progress, width, height) => {
  const { lit, body, ground } = readPalette(ctx.canvas as HTMLCanvasElement);

  ctx.clearRect(0, 0, width, height);

  const cx = width / 2;
  const cy = height / 2;
  const scale = Math.min(width, height) * 0.33;

  // The tumble. Yaw sweeps a little over half a turn across the scrub; pitch
  // rises and falls so the body never presents the same silhouette twice.
  const yaw = progress * Math.PI * 1.15 - 0.4;
  const pitch = Math.sin(progress * Math.PI) * 0.55 + 0.25;
  const roll = progress * 0.35;

  // Soft key light from upper-left: a large, faint wash in the lit colour.
  // On the dark ground it glows; on the light ground it reads as a shadow.
  const glow = ctx.createRadialGradient(
    cx - scale * 0.6,
    cy - scale * 0.7,
    0,
    cx,
    cy,
    scale * 2.2,
  );
  glow.addColorStop(0, rgba(lit, 0.1));
  glow.addColorStop(0.5, rgba(lit, 0.03));
  glow.addColorStop(1, rgba(lit, 0));
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  for (const ring of RINGS) {
    const colour = ring.weight === 1 ? lit : body;
    let prev: [number, number] | null = null;

    for (let i = 0; i <= ring.segments; i++) {
      const t = (i / ring.segments) * Math.PI * 2;
      const lx = Math.cos(t) * ring.radius;
      const ly = Math.sin(t) * ring.radius;

      // Ring's own tilt, then the whole body's tumble.
      const [tx, ty, tz] = rotate(lx, ly, 0, ring.tiltX, 0, ring.tiltZ);
      const [x, y, z] = rotate(tx, ty, tz, pitch, yaw, roll);

      const depth = CAMERA_DISTANCE / (CAMERA_DISTANCE - z);
      const sx = cx + x * scale * depth;
      const sy = cy + y * scale * depth;
      // Nearer = more intense. Maps z in [-1, 1] to roughly [0.15, 1].
      const lum = 0.15 + ((z + 1) / 2) * 0.85;

      if (prev) {
        ctx.strokeStyle = rgba(colour, ring.weight * lum * 0.9);
        ctx.lineWidth = ring.weight === 1 ? 1.4 * depth : 0.9 * depth;
        ctx.beginPath();
        ctx.moveTo(prev[0], prev[1]);
        ctx.lineTo(sx, sy);
        ctx.stroke();
      }
      prev = [sx, sy];

      // Sparse markers on the lit ring only — like index marks on a bezel.
      if (ring.weight === 1 && i % 20 === 0) {
        ctx.fillStyle = rgba(lit, lum * 0.9);
        ctx.beginPath();
        ctx.arc(sx, sy, 1.6 * depth, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // Vignette so the edges settle into the page ground.
  const vignette = ctx.createRadialGradient(
    cx,
    cy,
    scale * 1.1,
    cx,
    cy,
    Math.max(width, height) * 0.75,
  );
  vignette.addColorStop(0, rgba(ground, 0));
  vignette.addColorStop(1, rgba(ground, 0.85));
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, width, height);
};
