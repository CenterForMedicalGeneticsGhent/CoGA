/**
 * Flag a haplotype band as an affected/carrier (risk) allele *without* hiding its
 * parent-of-origin fill.
 *
 * The risk segment keeps its blue/green homolog fill and gets a clean, solid frame
 * in the risk colour — no diagonal hatching. The saturated risk colour (red for
 * affected, amber for carrier) reads clearly against the muted homolog fills, so
 * origin stays readable and the risk allele is unmistakable, even on a sliver-wide
 * (whole-genome) segment.
 *
 * Call this *after* the band's base fill has been drawn at (x, y, w, h).
 */
export const drawHaplotypeRiskOverlay = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string,
): void => {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  // Inset by half the line width so the frame sits crisply on the band edge.
  ctx.strokeRect(x + 0.75, y + 0.75, Math.max(w - 1.5, 0.5), Math.max(h - 1.5, 0.5));
  ctx.restore();
};
