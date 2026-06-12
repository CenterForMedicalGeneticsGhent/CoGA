from backend.app.services.phased_marker_service import compute_phased_marker_bins


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
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected=set(), start=0, end=500, max_bins=500
    )
    markers = out["C"]
    assert [m.paternal for m in markers] == [0, 0, 1, 1]
    # mother homozygous everywhere -> maternal side uninformative
    assert all(m.maternal is None for m in markers)


def test_maternal_informative_when_father_homozygous():
    rows = _rows((100, {"F": "0|0", "M": "0|1", "C": "0|1"}))
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected=set(), start=0, end=200, max_bins=200
    )
    marker = out["C"][0]
    assert marker.maternal == 1
    assert marker.paternal is None


def test_orients_homologs_by_the_affected_child():
    # affected child inherits paternal homolog 0 three times, 1 once -> father_flip
    rows = _rows(
        (100, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (200, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (300, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # raw 0
        (400, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # raw 1
    )
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected={"C"}, start=0, end=500, max_bins=500
    )
    # raw [0,0,0,1] flipped -> [1,1,1,0]
    assert [m.paternal for m in out["C"]] == [1, 1, 1, 0]


def test_bin_majority_denoises_single_marker_errors():
    rows = _rows(
        (10, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # paternal 1
        (20, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1
        (30, {"F": "0|1", "M": "0|0", "C": "0|0"}),  # 0  (noise)
        (40, {"F": "0|1", "M": "0|0", "C": "0|1"}),  # 1
    )
    # all four fall in a single bin
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected=set(), start=0, end=100, max_bins=1
    )
    assert len(out["C"]) == 1
    assert out["C"][0].paternal == 1  # majority of [1, 1, 0, 1]


def test_ambiguous_markers_are_dropped():
    # both parents het, child het -> parent-of-origin ambiguous on both sides
    rows = _rows((100, {"F": "0|1", "M": "0|1", "C": "0|1"}))
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected=set(), start=0, end=200, max_bins=200
    )
    assert out["C"] == []


def test_requires_both_parents_present_in_the_data():
    rows = _rows((100, {"M": "0|0", "C": "0|1"}))  # father absent
    out = compute_phased_marker_bins(
        rows, father="F", mother="M", children=["C"], affected=set(), start=0, end=200, max_bins=200
    )
    assert out["C"] == []
