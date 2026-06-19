// Pure CNV point scorer — mirrors backend/app/services/cnv_acmg_points.py.

import { CNV_CLASS_LABELS, cnvCriterionMap } from './criteria';
import type { CnvClassification, CnvKind, CnvSelection } from './types';

const clampPoints = (kind: CnvKind, code: string, points: number): number => {
  const def = cnvCriterionMap(kind)[code];
  if (!def) return 0;
  return Math.max(def.minPoints, Math.min(def.maxPoints, points));
};

export const classKeyForPoints = (points: number): string => {
  if (points >= 0.99) return 'cnv_class_5';
  if (points >= 0.9) return 'cnv_class_4';
  if (points > -0.9) return 'cnv_class_3';
  if (points > -0.99) return 'cnv_class_2';
  return 'cnv_class_1';
};

export const computeCnvClassification = (
  kind: CnvKind,
  selections: CnvSelection[],
): CnvClassification => {
  const total = selections
    .filter((selection) => selection.accepted)
    .reduce((sum, selection) => sum + clampPoints(kind, selection.code, selection.points), 0);
  const pointTotal = Math.round(total * 100) / 100;
  const classKey = classKeyForPoints(pointTotal);
  return { pointTotal, classKey, classLabel: CNV_CLASS_LABELS[classKey] };
};
