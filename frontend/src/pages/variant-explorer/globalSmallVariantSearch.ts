import { useCallback, useMemo, useState } from 'react';
import type { FormEvent } from 'react';

import {
  buildActiveFilterChips,
  buildSmallVariantQueryParams,
  createEmptySmallFilters,
  joinFilterValues,
  MULTI_VALUE_FILTER_KEYS,
  parseCommaSeparatedValues,
  type ActiveSmallFilterChip,
  type FamilyMember,
  type SmallFilterState,
  type SmallPreset,
  type SmallVariantFamily,
  type SmallVariantFilterPreset,
  type SmallVariantSampleFilter,
} from '../families/smallVariantSearch';

export type GlobalVariantSort =
  | 'total_samples'
  | 'het_samples'
  | 'hom_samples'
  | 'total_families'
  | 'position';

export type GlobalVariantOrder = 'asc' | 'desc';

export type GenotypeFilterMode = 'het' | 'hom' | 'het_hom';

export interface SampleGenotypeFilter {
  sample: string;
  mode: GenotypeFilterMode;
}

const PAGE_SIZE = 50;

const EMPTY_MEMBERS: FamilyMember[] = [];
const EMPTY_RELATIONSHIPS: SmallVariantFamily['relationships'] = [];
const EMPTY_SAMPLE_FILTERS: Record<string, SmallVariantSampleFilter> = {};

/**
 * Family-agnostic counterpart to `useSmallVariantSearchState`. It reuses the
 * shared `SmallFilterState`, chip rendering and query-string serialisation so
 * the Global Small Variant Explorer can render the existing
 * `SmallVariantFilterForm` (with `familyAware={false}`) while talking to the
 * variant-explorer API. Family/sample handlers are intentionally no-ops.
 */
