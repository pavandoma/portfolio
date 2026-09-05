/**
 * Copy for the cinematic layout. Quiet, expensive, very few words.
 * Everything factual traces back to profile.ts; this file only sets the tone.
 */

export const cinematic = {
  hero: {
    /** Set in caps at display size; the scroll tracks the letters in. */
    name: "Pavan Srinivas",
    role: "AI / ML Engineer",
    cue: "Scroll",
  },

  story: {
    label: "01 — Origin",
    title: "Crafted in darkness.",
    lines: [
      "The parts that make a model trustworthy are the parts nobody sees.",
      "Retrieval that stays relevant. Evaluation that stays honest.",
      "Pipelines that hold.",
    ],
  },

  details: {
    label: "02 — Macro details",
    title: "Measured, not claimed.",
  },

  specs: {
    label: "03 — Specification",
    title: "What it is made of.",
  },

  timeline: {
    label: "04 — Provenance",
    title: "Where it was made.",
  },

  outro: {
    label: "05 — Contact",
    title: "Start a conversation.",
  },
} as const;

/**
 * Split a display figure like "97.5%" or "5" into a tweenable number and its
 * suffix, so the metric can count up under scroll and still print correctly.
 */
export function parseFigure(display: string): {
  value: number;
  decimals: number;
  suffix: string;
} {
  const match = display.match(/^([\d.]+)(.*)$/);
  if (!match) return { value: 0, decimals: 0, suffix: display };
  const [, number, suffix] = match;
  const decimals = number.includes(".") ? number.split(".")[1].length : 0;
  return { value: Number(number), decimals, suffix };
}
