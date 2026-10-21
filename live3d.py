"""
live3d.py  —  Cinematic Real-Time 3D Ocean Simulation Visualisation
====================================================================
Renders a photorealistic-styled underwater mission environment with:
  • High-resolution procedural seabed with depth-graded colouring
  • Volumetric water column layers (surface → thermocline → deep)
  • Animated caustic light patterns on the seabed
  • Metallic submarine AUV models with glow halos & headlights
  • Bioluminescent particle field (ambient marine snow)
  • Holographic task beacon projections
  • Animated acoustic communication arcs with pulse markers
  • Cinematic slow-orbit camera with depth-of-field tinting
  • Multi-panel HUD overlay (energy bars, fault states, task table)
"""
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("TkAgg")   # interactive backend — change to Qt5Agg if TkAgg unavailable

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
import numpy as np
from collections import deque

import config

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette — cinematic deep-ocean
# ─────────────────────────────────────────────────────────────────────────────
AMV_COLORS   = ['#00C6FF', '#FF6B35', '#00E676', '#FF2D6F', '#B040FF']
AMV_GLOW     = ['#80EEFF', '#FFB380', '#69F0AE', '#FF80AB', '#D580FF']
AMV_DARK     = ['#004466', '#662200', '#004D26', '#66001F', '#3D0066']
FAULT_COLORS = {
    'normal':                  '#00E676',
    'actuator_degraded_mild':  '#FFD740',
    'actuator_degraded_severe':'#FF6D00',
    'sensor_failure':          '#FF1744',
    'load_fault':              '#AA00FF',
}

# Ocean depth colour stops
WATER_SURFACE  = '#0a3d5c'
WATER_SHALLOW  = '#062d4a'
WATER_MID      = '#041e35'
WATER_DEEP     = '#020e1a'
WATER_ABYSS    = '#010810'

# Seabed palette
SEABED_SHALLOW = '#3a5a3a'
SEABED_MID     = '#2a4a2e'
SEABED_DEEP    = '#1a3420'
SEABED_RIDGE   = '#4a6a42'


# ─────────────────────────────────────────────────────────────────────────────
# Helper — smooth Perlin-like noise for terrain
# ─────────────────────────────────────────────────────────────────────────────
def _fractal_terrain(shape, seed=42, octaves=4, persistence=0.5, base_scale=4.0):
    """Generate fractal noise terrain using summed interpolated noise."""
    rng = np.random.default_rng(seed)
    result = np.zeros(shape)
    amplitude = 1.0
    for octave in range(octaves):
        scale = base_scale * (2 ** octave)
        # Generate small random grid and interpolate up
        small_h = max(3, int(shape[0] / scale) + 2)
        small_w = max(3, int(shape[1] / scale) + 2)
        noise = rng.standard_normal((small_h, small_w))
        # Bilinear interpolation to full resolution
        from scipy.ndimage import zoom
        zoomed = zoom(noise, (shape[0] / small_h, shape[1] / small_w), order=3)
        # Crop to exact shape
        zoomed = zoomed[:shape[0], :shape[1]]
        result += amplitude * zoomed
        amplitude *= persistence
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build a detailed submarine geometry
# ─────────────────────────────────────────────────────────────────────────────
def _make_sub_verts(cx, cy, cz, length=28.0, radius=5.0, heading=0.0):
    """
    Returns a list of (face_verts, face_color) tuples for a submarine-like
    hull rendered at (cx, cy, cz) with the nose pointing along `heading` (rad).
    Includes hull body, nose cone, sail, stabilizers, and rudder.
    """
    faces = []
    cos_h, sin_h = np.cos(heading), np.sin(heading)

    def rot(dx, dy):
        return dx * cos_h - dy * sin_h, dx * sin_h + dy * cos_h

    # ── Main hull (smooth cylinder approximated as dodecagonal prism) ────
    n_sides = 12
    angles  = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
    nose_x, nose_y = rot(length / 2, 0)
    tail_x, tail_y = rot(-length / 2, 0)

    # Side quads with subtle shading variation
    for i in range(n_sides):
        a0, a1 = angles[i], angles[(i + 1) % n_sides]
        r0 = radius * np.array([np.cos(a0), np.sin(a0)])
        r1 = radius * np.array([np.cos(a1), np.sin(a1)])
        dx0, dz0 = rot(0, r0[0])
        dx1, dz1 = rot(0, r1[0])
        dy0 = r0[1]; dy1 = r1[1]

        v_nose_0 = [cx + nose_x * 0.4 + dx0, cy + nose_y * 0.4 + dz0, cz + dy0 * 0.5]
        v_nose_1 = [cx + nose_x * 0.4 + dx1, cy + nose_y * 0.4 + dz1, cz + dy1 * 0.5]
        v_tail_0 = [cx + tail_x * 0.6 + dx0, cy + tail_y * 0.6 + dz0, cz + dy0 * 0.7]
        v_tail_1 = [cx + tail_x * 0.6 + dx1, cy + tail_y * 0.6 + dz1, cz + dy1 * 0.7]
        faces.append([v_nose_0, v_nose_1, v_tail_1, v_tail_0])

    # ── Nose cone (tapered) ──────────────────────────────────────────────
    tip = [cx + nose_x, cy + nose_y, cz]
    for i in range(n_sides):
        a0, a1 = angles[i], angles[(i + 1) % n_sides]
        r0 = radius * 0.5 * np.array([np.cos(a0), np.sin(a0)])
        r1 = radius * 0.5 * np.array([np.cos(a1), np.sin(a1)])
        dx0, dz0 = rot(0, r0[0]); dy0 = r0[1]
        dx1, dz1 = rot(0, r1[0]); dy1 = r1[1]
        base_0 = [cx + nose_x * 0.4 + dx0, cy + nose_y * 0.4 + dz0, cz + dy0 * 0.5]
        base_1 = [cx + nose_x * 0.4 + dx1, cy + nose_y * 0.4 + dz1, cz + dy1 * 0.5]
        faces.append([tip, base_0, base_1])

    # ── Sail (conning tower) ──────────────────────────────────────────────
    sx, sy = rot(length * 0.1, 0)
    sail_w, sail_h = 4.0, 9.0
    sw, sle = rot(sail_w * 0.5, 0), rot(-sail_w * 0.5, 0)
    base_z = cz + radius * 0.85
    top_z  = base_z + sail_h
    sail_faces = [
        [[cx + sx + sw[0], cy + sy + sw[1], base_z],
         [cx + sx + sle[0], cy + sy + sle[1], base_z],
         [cx + sx + sle[0], cy + sy + sle[1], top_z],
         [cx + sx + sw[0], cy + sy + sw[1], top_z]],
    ]
    faces += sail_faces

    # ── Horizontal stabilisers (cross-fins at tail) ──────────────────────
    tx, ty = rot(-length * 0.4, 0)
    for sign in (+1, -1):
        fin_tip_dx, fin_tip_dy = rot(0, sign * radius * 2.5)
        fin_root_dx, fin_root_dy = rot(0, sign * radius * 1.0)
        fin_back_dx, fin_back_dy = rot(-length * 0.1, sign * radius * 2.0)
        faces.append([
            [cx + tx + fin_root_dx, cy + ty + fin_root_dy, cz],
            [cx + tx + fin_tip_dx,  cy + ty + fin_tip_dy,  cz],
            [cx + tx + fin_back_dx, cy + ty + fin_back_dy, cz - 1.5],
        ])

    # ── Vertical rudder fin ──────────────────────────────────────────────
    vfin = [[cx + tx,                cy + ty,           cz + radius * 0.8],
            [cx + tx,                cy + ty,           cz + radius * 2.2],
            [cx + tx - length * 0.08, cy + ty,          cz + radius * 1.5]]
    faces.append(vfin)

    return faces


