// Pure ACMG point scorer. Sums signed points over accepted selections and maps
// the total onto the five ACMG classes, honouring the BA1 stand-alone override.

import {
  ACMG_CLASS_LABELS,
  ACMG_CRITERIA_BY_CODE,
  STRENGTH_POINTS,
} from './criteria';
import type {
  AcmgClassification,
  AcmgClassKey,
  AcmgSelection,
  AcmgVusTier,
} from './types';

// Signed point value of a single accepted selection.
export function selectionPoints(selection: AcmgSelection): number {
  const def = ACMG_CRITERIA_BY_CODE[selection.code];
  if (!def) return 0;
  const magnitude = STRENGTH_POINTS[selection.strength] ?? 0;
  return def.direction === 'benign' ? -magnitude : magnitude;
}

function classKeyForPoints(points: number): AcmgClassKey {
  if (points >= 10) return 'acmg_class_5';
  if (points >= 6) return 'acmg_class_4';
  if (points >= 0) return 'acmg_class_3';
  if (points >= -6) return 'acmg_class_2';
  return 'acmg_class_1';
}

// MAGI-ACMG VUS sub-tier over the Tavtigian VUS band (points 0–5), by proximity
// to the Likely-Pathogenic threshold (6). Keep these cut-offs in parity with the
// backend (acmg_points.vus_tier_for): 4–5 hot · 2–3 warm · 0–1 cold.
export function vusTierForPoints(points: number, classKey: AcmgClassKey): AcmgVusTier | null {
  if (classKey !== 'acmg_class_3') return null;
  if (points >= 4) return 'hot';
  if (points >= 2) return 'warm';
  return 'cold';
}

export function computeClassification(selections: AcmgSelection[]): AcmgClassification {
  const accepted = selections.filter((selection) => selection.accepted);
  const points = accepted.reduce((sum, selection) => sum + selectionPoints(selection), 0);

  // BA1 (allele frequency ≥ 5%) classifies a variant Benign on its own.
  const standAloneBenign = accepted.some((selection) => selection.code === 'BA1');
  const classKey = standAloneBenign ? 'acmg_class_1' : classKeyForPoints(points);

  return {
    points,
    classKey,
    label: ACMG_CLASS_LABELS[classKey],
    standAloneBenign,
    vusTier: vusTierForPoints(points, classKey),
  };
}
