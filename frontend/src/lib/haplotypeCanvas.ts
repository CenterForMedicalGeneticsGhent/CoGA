/**
 * Flag a haplotype band as the disease/risk haplotype *without* hiding its
 * parent-of-origin fill.
 *
 * Previously the risk colour replaced the band fill, which erased the blue/green
 * paternal/maternal origin signal on exactly the segments analysts care about
 * most. Instead we keep the origin fill and overlay a diagonal hatch plus a thin
 * frame in the risk colour: origin stays readable, risk is unmistakable, and the
 * frame keeps even a 1px-wide segment (whole-genome view) legible.
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
  // Diagonal hatch, clipped to the band so lines never bleed into neighbours.
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  const step = 4;
  for (let dx = -h; dx < w; dx += step) {
    ctx.beginPath();
    ctx.moveTo(x + dx, y + h);
    ctx.lineTo(x + dx + h, y);
    ctx.stroke();
  }
  ctx.restore();
  // Frame so a sliver-wide segment still reads as risk once the hatch vanishes.
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, Math.max(w - 1, 0.5), Math.max(h - 1, 0.5));
};
