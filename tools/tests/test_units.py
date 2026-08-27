"""Float emission. Determinism (ADR-0004) depends entirely on this."""

from __future__ import annotations

import pytest

from cite_tools.model import units


class TestDeterminism:
    def test_negative_zero_normalises(self) -> None:
        assert units.fmt(-0.0) == units.fmt(0.0) == "0"

    def test_near_zero_normalises(self) -> None:
        # A yaw computed as a difference of equal angles can land here.
        assert units.fmt(-1e-17) == "0"
        assert units.fmt(1e-17) == "0"

    def test_no_scientific_notation_for_realistic_magnitudes(self) -> None:
        for value in (0.001, 0.05, 1.2, 1200.0, 6.15):
            assert "e" not in units.fmt(value), value

    def test_stable_across_repeated_calls(self) -> None:
        value = 1.5707963267948966
        assert len({units.fmt(value) for _ in range(100)}) == 1

    def test_integral_values_lose_the_trailing_zero(self) -> None:
        assert units.fmt(1200.0) == "1200"
        assert units.fmt(2.0) == "2"


class TestTriple:
    def test_formats_as_urdf_expects(self) -> None:
        assert units.fmt_triple([0.0, -0.0, 0.6]) == "0 0 0.6"

    def test_rejects_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="exactly 3"):
            units.fmt_triple([0.0, 1.0])


class TestDisplayOnly:
    def test_degrees_are_display_only(self) -> None:
        # Present for `cite-model show`; must never appear in the model itself.
        assert units.degrees_for_display(1.5707963267948966) == "90"


class TestYamlSafeFloat:
    """Generated YAML read back as ROS parameters must keep its floats floating."""

    def test_whole_numbers_keep_a_decimal_point(self) -> None:
        # YAML parses `2` as an integer, and a node declaring the parameter as a
        # double then rejects it with "expected [double] got [integer]" — an
        # error that names the type but not the missing decimal point.
        assert units.fmt_float(2.0) == "2.0"
        assert units.fmt_float(0.0) == "0.0"
        assert units.fmt_float(-3.0) == "-3.0"

    def test_fractional_values_are_unchanged(self) -> None:
        assert units.fmt_float(0.35) == "0.35"
        assert units.fmt_float(0.005) == "0.005"

    def test_round_trips_through_yaml_as_a_float(self) -> None:
        import yaml

        for value in (2.0, 0.0, 0.35, 1200.0):
            loaded = yaml.safe_load(f"x: {units.fmt_float(value)}")["x"]
            assert isinstance(loaded, float), f"{value} came back as {type(loaded).__name__}"
