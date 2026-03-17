"""
physics.py — Ocean environment model for the AUV swarm simulation.
Models temperature, pressure, sound speed, buoyancy, current drag,
and depth-coupled fault probability.
"""
import math
import numpy as np

import config


class OceanEnvironment:
    """Underwater column physics for depth-aware AMV simulation."""

    def __init__(self):
        self._surface_temp = config.SURFACE_TEMP
        self._deep_temp = config.DEEP_TEMP
        self._thermocline_depth = config.THERMOCLINE_DEPTH
        self._thermocline_width = config.THERMOCLINE_WIDTH
        self._salinity = config.SALINITY

    # ── Temperature ──────────────────────────────────────────────────────────

    def temperature(self, depth: float) -> float:
        """
        Water temperature at a given depth using sigmoid thermocline.
        Surface: ~28 °C, Deep: ~4 °C, transition centred at 80 m.
        """
        exponent = (depth - self._thermocline_depth) / (self._thermocline_width / 4.0)
        sigmoid = 1.0 / (1.0 + math.exp(-exponent))
        return self._surface_temp - (self._surface_temp - self._deep_temp) * sigmoid

    # ── Pressure ─────────────────────────────────────────────────────────────

    @staticmethod
    def pressure(depth: float) -> float:
        """Hydrostatic pressure in bar. ~1 bar per 10 m + 1.013 atm."""
        return 1.013 + depth / 10.0

    # ── Sound speed (Mackenzie 1981) ─────────────────────────────────────────

    def sound_speed(self, depth: float) -> float:
        """
        Sound speed in m/s using the Mackenzie (1981) nine-term equation.
        Inputs: temperature (°C), salinity (PSU), depth (m).
        """
        T = self.temperature(depth)
        S = self._salinity
        D = depth
        c = (1448.96 + 4.591 * T - 5.304e-2 * T**2 + 2.374e-4 * T**3
             + 1.340 * (S - 35) + 1.630e-2 * D + 1.675e-7 * D**2
             - 1.025e-2 * T * (S - 35) - 7.139e-13 * T * D**3)
        return c

    # ── Buoyancy ─────────────────────────────────────────────────────────────

    def buoyancy(self, volume: float, mass: float, depth: float) -> float:
        """
        Net buoyancy force (N).  Positive = upward.
        Uses seawater density ≈ 1025 kg/m³ (slight depth adjustment).
        """
        rho_sw = 1025.0 + 0.005 * depth       # small compressibility correction
        g = 9.81
        buoyant_force = rho_sw * volume * g
        weight = mass * g
        return buoyant_force - weight

    # ── Ocean current drag ───────────────────────────────────────────────────

    @staticmethod
    def current_drag(timestep: int) -> np.ndarray:
        """
        Slow time-varying sinusoidal 2D drag vector (m/timestep).
        Represents tidal / current effects in the horizontal plane.
        """
        vx = 0.8 * math.sin(2.0 * math.pi * timestep / 500.0)
        vy = 0.5 * math.cos(2.0 * math.pi * timestep / 700.0)
        return np.array([vx, vy], dtype=np.float64)

    # ── Fault probability modifier ───────────────────────────────────────────

    def fault_modifier(self, depth: float) -> float:
        """
        Fault probability multiplier scaled by pressure.
        1.0 at surface → 2.5 at 200 m depth (linear interpolation).
        """
        p = self.pressure(depth)
        p_surface = self.pressure(0)
        p_deep = self.pressure(200.0)
        ratio = (p - p_surface) / (p_deep - p_surface)
        return 1.0 + 1.5 * min(ratio, 1.0)

    # ── Depth-dependent effective acoustic range ─────────────────────────────

    @staticmethod
    def effective_acoustic_range(depth: float) -> float:
        """
        Interpolate acoustic range: 3000 m at surface → 1800 m at 150 m depth.
        """
        t = min(depth / 150.0, 1.0)
        return config.ACOUSTIC_RANGE_SURFACE * (1.0 - t) + config.ACOUSTIC_RANGE_DEEP * t
