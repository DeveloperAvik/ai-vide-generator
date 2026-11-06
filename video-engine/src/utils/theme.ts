/** Design system: one place for colour, type and the 8px grid. Legacy keys (bg/panel/fg/muted/accent/warn/sans/mono) are kept
 *  because the 3D components still read them. */
export const T = {
  bg: "#0a0f1c", panel: "#111a2e", surface: "#16213a", border: "#26344f",
  fg: "#e8eef9", muted: "#8a9bb8", dim: "#5b6b88",
  accent: "#3b82f6", cyan: "#22d3ee", warn: "#fbbf24", danger: "#f87171", ok: "#34d399", violet: "#a78bfa",
  sans: "Inter, Helvetica, Arial, sans-serif", mono: "'JetBrains Mono', Menlo, 'DejaVu Sans Mono', monospace",
  // layout grid (1920x1080): captions occupy the bottom ~170px, so content must end at contentBottom
  margin: 96, contentTop: 200, contentBottom: 900, gap: 24, radius: 16,
  shadow: "0 12px 32px rgba(2, 6, 18, 0.45)",
} as const;

/** syntax colours (kept in the same cool palette; no neon) */
export const SYN = { keyword: "#7aa2f7", string: "#9ece6a", number: "#ff9e64", comment: "#5b6b88", fn: "#7dcfff", type: "#bb9af7",
  reg: "#22d3ee", mnemonic: "#fbbf24", addr: "#ff9e64", plain: "#e8eef9" } as const;
