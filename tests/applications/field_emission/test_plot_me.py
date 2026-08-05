import pytest

from sc_linac_physics.applications.field_emission import plot_me


def test_add_poly_fit():
    try:
        plot_me.add_poly_fit(None, None, None, None)
    except TypeError:
        pytest.fail("add_poly_fit raises TypeError")