def _make_target_verts(tx, ty, tz, r=12.0):
    """
    Returns face lists for a sonar-target marker: a diamond/octahedron shape
    anchored at the seabed at (tx, ty, tz=seabed depth).
    """
    faces = []
    top  = [tx, ty, tz + r]
    bot  = [tx, ty, tz - r * 0.3]
    ring = [(tx + r * np.cos(a), ty + r * np.sin(a), tz)
            for a in np.linspace(0, 2 * np.pi, 6, endpoint=False)]
    for i in range(6):
        j = (i + 1) % 6
        faces.append([top, ring[i], ring[j]])
        faces.append([bot, ring[i], ring[j]])
    return faces


# ─────────────────────────────────────────────────────────────────────────────
# Custom seabed colormap — depth-aware with sediment tones
# ─────────────────────────────────────────────────────────────────────────────
_SEABED_CMAP = mcolors.LinearSegmentedColormap.from_list(
    'ocean_seabed',
    ['#1a3420', '#2a4a2e', '#3a5a38', '#4a6a42', '#5a7a4c',
     '#3a5a38', '#2a4a30', '#1a3a24'],
    N=256
)

_CAUSTIC_CMAP = mcolors.LinearSegmentedColormap.from_list(
    'caustic_light',
    ['#00000000', '#0088aa22', '#00ccee44', '#0088aa22', '#00000000'],
    N=256
)


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────
class LiveSimulation3D:
    """Cinematic real-time 3D ocean simulation rendering."""

    # Layout constants
    SURF_Z  =   0.0
    FLOOR_Z = -config.DEPTH_MAX
    THERMO_Z = -config.THERMOCLINE_DEPTH

    def __init__(self):
        plt.ion()
        # ── Figure with GridSpec for 3D viewport + HUD column ────────────
        self.fig = plt.figure(figsize=(22, 11), facecolor='#030810')
        self.fig.canvas.manager.set_window_title('AMV Swarm — Deep Ocean Mission Simulator')

        gs = gridspec.GridSpec(4, 3, figure=self.fig,
                               width_ratios=[3.5, 1, 1],
                               hspace=0.04, wspace=0.06,
                               left=0.01, right=0.99, top=0.97, bottom=0.02)

        self.ax  = self.fig.add_subplot(gs[:, 0], projection='3d')
        self.ax_hud_energy  = self.fig.add_subplot(gs[0, 1])
        self.ax_hud_fault   = self.fig.add_subplot(gs[1, 1])
        self.ax_hud_tasks   = self.fig.add_subplot(gs[0:2, 2])
        self.ax_hud_comms   = self.fig.add_subplot(gs[2, 1])
        self.ax_hud_depth   = self.fig.add_subplot(gs[2, 2])
        self.ax_hud_legend  = self.fig.add_subplot(gs[3, 1:])

        for ax in [self.ax_hud_energy, self.ax_hud_fault, self.ax_hud_tasks,
                   self.ax_hud_comms, self.ax_hud_depth, self.ax_hud_legend]:
            ax.set_facecolor('#060d1a')
            for spine in ax.spines.values():
                spine.set_edgecolor('#0f2a4a')
                spine.set_linewidth(0.5)

        self.ax.set_facecolor('#010810')

        # Pre-build static ocean geometry
        self._init_ocean_geometry()

        # Trail buffers
        self._trails  = {}
        self._trail_len = 50
        self._headings = {}
        self._frame   = 0
        self._azim    = -55.0

        # Marine snow particles (persistent bioluminescent specks)
        rng = np.random.default_rng(99)
        M = config.MISSION_SPACE
        n_particles = 80
        self._particles_x = rng.uniform(0, M, n_particles)
        self._particles_y = rng.uniform(0, M, n_particles)
        self._particles_z = rng.uniform(self.FLOOR_Z + 10, self.SURF_Z - 5, n_particles)
        self._particles_drift = rng.uniform(-0.8, 0.8, (n_particles, 3))

        # Fullscreen attempt
        try:
            manager = plt.get_current_fig_manager()
            manager.window.state('zoomed')
        except Exception:
            try:
                manager.full_screen_toggle()
            except Exception:
                pass

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    # ─────────────────────────────────────────────────────────────────────────
    # Static ocean geometry pre-computation
    # ─────────────────────────────────────────────────────────────────────────
    def _init_ocean_geometry(self):
        """Pre-build high-res floor mesh, surface grid, water column layers."""
        M = config.MISSION_SPACE
        N = 30   # balanced resolution — clear enough, not too heavy

        xs = np.linspace(0, M, N)
        ys = np.linspace(0, M, N)
        self._floor_X, self._floor_Y = np.meshgrid(xs, ys)

        # Fractal procedural seabed — gentle undulation (NOT blocking AUVs)
        try:
            terrain = _fractal_terrain((N, N), seed=42, octaves=4,
                                       persistence=0.4, base_scale=3.0)
        except ImportError:
            rng = np.random.default_rng(42)
            terrain = (rng.uniform(-1, 1, (N, N))
                       + 0.6 * np.sin(self._floor_X / 80)
                       + 0.4 * np.cos(self._floor_Y / 60)
                       + 0.3 * np.sin((self._floor_X + self._floor_Y) / 120))

        # Normalize and keep FLAT — only ±3m so it never blocks anything
        terrain = (terrain - terrain.mean()) / (terrain.std() + 1e-8)
        self._floor_Z = self.FLOOR_Z + terrain * 3.0  # ±3m gentle bumps only

        # Surface grid — gentle wave undulation
        Ns = 12
        self._surf_X, self._surf_Y = np.meshgrid(
            np.linspace(0, M, Ns), np.linspace(0, M, Ns))
        self._surf_Z_base = np.zeros_like(self._surf_X) + self.SURF_Z

        # Thermocline slab corners (wider band)
        self._thermo_Z = self.THERMO_Z
        band = 15
        self._thermo_faces_lower = [[
            [0,   0,   self._thermo_Z - band],
            [M,   0,   self._thermo_Z - band],
            [M,   M,   self._thermo_Z - band],
            [0,   M,   self._thermo_Z - band],
        ]]
        self._thermo_faces_upper = [[
            [0,   0,   self._thermo_Z + band],
            [M,   0,   self._thermo_Z + band],
            [M,   M,   self._thermo_Z + band],
            [0,   M,   self._thermo_Z + band],
        ]]
        self._thermo_faces_mid = [[
            [0,   0,   self._thermo_Z],
            [M,   0,   self._thermo_Z],
            [M,   M,   self._thermo_Z],
            [0,   M,   self._thermo_Z],
        ]]

        # Water column depth layers — fewer, subtler so AUVs remain visible
        self._water_layers = []
        layer_depths = np.linspace(self.SURF_Z - 10, self.FLOOR_Z + 30, 3)
        for z in layer_depths:
            self._water_layers.append([[
                [0, 0, z], [M, 0, z], [M, M, z], [0, M, z]
            ]])

    # ─────────────────────────────────────────────────────────────────────────
    # Per-frame update entry point
    # ─────────────────────────────────────────────────────────────────────────
    def update(self, timestep, amvs, tasks, comms_mesh, mt, deadlock_count):
        """Full scene redraw. Called every simulation timestep."""
        self._frame += 1
        ax = self.ax
        ax.cla()

        M = config.MISSION_SPACE

        # ── Convert AMV 2-D position + depth to 3-D world coords ────────
        def amv_z(amv):
            return -getattr(amv, 'depth', 30.0)

        # Update heading estimates from trail history
        for amv in amvs:
            prev = self._trails.get(amv.amv_id)
            if prev and len(prev) >= 2:
                dx = amv.position[0] - prev[-1][0]
                dy = amv.position[1] - prev[-1][1]
                if abs(dx) + abs(dy) > 0.5:
                    self._headings[amv.amv_id] = np.arctan2(dy, dx)
            if amv.amv_id not in self._trails:
                self._trails[amv.amv_id] = deque(maxlen=self._trail_len)
            self._trails[amv.amv_id].append(
                (amv.position[0], amv.position[1], amv_z(amv)))

        # ── Deep ocean background ────────────────────────────────────────
        ax.set_facecolor('#010810')
        ax.xaxis.pane.fill = True;  ax.xaxis.pane.set_facecolor('#020c18')
        ax.yaxis.pane.fill = True;  ax.yaxis.pane.set_facecolor('#01091a')
        ax.zaxis.pane.fill = True;  ax.zaxis.pane.set_facecolor('#011228')
        ax.xaxis.pane.set_edgecolor('#0a2040')
        ax.yaxis.pane.set_edgecolor('#0a2040')
        ax.zaxis.pane.set_edgecolor('#0a2040')
        ax.tick_params(colors='#3a7ab8', labelsize=6)
        # Grid lines — very subtle
        ax.xaxis._axinfo['grid'].update(color='#0a2040', linewidth=0.3)
        ax.yaxis._axinfo['grid'].update(color='#0a2040', linewidth=0.3)
        ax.zaxis._axinfo['grid'].update(color='#0a2040', linewidth=0.3)

        # ── Ocean floor — depth-coloured surface ─────────────────────────
        z_norm = (self._floor_Z - self._floor_Z.min()) / (
            self._floor_Z.max() - self._floor_Z.min() + 1e-8)

        # Animated caustic pattern overlay
        caustic_phase = self._frame * 0.08
        caustic = 0.5 + 0.5 * np.sin(
            self._floor_X / 60 + caustic_phase) * np.cos(
            self._floor_Y / 50 - caustic_phase * 0.7)
        z_colored = np.clip(z_norm + caustic * 0.06, 0, 1)

        ax.plot_surface(self._floor_X, self._floor_Y, self._floor_Z,
                        facecolors=_SEABED_CMAP(z_colored),
                        alpha=0.85,
                        linewidth=0, antialiased=True, shade=True,
                        rstride=1, cstride=1)

        # ── Water column volumetric fog layers ───────────────────────────
        depth_range = abs(self.FLOOR_Z)
        for i, layer_faces in enumerate(self._water_layers):
            z_val = layer_faces[0][0][2]
            depth_frac = abs(z_val) / depth_range
            alpha = 0.01 + depth_frac * 0.03   # very subtle so AUVs stay visible
            r = int(0 + depth_frac * 3)
            g = int(20 - depth_frac * 12)
            b = int(50 - depth_frac * 25)
            color = f'#{max(0,r):02x}{max(0,g):02x}{max(0,b):02x}'
            layer = Poly3DCollection(layer_faces, alpha=alpha, linewidth=0)
            layer.set_facecolor(color)
            layer.set_edgecolor('none')
            ax.add_collection3d(layer)

        # ── Thermocline band (multi-layer for volume feel) ───────────────
        for thermo_faces, alpha_t in [(self._thermo_faces_lower, 0.04),
                                       (self._thermo_faces_mid, 0.07),
                                       (self._thermo_faces_upper, 0.04)]:
            thermo_slab = Poly3DCollection(thermo_faces, alpha=alpha_t, linewidth=0)
            thermo_slab.set_facecolor('#005577')
            thermo_slab.set_edgecolor('none')
            ax.add_collection3d(thermo_slab)

        # ── Ocean surface with animated waves ────────────────────────────
        wave_phase = self._frame * 0.06
        wave_z = self._surf_Z_base + (
            0.6 * np.sin(self._surf_X / 100 + wave_phase)
            * np.cos(self._surf_Y / 90 - wave_phase * 0.5)
        )
        ax.plot_surface(self._surf_X, self._surf_Y, wave_z,
                        color='#0088aa', alpha=0.10,
                        linewidth=0.15, edgecolor='#00bbdd22',
                        antialiased=True)

        # ── Bioluminescent marine snow particles ─────────────────────────
        drift = self._particles_drift
        px = self._particles_x + drift[:, 0] * np.sin(self._frame * 0.03)
        py = self._particles_y + drift[:, 1] * np.cos(self._frame * 0.025)
        pz = self._particles_z + drift[:, 2] * np.sin(self._frame * 0.02 +
                                                        np.arange(len(px)) * 0.1)
        # Subtle twinkle via alpha modulation
        twinkle = 0.08 + 0.12 * np.abs(np.sin(self._frame * 0.05 +
                                                np.arange(len(px)) * 0.3))
        ax.scatter(px, py, pz, color='#aaddff', s=0.8, alpha=0.15,
                   zorder=0, depthshade=True)

        # ── Communication links (curved arcs with pulse markers) ─────────
        if comms_mesh is not None:
            G = comms_mesh.graph
            amv_pos3d = {a.amv_id: (a.position[0], a.position[1], amv_z(a))
                         for a in amvs}
            for u, v, data in G.edges(data=True):
                if u not in amv_pos3d or v not in amv_pos3d:
                    continue
                plp = data.get('packet_loss_prob', 0.5)
                quality = max(0.05, 1.0 - plp)
                pu, pv = amv_pos3d[u], amv_pos3d[v]

                # Smooth curved arc using quadratic Bezier
                n_pts = 20
                t_arr = np.linspace(0, 1, n_pts)
                # Control point: midpoint pushed deeper
                ctrl = np.array([
                    (pu[0] + pv[0]) / 2,
                    (pu[1] + pv[1]) / 2,
                    min(pu[2], pv[2]) - 18.0  # sag below both endpoints
                ])
                p0, p1 = np.array(pu), np.array(pv)
                arc = np.outer((1-t_arr)**2, p0) + np.outer(2*(1-t_arr)*t_arr, ctrl) + \
                      np.outer(t_arr**2, p1)

                # Link colour by quality
                if quality > 0.6:
                    lc = '#00e5ff'
                elif quality > 0.3:
                    lc = '#ff9800'
                else:
                    lc = '#ff1744'

                ax.plot(arc[:, 0], arc[:, 1], arc[:, 2],
                        color=lc, alpha=quality * 0.5,
                        linewidth=quality * 1.8 + 0.3, linestyle='-')

                # Animated pulse travelling along the link
                pulse_t = (self._frame * 0.04 + u * 0.3) % 1.0
                pulse_idx = int(pulse_t * (n_pts - 1))
                ax.scatter([arc[pulse_idx, 0]], [arc[pulse_idx, 1]],
                           [arc[pulse_idx, 2]],
                           color=lc, s=12, alpha=quality * 0.8,
                           zorder=5, depthshade=False)

        # ── Mission targets — holographic beacons ─────────────────────────
        for task in tasks:
            if task.is_dummy:
                continue
            tx, ty = task.position
            tz = self.FLOOR_Z + 4

            if task.status == 'completed':
                tcolor = '#00e676'; alpha_t = 0.50; glow_r = 12
                beam_alpha = 0.06
            elif task.status == 'active':
                tcolor = '#ffab40'; alpha_t = 0.85; glow_r = 16
                beam_alpha = 0.15
            else:
                tcolor = '#4a7a8a'; alpha_t = 0.65; glow_r = 10
                beam_alpha = 0.08

            # Diamond marker
            verts = _make_target_verts(tx, ty, tz, r=glow_r)
            poly_t = Poly3DCollection(verts, alpha=alpha_t, linewidth=0.2)
            poly_t.set_facecolor(tcolor)
            poly_t.set_edgecolor(tcolor)
            ax.add_collection3d(poly_t)

            # Holographic beam — vertical light column from seabed upward
            beam_h = 35
            beam_angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            beam_r_base = glow_r * 0.8
            beam_r_top = glow_r * 0.3
            for i_b in range(len(beam_angles)):
                a0 = beam_angles[i_b]
                a1 = beam_angles[(i_b + 1) % len(beam_angles)]
                face = [
                    [tx + beam_r_base * np.cos(a0), ty + beam_r_base * np.sin(a0), tz],
                    [tx + beam_r_base * np.cos(a1), ty + beam_r_base * np.sin(a1), tz],
                    [tx + beam_r_top * np.cos(a1), ty + beam_r_top * np.sin(a1), tz + beam_h],
                    [tx + beam_r_top * np.cos(a0), ty + beam_r_top * np.sin(a0), tz + beam_h],
                ]
                beam_poly = Poly3DCollection([face], alpha=beam_alpha, linewidth=0)
                beam_poly.set_facecolor(tcolor)
                beam_poly.set_edgecolor('none')
                ax.add_collection3d(beam_poly)

            # Sonar ping ring (pulsing, expanding circle)
            pulse_r = glow_r * (1 + 0.5 * np.sin(self._frame * 0.2 + task.task_id))
            ring_a  = np.linspace(0, 2 * np.pi, 32)
            ax.plot(tx + pulse_r * np.cos(ring_a),
                    ty + pulse_r * np.sin(ring_a),
                    np.full(32, tz - 1),
                    color=tcolor, alpha=0.25, linewidth=0.6)

            # Second expanding ring (delayed phase)
            pulse_r2 = glow_r * (1 + 0.5 * np.sin(self._frame * 0.2 + task.task_id + np.pi))
            ax.plot(tx + pulse_r2 * np.cos(ring_a),
                    ty + pulse_r2 * np.sin(ring_a),
                    np.full(32, tz - 2),
                    color=tcolor, alpha=0.15, linewidth=0.4)

            # Task ID label
            ax.text(tx, ty, tz + beam_h + 3, f'T{task.task_id}',
                    color=tcolor, fontsize=5.5, fontweight='bold',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15',
                              facecolor='#00000066', edgecolor=tcolor,
                              linewidth=0.4))

        # ── AMV particle wakes (smooth gradient trails) ──────────────────
        for amv_id, trail in self._trails.items():
            if len(trail) < 3:
                continue
            pts = list(trail)
            c  = AMV_COLORS[amv_id % len(AMV_COLORS)]
            gc = AMV_GLOW[amv_id % len(AMV_GLOW)]
            n  = len(pts)

            # Smooth fading trail segments
            for i in range(n - 1):
                seg_alpha = ((i + 1) / n) * 0.45
                lw = 0.5 + (i / n) * 1.5
                ax.plot([pts[i][0], pts[i+1][0]],
                        [pts[i][1], pts[i+1][1]],
                        [pts[i][2], pts[i+1][2]],
                        color=c, alpha=seg_alpha, linewidth=lw)

            # Bubble particles along trail (sparse, drifting upward)
            scatter_idx = list(range(0, n, 5))
            if scatter_idx:
                rng_b = np.random.default_rng(self._frame + amv_id)
                bx = [pts[i][0] + rng_b.uniform(-3, 3) for i in scatter_idx]
                by = [pts[i][1] + rng_b.uniform(-3, 3) for i in scatter_idx]
                bz = [pts[i][2] + rng_b.uniform(1, 8) for i in scatter_idx]
                ba = [(i / n) * 0.3 for i in scatter_idx]
                ax.scatter(bx, by, bz, color=gc, s=3.0, alpha=0.2,
                           zorder=2, depthshade=True)

        # ── Submarine-shaped AUVs with metallic shading ──────────────────
        for amv in amvs:
            cx, cy = amv.position
            cz = amv_z(amv)
            c   = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
            gc  = AMV_GLOW[amv.amv_id % len(AMV_GLOW)]
            dc  = AMV_DARK[amv.amv_id % len(AMV_DARK)]
            fc  = FAULT_COLORS.get(amv.fault_state, '#ffffff')
            hdg = self._headings.get(amv.amv_id, 0.0)

            # Hull geometry — slightly larger for visibility
            faces = _make_sub_verts(cx, cy, cz, length=32, radius=6.5, heading=hdg)
            hull  = Poly3DCollection(faces, alpha=0.92, linewidth=0.15)
            hull.set_facecolor(c)
            hull.set_edgecolor(dc)
            ax.add_collection3d(hull)

            # Ambient glow halo around submarine
            glow_r = 18
            glow_a = np.linspace(0, 2 * np.pi, 28)
            glow_x = cx + glow_r * np.cos(glow_a)
            glow_y = cy + glow_r * np.sin(glow_a)
            glow_z = np.full(28, cz)
            ax.plot(glow_x, glow_y, glow_z,
                    color=gc, alpha=0.15, linewidth=3.0)

            # Fault state warning ring
            if amv.fault_state != 'normal':
                fault_r = 16
                pulse_scale = 1.0 + 0.15 * np.sin(self._frame * 0.3)
                fault_ring_r = fault_r * pulse_scale
                ax.plot(cx + fault_ring_r * np.cos(glow_a),
                        cy + fault_ring_r * np.sin(glow_a),
                        np.full(28, cz),
                        color=fc, alpha=0.6, linewidth=2.0)
                # Second pulse ring
                ax.plot(cx + (fault_ring_r * 1.3) * np.cos(glow_a),
                        cy + (fault_ring_r * 1.3) * np.sin(glow_a),
                        np.full(28, cz),
                        color=fc, alpha=0.25, linewidth=1.0)

            # Headlight beam (cone of light in heading direction)
            beam_len = 40
            beam_spread = 10
            hdg_dx = np.cos(hdg) * beam_len
            hdg_dy = np.sin(hdg) * beam_len
            perp_dx = -np.sin(hdg) * beam_spread
            perp_dy = np.cos(hdg) * beam_spread
            headlight_face = [
                [cx, cy, cz],
                [cx + hdg_dx + perp_dx, cy + hdg_dy + perp_dy, cz + beam_spread * 0.5],
                [cx + hdg_dx - perp_dx, cy + hdg_dy - perp_dy, cz - beam_spread * 0.5],
            ]
            hl_poly = Poly3DCollection([headlight_face], alpha=0.05, linewidth=0)
            hl_poly.set_facecolor(gc)
            hl_poly.set_edgecolor('none')
            ax.add_collection3d(hl_poly)

            # Propeller disc at tail (spinning animation)
            tail_dx = -16 * np.cos(hdg); tail_dy = -16 * np.sin(hdg)
            prop_a  = np.linspace(0, 2 * np.pi, 20)
            prop_r  = 7.5
            spin = self._frame * 0.4 + amv.amv_id
            prop_xs = tail_dx + cx + prop_r * np.sin(hdg + np.pi/2) * np.cos(prop_a + spin)
            prop_ys = tail_dy + cy + prop_r * np.cos(hdg + np.pi/2) * np.cos(prop_a + spin)
            prop_zs = cz + prop_r * np.sin(prop_a + spin)
            ax.plot(prop_xs, prop_ys, prop_zs, color=gc, alpha=0.45, linewidth=0.8)

            # AMV label — clean HUD style
            label_z = cz + 18
            state_abbrev = amv.fsm_state[:3].upper()
            ax.text(cx, cy, label_z,
                    f'AMV{amv.amv_id}\n{int(amv.energy)}%\n{state_abbrev}',
                    color='white', fontsize=6, fontweight='bold',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.25',
                              facecolor='#000000aa',
                              edgecolor=c, linewidth=1.0))

            # Thin depth line to surface (very subtle)
            ax.plot([cx, cx], [cy, cy], [self.SURF_Z, cz],
                    color=c, alpha=0.10, linewidth=0.3, linestyle=':')

            # Assignment line to target
            if (amv.assigned_task is not None
                    and not amv.assigned_task.is_dummy
                    and amv.assigned_task.status != 'completed'):
                tpos = amv.assigned_task.position
                ax.plot([cx, tpos[0]], [cy, tpos[1]], [cz, self.FLOOR_Z + 4],
                        color=gc, alpha=0.30, linewidth=0.6, linestyle='--')

        # ── Axes & labels ────────────────────────────────────────────────
        ax.set_xlim(0, M); ax.set_ylim(0, M)
        ax.set_zlim(self.FLOOR_Z - 8, self.SURF_Z + 5)
        ax.set_xlabel('East (m)',  color='#3a7ab8', fontsize=7.5, labelpad=8)
        ax.set_ylabel('North (m)', color='#3a7ab8', fontsize=7.5, labelpad=8)
        ax.set_zlabel('Depth',     color='#3a7ab8', fontsize=7.5, labelpad=6)

        # Custom Z tick labels
        z_ticks = np.arange(self.FLOOR_Z, 5, 30)
        ax.set_zticks(z_ticks)
        ax.set_zticklabels([f'{int(-z)}m' for z in z_ticks],
                           color='#3a7ab8', fontsize=5.5)

        # Smooth cinematic camera orbit
        self._azim += 0.10
        ax.view_init(elev=24, azim=self._azim)

        # Mission title bar
        tasks_done  = sum(1 for t in tasks if t.status == 'completed')
        tasks_total = sum(1 for t in tasks if not t.is_dummy)
        ax.set_title(
            f'  T={timestep:>4}/{config.SIMULATION_TIMESTEPS}   '
            f'│  Tasks {tasks_done}/{tasks_total}   '
            f'│  Deadlocks {deadlock_count}   '
            f'│  mt={mt}',
            color='#c0e0ff', fontsize=9.5, fontweight='bold', pad=8,
            loc='left',
            fontfamily='monospace')

        # ── HUD panels ───────────────────────────────────────────────────
        self._draw_hud_energy(amvs)
        self._draw_hud_fault(amvs)
        self._draw_hud_tasks(tasks)
        self._draw_hud_comms(amvs, comms_mesh)
        self._draw_hud_depth(amvs)
        self._draw_hud_legend()

        # ── Render ───────────────────────────────────────────────────────
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.001)

    # ─────────────────────────────────────────────────────────────────────────
    # HUD helper panels
    # ─────────────────────────────────────────────────────────────────────────
    def _hud_clear(self, ax, title):
        ax.cla()
        ax.set_facecolor('#060d1a')
        ax.set_title(title, color='#70b8e8', fontsize=7.5, fontweight='bold', pad=4)
        for spine in ax.spines.values():
            spine.set_edgecolor('#0f2a4a')
            spine.set_linewidth(0.5)
        ax.tick_params(colors='#3a7ab8', labelsize=5.5)

    def _draw_hud_energy(self, amvs):
        ax = self.ax_hud_energy
        self._hud_clear(ax, 'Energy Levels')
        n = len(amvs)
        for i, amv in enumerate(amvs):
            c  = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
            pct = amv.energy / 100.0
            # Gradient bar color based on energy level
            if pct > 0.6:
                bar_c = '#00e676'
            elif pct > 0.35:
                bar_c = '#ffd740'
            elif pct > 0.15:
                bar_c = '#ff9800'
            else:
                bar_c = '#ff1744'

            # Background bar
            ax.barh(i, 1.0, color='#0a1520', height=0.55, alpha=0.6)
            # Energy bar
            ax.barh(i, pct, color=bar_c, height=0.55, alpha=0.85)
            # Glow edge
            ax.barh(i, pct, color=bar_c, height=0.55, alpha=0.15,
                    edgecolor=bar_c, linewidth=0.8)

            ax.text(max(pct + 0.02, 0.08), i, f'{amv.energy:.0f}%',
                    color='white', fontsize=6, va='center')
            ax.text(-0.02, i, f'AMV{amv.amv_id}', color=c,
                    fontsize=6, va='center', ha='right', fontweight='bold')
        ax.set_xlim(0, 1.25); ax.set_ylim(-0.6, n - 0.4)
        ax.set_xticks([]); ax.set_yticks([])

    def _draw_hud_fault(self, amvs):
        ax = self.ax_hud_fault
        self._hud_clear(ax, 'Fault States')
        for i, amv in enumerate(amvs):
            fc = FAULT_COLORS.get(amv.fault_state, '#ffffff')
            c  = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
            label = amv.fault_state.replace('_', ' ')
            # Status indicator dot
            ax.plot(0.08, i, 'o', color=fc, markersize=5, alpha=0.9,
                    transform=ax.transData)
            ax.text(0.15, i, f'AMV{amv.amv_id}', color=c,
                    fontsize=6, va='center', ha='left', fontweight='bold',
                    transform=ax.transData)
            ax.text(0.92, i, label, color=fc,
                    fontsize=5.5, va='center', ha='right',
                    transform=ax.transData)
            ax.axhline(i - 0.5, color='#0f2a4a', linewidth=0.3, alpha=0.5)
        ax.set_xlim(0, 1); ax.set_ylim(-0.5, len(amvs) - 0.5)
        ax.set_xticks([]); ax.set_yticks([])

    def _draw_hud_tasks(self, tasks):
        ax = self.ax_hud_tasks
        self._hud_clear(ax, 'Mission Tasks')
        real_tasks = [t for t in tasks if not t.is_dummy]
        col_w = [0.12, 0.35, 0.28, 0.25]
        headers = ['ID', 'Status', 'Quality', 'Priority']
        for ci, (h, x) in enumerate(zip(headers, np.cumsum([0] + col_w))):
            ax.text(x + col_w[ci] * 0.5, len(real_tasks) + 0.3, h,
                    color='#70b8e8', fontsize=5.5, fontweight='bold',
                    ha='center', va='center', transform=ax.transData)
        for i, t in enumerate(reversed(real_tasks)):
            row_y = i
            sc = '#00e676' if t.status == 'completed' else (
                 '#ffab40' if t.status == 'active' else '#4a7a8a')
            qc = '#00e676' if t.completion_quality == 'completed_clean' else (
                 '#ff9800' if t.completion_quality == 'completed_degraded' else '#4a7a8a')
            q_str = (t.completion_quality or '—').replace('completed_', '')
            cells = [f'T{t.task_id}', t.status, q_str, f'{t.priority_weight:.2f}']
            colors = ['#c0e0ff', sc, qc, '#7ab0d0']
            for ci, (cell, cc, x) in enumerate(zip(cells, colors, np.cumsum([0]+col_w))):
                ax.text(x + col_w[ci] * 0.5, row_y, cell,
                        color=cc, fontsize=5.5, ha='center', va='center',
                        transform=ax.transData)
            # Subtle row divider
            if i > 0:
                ax.axhline(row_y - 0.5, color='#0f2a4a', linewidth=0.2, alpha=0.4)
        ax.set_xlim(0, 1); ax.set_ylim(-0.5, len(real_tasks) + 0.8)
        ax.set_xticks([]); ax.set_yticks([])

    def _draw_hud_comms(self, amvs, comms_mesh):
        ax = self.ax_hud_comms
        self._hud_clear(ax, 'Acoustic Links')
        if comms_mesh is None:
            ax.text(0.5, 0.5, 'No data', color='#3a7ab8', ha='center',
                    va='center', transform=ax.transAxes, fontsize=7)
            return
        G = comms_mesh.graph
        edges = list(G.edges(data=True))
        if not edges:
            ax.text(0.5, 0.5, 'No links', color='#3a7ab8', ha='center',
                    va='center', transform=ax.transAxes, fontsize=7)
            return
        for i, (u, v, data) in enumerate(edges[:10]):
            plp   = data.get('packet_loss_prob', 0.5)
            quality = 1.0 - plp
            if quality > 0.6:
                lc = '#00e5ff'
            elif quality > 0.3:
                lc = '#ff9800'
            else:
                lc = '#ff1744'
            # Background bar
            ax.barh(i, 1.0, color='#0a1520', height=0.45, alpha=0.5)
            ax.barh(i, quality, color=lc, height=0.45, alpha=0.75)
            ax.text(-0.02, i, f'{u}↔{v}', color='#7ab0d0', fontsize=5,
                    va='center', ha='right')
            ax.text(quality + 0.02, i, f'{quality:.0%}', color=lc,
                    fontsize=5, va='center')
        ax.set_xlim(0, 1.3); ax.set_ylim(-0.5, min(10, len(edges)) - 0.5)
        ax.set_xticks([]); ax.set_yticks([])

    def _draw_hud_depth(self, amvs):
        ax = self.ax_hud_depth
        self._hud_clear(ax, 'Depth Profile')
        for amv in amvs:
            c = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
            depth = getattr(amv, 'depth', 30.0)
            # Background
            ax.barh(amv.amv_id, config.DEPTH_MAX, color='#0a1520',
                    height=0.45, alpha=0.5)
            ax.barh(amv.amv_id, depth, color=c, height=0.45, alpha=0.75)
            ax.text(depth + 2, amv.amv_id, f'{depth:.0f}m',
                    color='white', fontsize=5.5, va='center')
        # Thermocline reference
        thermo = config.THERMOCLINE_DEPTH
        ax.axvline(thermo, color='#00b4d8', linewidth=1.0, linestyle='--', alpha=0.5)
        ax.text(thermo + 1, len(amvs) - 0.3, 'Thermo',
                color='#00b4d8', fontsize=5, va='top')
        ax.set_xlim(0, config.DEPTH_MAX + 20)
        ax.set_ylim(-0.5, len(amvs) - 0.4)
        ax.set_xticks([]); ax.set_yticks([])

    def _draw_hud_legend(self):
        ax = self.ax_hud_legend
        self._hud_clear(ax, '')
        ax.set_facecolor('#030810')
        items = [
            ('AMV Submarine', '#00C6FF', 'o'),
            ('Task (Unassigned)', '#4a7a8a', 'D'),
            ('Task (Active)', '#ffab40', 'D'),
            ('Task (Completed)', '#00e676', 'D'),
            ('Normal', '#00E676', 's'),
            ('Actuator Mild', '#FFD740', 's'),
            ('Actuator Severe', '#FF6D00', 's'),
            ('Sensor Fail', '#FF1744', 's'),
            ('Load Fault', '#AA00FF', 's'),
            ('Comm Good', '#00e5ff', '-'),
            ('Comm Degraded', '#ff9800', '--'),
            ('Thermocline', '#005577', ':'),
        ]
        n = len(items)
        cols = 4
        rows = (n + cols - 1) // cols
        for idx, (label, color, marker) in enumerate(items):
            col = idx % cols
            row = idx // cols
            x = col / cols + 0.01
            y = 1.0 - (row + 0.6) / rows
            ax.plot([x, x + 0.035], [y, y], color=color, linewidth=2.5,
                    transform=ax.transAxes, clip_on=False, alpha=0.8)
            ax.text(x + 0.045, y, label, color='#90b8d8', fontsize=5.5,
                    va='center', transform=ax.transAxes)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.set_xticks([]); ax.set_yticks([])
        ax.axis('off')

    # ─────────────────────────────────────────────────────────────────────────

    def close(self):
        """Hold final frame 3 s, then tear down the interactive window."""
        try:
            plt.pause(3.0)
        except Exception:
            pass
        plt.close(self.fig)
        plt.ioff()
        matplotlib.use('Agg')
