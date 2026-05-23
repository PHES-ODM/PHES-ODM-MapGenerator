import pandas as pd

from odm_map_maker.utils.selector_filter import SelectorFilter


def _df(selectors):
    """Build a single-row DataFrame with the given selectors value."""
    return pd.DataFrame({"selectors": [selectors]})


def _apply(constructor_selectors, row_selector):
    sf = SelectorFilter(selectors=constructor_selectors, selector_column="selectors")
    result = sf.apply(_df(row_selector), remove_selectors_column=True)
    return len(result) == 1


# ---------------------------------------------------------------------------
# Blank / empty row selector — always kept
# ---------------------------------------------------------------------------

def test_blank_row_always_kept():
    assert _apply("amr", None) is True
    assert _apply("amr", "") is True
    assert _apply("", "") is True
    assert _apply(None, None) is True


# ---------------------------------------------------------------------------
# Include flags
# ---------------------------------------------------------------------------

def test_include_flag_kept_when_matching():
    assert _apply("amr", "amr") is True

def test_include_flag_dropped_when_not_matching():
    assert _apply("amr", "deprecated") is False

def test_include_flag_dropped_when_constructor_has_no_includes():
    # No include flags in constructor → row with include flag is dropped
    assert _apply("!deprecated", "amr") is False

def test_row_with_multiple_include_flags_kept_if_any_match():
    assert _apply("b,c", "a,b") is True

def test_row_with_multiple_include_flags_dropped_if_none_match():
    assert _apply("c,d", "a,b") is False

def test_row_kept_when_no_include_flags_and_constructor_has_some():
    # Row has no include flags → not filtered by include rule
    assert _apply("amr", "!deprecated") is True


# ---------------------------------------------------------------------------
# Exclude flags
# ---------------------------------------------------------------------------

def test_constructor_exclude_drops_row_with_that_flag():
    assert _apply("!amr", "amr") is False

def test_row_exclude_drops_row_when_constructor_has_that_flag():
    # Row says "!deprecated", constructor passes "deprecated" → drop
    assert _apply("deprecated", "!deprecated") is False

def test_exclude_flag_no_effect_when_not_present():
    # Constructor has only "!deprecated" (no include flags).
    # A row with include flags ("amr,other") is dropped by rule 1 (no matching constructor include flag).
    assert _apply("!deprecated", "amr,other") is False
    # A row with only exclude flags and no include flags is kept.
    assert _apply("!deprecated", "!other") is True
    # A blank row is always kept.
    assert _apply("!deprecated", None) is True


# ---------------------------------------------------------------------------
# Module version selectors
# ---------------------------------------------------------------------------

def test_module_version_kept_when_matches():
    assert _apply("odm=3.0", "odm>=3.0") is True
    assert _apply("odm=3.0", "odm<=3.0") is True
    assert _apply("odm=3.0", "odm>=2.0,odm<=4.0") is True

def test_module_version_dropped_when_outside_range():
    assert _apply("odm=2.0", "odm>=3.0") is False
    assert _apply("odm=3.2", "odm>=3.0,odm<=3.1") is False

def test_module_version_dropped_when_module_not_in_constructor():
    # Row requires odm version but constructor specifies no odm version
    assert _apply("", "odm>=3.0") is False
    assert _apply("!deprecated", "odm>=3.0") is False

def test_unrelated_module_in_constructor_doesnt_affect_row():
    # Constructor has "nwss=1", row has "odm>=3.0" → different module, row dropped
    assert _apply("nwss=1", "odm>=3.0") is False


# ---------------------------------------------------------------------------
# apply_single helper
# ---------------------------------------------------------------------------

def test_apply_single_true():
    sf = SelectorFilter(selectors="amr,odm=3.0", selector_column="selectors")
    assert sf.apply_single("amr") is True
    assert sf.apply_single("odm>=3.0") is True

def test_apply_single_false():
    sf = SelectorFilter(selectors="amr", selector_column="selectors")
    assert sf.apply_single("deprecated") is False


# ---------------------------------------------------------------------------
# Multiple rows in DataFrame
# ---------------------------------------------------------------------------

def test_filters_multiple_rows():
    sf = SelectorFilter(selectors="amr", selector_column="selectors")
    df = pd.DataFrame({"selectors": ["amr", "deprecated", None, "amr,other"]})
    result = sf.apply(df, remove_selectors_column=True)
    # "amr" matches, "deprecated" doesn't, None is blank (kept), "amr,other" matches
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Comma-separated constructor selectors
# ---------------------------------------------------------------------------

def test_constructor_accepts_comma_string():
    sf = SelectorFilter(selectors="amr,!deprecated,odm=3.0", selector_column="selectors")
    assert sf.apply_single("amr") is True
    assert sf.apply_single("deprecated") is False
    assert sf.apply_single("odm>=3.0") is True

def test_constructor_accepts_list():
    sf = SelectorFilter(selectors=["amr", "!deprecated"], selector_column="selectors")
    assert sf.apply_single("amr") is True
    assert sf.apply_single("deprecated") is False
