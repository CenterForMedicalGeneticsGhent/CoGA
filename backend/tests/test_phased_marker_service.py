from backend.app.services.phased_marker_service import compute_phased_markers


def _rows(*variants):
    """variants: (pos, {sample: gt}) -> the (pos, sample_ids, gts) tuple shape."""
    return [(pos, list(gt.keys()), list(gt.values())) for pos, gt in variants]


def test_tracks_a_paternal_recombination_mother_homozygous():
    rows = _rows(
        (100, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # paternal homolog 0
        (200, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # 0
        (300, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1  <- switch
        (400, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1
    )
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    markers = out["C"]
    assert [m.hap1 for m in markers] == [0, 0, 1, 1]  # paternal homolog inherited
    # mother homozygous everywhere -> maternal side uninformative
    assert all(m.hap2 is None for m in markers)


def test_maternal_informative_when_father_homozygous():
    rows = _rows((100, {"F": "0|0", "M": "0|1", "C": "0|1"}))
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    marker = out["C"][0]
    assert marker.hap2 == 1  # maternal homolog inherited
    assert marker.hap1 is None


def test_orients_homologs_by_the_affected_child():
    # affected child inherits paternal homolog 0 three times, 1 once -> father_flip
    rows = _rows(
        (100, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (200, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (300, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (400, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # raw 1
    )
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected={"C"})
    # raw [0,0,0,1] flipped -> [1,1,1,0]
    assert [m.hap1 for m in out["C"]] == [1, 1, 1, 0]


def test_single_marker_switches_are_preserved_raw():
    # An isolated switch (the "0" amid 1s) is the kind of phasing noise/uncertainty
    # this overlay exists to surface. It must NOT be smoothed away — every site is
    # emitted as its own raw call, one marker per position.
    rows = _rows(
        (10, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # paternal 1
        (20, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1
        (30, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # 0  (isolated switch)
        (40, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1
    )
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    assert [(m.pos, m.hap1) for m in out["C"]] == [(10, 1), (20, 1), (30, 0), (40, 1)]


def test_emits_parent_markers_as_their_own_phased_alleles():
    rows = _rows(
        (100, {"F": "0|1", "M": "0|0", "C": "0|0"}),
        (200, {"F": "1|0", "M": "0|1", "C": "0|1"}),
    )
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    # Parents carry the alleles on their own two homologs (raw, not oriented).
    assert [(m.pos, m.hap1, m.hap2) for m in out["F"]] == [(100, 0, 1), (200, 1, 0)]
    assert [(m.pos, m.hap1, m.hap2) for m in out["M"]] == [(100, 0, 0), (200, 0, 1)]


def test_ambiguous_markers_are_dropped_for_the_child_only():
    # both parents het, child het -> parent-of-origin ambiguous on both sides
    rows = _rows((100, {"F": "0|1", "M": "0|1", "C": "0|1"}))
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    assert out["C"] == []
    # ...but the parents still get their own raw markers at that site.
    assert [(m.hap1, m.hap2) for m in out["F"]] == [(0, 1)]
    assert [(m.hap1, m.hap2) for m in out["M"]] == [(0, 1)]


def test_requires_both_parents_present_in_the_data():
    rows = _rows((100, {"M": "0|0", "C": "0|1"}))  # father absent
    out = compute_phased_markers(rows, father="F", mother="M", children=["C"], affected=set())
    assert out["C"] == []
    assert out["F"] == []
    assert out["M"] == []