export const useGlobalSmallVariantSearchState = () => {
  const emptyFilters = useMemo(() => createEmptySmallFilters(), []);
  const [draftFilters, setDraftFilters] = useState<SmallFilterState>(emptyFilters);
  const [filters, setFilters] = useState<SmallFilterState>(emptyFilters);
  const [page, setPage] = useState(1);
  const [assemblyId, setAssemblyIdState] = useState<string | undefined>(undefined);
  const [sort, setSortState] = useState<GlobalVariantSort>('total_samples');
  const [order, setOrder] = useState<GlobalVariantOrder>('desc');
  const [includeImputed, setIncludeImputedState] = useState(false);
  const [genotypeFilters, setGenotypeFilters] = useState<SampleGenotypeFilter[]>([]);

  const setDraftFilterValue = useCallback((name: keyof SmallFilterState, value: string) => {
    setDraftFilters((prev) => ({ ...prev, [name]: value }));
  }, []);

  const toggleDraftFilterListValue = useCallback(
    (
      key: Extract<
        keyof SmallFilterState,
        | 'impact'
        | 'effect'
        | 'clinvar'
        | 'exclude_clinvar'
        | 'exclude_review_tags'
        | 'classification'
        | 'review_tags'
        | 'category'
      >,
      value: string,
    ) => {
      setDraftFilters((prev) => {
        const current = new Set(parseCommaSeparatedValues(prev[key]));
        if (current.has(value)) {
          current.delete(value);
        } else {
          current.add(value);
        }
        return { ...prev, [key]: joinFilterValues(current) };
      });
    },
    [],
  );

  const handleApply = useCallback(
    (event: FormEvent) => {
      event.preventDefault();
      setFilters(draftFilters);
      setPage(1);
    },
    [draftFilters],
  );

  const handleReset = useCallback(() => {
    setDraftFilters(emptyFilters);
    setFilters(emptyFilters);
    setPage(1);
  }, [emptyFilters]);

  const activeFilterChips = useMemo(
    () => buildActiveFilterChips(filters, EMPTY_MEMBERS, EMPTY_SAMPLE_FILTERS),
    [filters],
  );

  const removeActiveFilterChip = useCallback((chip: ActiveSmallFilterChip) => {
    if (chip.kind !== 'top') return;
    setFilters((prev) => {
      const next = { ...prev };
      if (MULTI_VALUE_FILTER_KEYS.has(chip.key) && chip.value) {
        next[chip.key] = joinFilterValues(
          parseCommaSeparatedValues(next[chip.key]).filter((value) => value !== chip.value),
        );
      } else {
        next[chip.key] = '';
      }
      if (chip.key === 'locus') {
        next.chr = '';
        next.start = '';
        next.end = '';
        next.gene = '';
      }
      return next;
    });
    // Keep the editable draft in sync with the applied filters.
    setDraftFilters((prev) => {
      const next = { ...prev };
      if (MULTI_VALUE_FILTER_KEYS.has(chip.key) && chip.value) {
        next[chip.key] = joinFilterValues(
          parseCommaSeparatedValues(next[chip.key]).filter((value) => value !== chip.value),
        );
      } else {
        next[chip.key] = '';
      }
      return next;
    });
    setPage(1);
  }, []);

  const setAssemblyId = useCallback((nextAssemblyId: string | undefined) => {
    setAssemblyIdState(nextAssemblyId);
    setPage(1);
  }, []);

  const setIncludeImputed = useCallback((next: boolean) => {
    setIncludeImputedState(next);
    setPage(1);
  }, []);

  const applyGenotypeFilters = useCallback((next: SampleGenotypeFilter[]) => {
    setGenotypeFilters(next);
    setPage(1);
  }, []);

  const setSort = useCallback(
    (nextSort: GlobalVariantSort) => {
      if (sort === nextSort) {
        setOrder((prevOrder) => (prevOrder === 'desc' ? 'asc' : 'desc'));
      } else {
        setSortState(nextSort);
        setOrder('desc');
      }
      setPage(1);
    },
    [sort],
  );

  const requestQueryString = useMemo(() => {
    const params = buildSmallVariantQueryParams(filters, EMPTY_SAMPLE_FILTERS, page);
    params.set('page_size', String(PAGE_SIZE));
    params.set('sort', sort);
    params.set('order', order);
    if (assemblyId) {
      params.set('assembly_id', assemblyId);
    }
    if (includeImputed) {
      params.set('include_imputed', 'true');
    }
    genotypeFilters.forEach((entry) => {
      if (entry.sample) {
        params.append('sample_gt', `${entry.sample}:${entry.mode}`);
      }
    });
    return params.toString();
  }, [filters, page, sort, order, assemblyId, includeImputed, genotypeFilters]);

  // No-op family/sample handlers (the form hides these controls when
  // familyAware={false}, but the prop contract still requires them).
  const noopGtToggle = useCallback(() => {}, []);
  const noopSampleFieldChange = useCallback(() => {}, []);
  const noopApplyPreset = useCallback(() => {}, []);
  const noopApplySavedPreset = useCallback(() => {}, []);

  return {
    activeFilterChips,
    applyPreset: noopApplyPreset as (preset: SmallPreset) => void,
    applySavedPreset: noopApplySavedPreset as (preset: SmallVariantFilterPreset) => void,
    draftFilters,
    filters,
    handleApply,
    handleGtToggle: noopGtToggle as (sample: string, group: string, checked: boolean) => void,
    handleReset,
    handleSampleFieldChange: noopSampleFieldChange as (
      sample: string,
      field: keyof SmallVariantSampleFilter,
      value: string,
    ) => void,
    members: EMPTY_MEMBERS,
    relationships: EMPTY_RELATIONSHIPS,
    removeActiveFilterChip,
    sampleDraftFilters: EMPTY_SAMPLE_FILTERS,
    setDraftFilterValue,
    toggleDraftFilterListValue,
    // Global-explorer specific state.
    page,
    setPage,
    assemblyId,
    setAssemblyId,
    sort,
    order,
    setSort,
    includeImputed,
    setIncludeImputed,
    genotypeFilters,
    applyGenotypeFilters,
    requestQueryString,
  };
};
