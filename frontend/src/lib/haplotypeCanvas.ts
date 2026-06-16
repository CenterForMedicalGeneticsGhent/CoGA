/**
 * Mark a haplotype band as an affected/carrier (risk) allele with a thin line along
 * the bottom edge of the band, in the risk colour — minimal and clean. The homolog
 * (P1/P2/M1/M2) fill is left untouched, so origin stays fully readable and the risk
 * allele is flagged unobtrusively, on both the chromosome and whole-genome tracks.
 *
 * Call this *after* the band's base fill has been drawn at (x, y, w, h).
 */
const RISK_LINE_THICKNESS = 1.5;

export const drawHaplotypeRiskOverlay = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string,
): void => {
  ctx.save();
  ctx.fillStyle = color;
  ctx.fillRect(x, y + h - RISK_LINE_THICKNESS, Math.max(w, 0.5), RISK_LINE_THICKNESS);
  ctx.restore();
};
