import { useMemo, useState } from 'react';

import {
  buildInitialCnvSelections,
  cnvCriteriaForKind,
  cnvKindForType,
  CNV_SECTION_TITLES,
  computeCnvClassification,
  evaluateCnv,
  type CnvKind,
  type CnvSelection,
} from '../../lib/cnvAcmg';
import type {
  StructuralVariant,
  StructuralVariantReviewSavePayload,
} from './structuralVariantSearch';

type CnvAcmgClassificationModalProps = {
  variant: StructuralVariant;
  onClose: () => void;
  onSave: (payload: StructuralVariantReviewSavePayload) => Promise<void>;
  isPending?: boolean;
  errorMessage?: string | null;
};

const formatPoints = (value: number): string =>
  (value > 0 ? '+' : '') + value.toFixed(2).replace(/\.?0+$/, (m) => (m === '.00' ? '' : m));

export default function CnvAcmgClassificationModal({
  variant,
  onClose,
  onSave,
  isPending = false,
  errorMessage = null,
}: CnvAcmgClassificationModalProps) {
  const savedKind = variant.review?.cnv_acmg?.kind;
  const [kind, setKind] = useState<CnvKind>(savedKind ?? cnvKindForType(variant.type));

  const suggestions = useMemo(
    () =>
      evaluateCnv({
        type: variant.type,
        gene: variant.gene,
        genePli: variant.gene_pli ?? variant.annotation_extra?.pli ?? null,
        inheritance: variant.annotation_extra?.inheritance ?? null,
      }),
    [variant],
  );

  // Re-seed selections whenever the kind changes; saved selections apply only when
  // their kind matches what is being shown.
  const [selectionsByKind, setSelectionsByKind] = useState<Record<CnvKind, CnvSelection[]>>(() => {
    const saved = variant.review?.cnv_acmg?.criteria;
    const seed = (k: CnvKind) =>
      buildInitialCnvSelections(k, suggestions, savedKind === k ? saved : undefined);
    return { loss: seed('loss'), gain: seed('gain') };
  });

  const selections = selectionsByKind[kind];
  const classification = useMemo(
    () => computeCnvClassification(kind, selections),
    [kind, selections],
  );

  const updateSelection = (code: string, patch: Partial<CnvSelection>) => {
    setSelectionsByKind((current) => ({
      ...current,
      [kind]: current[kind].map((selection) =>
        selection.code === code ? { ...selection, ...patch } : selection,
      ),
    }));
  };

  const sections = useMemo(() => {
    const defs = cnvCriteriaForKind(kind);
    const grouped = new Map<string, typeof defs>();
    defs.forEach((def) => {
      const list = grouped.get(def.section) ?? [];
      list.push(def);
      grouped.set(def.section, list);
    });
    return Array.from(grouped.entries());
  }, [kind]);

  const selectionMap = useMemo(
    () => Object.fromEntries(selections.map((selection) => [selection.code, selection])),
    [selections],
  );

  const handleSave = async () => {
    const payload: StructuralVariantReviewSavePayload = {
      classification: classification.classLabel,
      tags: variant.review?.tags ?? [],
      note: variant.review?.note ?? undefined,
      cnv_acmg: {
        kind,
        criteria: selections.map((selection) => ({
          code: selection.code,
          points: selection.points,
          accepted: selection.accepted,
          evidence: selection.evidence ?? undefined,
          auto_suggested: selection.autoSuggested,
        })),
        point_total: classification.pointTotal,
        classification: classification.classLabel,
      },
    };
    await onSave(payload);
  };

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-surface surface-card variant-review-modal acmg-modal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="variant-review-modal-header">
          <div className="variant-review-modal-summary">
            <p className="page-kicker">ClinGen CNV classification</p>
            <h2 className="section-title">
              {variant.type || 'SV'} · {variant.chr}:{variant.start.toLocaleString()}-
              {variant.end.toLocaleString()}
              {variant.gene ? ` · ${variant.gene}` : ''}
            </h2>
            <p className="variant-review-modal-subtitle">
              Semi-automatic decision support (Riggs et al., 2020). Confirm every criterion before
              clinical use.
            </p>
          </div>
          <label className="variant-summary-select-field">
            <span>CNV type</span>
            <select value={kind} onChange={(event) => setKind(event.target.value as CnvKind)}>
              <option value="loss">Copy-number loss</option>
              <option value="gain">Copy-number gain</option>
            </select>
          </label>
        </div>

        <div className="variant-review-modal-body acmg-modal-body">
          {errorMessage ? (
            <div className="variant-workspace-feedback variant-workspace-feedback--error">
              {errorMessage}
            </div>
          ) : null}

          <div className="acmg-modal-classification-banner">
            <span className="table-chip report-classification-chip">
              {classification.classLabel}
            </span>
            <span className="table-subtle">Point total {formatPoints(classification.pointTotal)}</span>
          </div>

          {sections.map(([section, defs]) => (
            <div key={section} className="acmg-criteria-section">
              <p className="variant-card-section-title">
                {CNV_SECTION_TITLES[section] || `Section ${section}`}
              </p>
              <div className="cnv-criteria-list">
                {defs.map((def) => {
                  const selection = selectionMap[def.code];
                  if (!selection) return null;
                  const adjustable = def.minPoints !== def.maxPoints;
                  return (
                    <div
                      key={def.code}
                      className={`cnv-criterion-row${selection.accepted ? ' cnv-criterion-row--active' : ''}`}
                    >
                      <label className="analysis-checkbox cnv-criterion-main">
                        <input
                          type="checkbox"
                          checked={selection.accepted}
                          onChange={(event) =>
                            updateSelection(def.code, { accepted: event.target.checked })
                          }
                        />
                        <span>
                          <strong>{def.code}</strong> — {def.name}
                          {selection.autoSuggested ? (
                            <span className="table-chip cnv-auto-chip">auto</span>
                          ) : null}
                        </span>
                      </label>
                      <div className="cnv-criterion-controls">
                        <label className="cnv-points-field">
                          <span>Points</span>
                          <input
                            type="number"
                            step={0.05}
                            min={def.minPoints}
                            max={def.maxPoints}
                            value={selection.points}
                            disabled={!adjustable}
                            onChange={(event) =>
                              updateSelection(def.code, {
                                points: Math.max(
                                  def.minPoints,
                                  Math.min(def.maxPoints, Number(event.target.value)),
                                ),
                              })
                            }
                          />
                          <span className="table-subtle">
                            [{formatPoints(def.minPoints)} … {formatPoints(def.maxPoints)}]
                          </span>
                        </label>
                        <input
                          className="cnv-evidence-field"
                          placeholder="Evidence / note"
                          value={selection.evidence ?? ''}
                          onChange={(event) =>
                            updateSelection(def.code, { evidence: event.target.value })
                          }
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="variant-search-actions variant-review-modal-actions">
          <button type="button" className="button-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="form-button" disabled={isPending} onClick={handleSave}>
            {isPending ? 'Saving…' : 'Save classification'}
          </button>
        </div>
      </div>
    </div>
  );
}
