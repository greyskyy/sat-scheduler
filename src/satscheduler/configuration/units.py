"""Specific unit classes."""
import astropy.units as u


class Frequency(u.SpecificTypeQuantity):
    """Specific type quantity for frequency.

    The base type is Hz.
    """

    _equivalent_unit = u.Hz
    _unit = u.Hz
    _default_unit = u.Hz

    def _set_unit(self, unit):
        if unit is None:
            super()._set_unit(u.Hz)
        else:
            super()._set_unit(unit)


class Mass(u.SpecificTypeQuantity):
    """Specific type quantity for mass.

    The base unit is kg.
    """

    _equivalent_unit = u.kg
    _unit = u.kg
    _default_unit = u.kg

    def _set_unit(self, unit):
        if unit is None:
            super()._set_unit(u.kg)
        else:
            super()._set_unit(unit)


class Area(u.SpecificTypeQuantity):
    """Specific type quantity for a 2-dimensional area.

    The base unit is m^2.
    """

    _equivalent_unit = u.m**2
    _unit = u.m**2
    _default_unit = u.m**2

    def _set_unit(self, unit):
        if unit is None:
            super()._set_unit(u.m**2)
        else:
            super()._set_unit(unit)
