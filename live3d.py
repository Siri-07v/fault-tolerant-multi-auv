"""
live3d.py — Real-time 3D interactive visualization for the AMV swarm simulation.
Opens a persistent matplotlib window and updates it every timestep.
"""
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import numpy as np
from collections import deque

import config

# AMV color palette (same as visualize.py)
AMV_COLORS = ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0']


class LiveSimulation3D:
    """Real-time 3D space-time visualization of the AMV swarm."""

    def __init__(self):
        plt.ion()
        self.fig = plt.figure(figsize=(19, 10))
        self.fig.canvas.manager.set_window_title('AMV Swarm — Live 3D Simulation')
        self.fig.patch.set_facecolor('#E8F4FD')
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.fig.subplots_adjust(left=0, right=1, top=0.92, bottom=0)
        self.ax.set_facecolor('#D6EAF8')

        # Fullscreen
        try:
            manager = plt.get_current_fig_manager()
            manager.window.state('zoomed')       # Windows fullscreen
        except Exception:
            try:
                manager.full_screen_toggle()     # Linux/Mac fallback
            except Exception:
                pass

        # Trail buffers — last 30 positions per AMV
        self._trails = {}          # {amv_id: deque([(x, y, t), ...])}
        self._trail_len = 30

        # Force an initial draw
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    # ─────────────────────────────────────────────────────────────────────────

    def update(self, timestep, amvs, tasks, comms_mesh, mt, deadlock_count):
        """Redraw the full 3D scene. Called once per simulation timestep."""
        ax = self.ax
        ax.cla()
        ax.set_facecolor('#D6EAF8')

        n_timesteps = config.SIMULATION_TIMESTEPS

        # ── Update trails ────────────────────────────────────────────────────
        for amv in amvs:
            if amv.amv_id not in self._trails:
                self._trails[amv.amv_id] = deque(maxlen=self._trail_len)
            self._trails[amv.amv_id].append(
                (amv.position[0], amv.position[1], timestep))

        # ── Draw trajectory trails ───────────────────────────────────────────
        for amv_id, trail in self._trails.items():
            if len(trail) < 2:
                continue
            xs = [p[0] for p in trail]
            ys = [p[1] for p in trail]
            zs = [p[2] for p in trail]
            c = AMV_COLORS[amv_id % len(AMV_COLORS)]
            ax.plot(xs, ys, zs, color=c, alpha=0.4, linewidth=1.2)

        # ── Draw tasks ───────────────────────────────────────────────────────
        for task in tasks:
            if task.is_dummy:
                continue
            if task.status == "completed":
                color = '#4CAF50'
            elif task.status == "active":
                color = '#FF9800'
            else:
                color = '#9E9E9E'
            ax.scatter(task.position[0], task.position[1], 0,
                       color=color, marker='s', s=60, edgecolors='black',
                       linewidths=0.5, alpha=0.8, zorder=3)

        # ── Draw communication links ─────────────────────────────────────────
        if comms_mesh is not None:
            G = comms_mesh.graph
            pos = {n: G.nodes[n].get("pos", (0, 0)) for n in G.nodes()}
            for u, v, data in G.edges(data=True):
                plp = data.get("packet_loss_prob", 0.5)
                quality = 1.0 - plp
                if u in pos and v in pos:
                    ax.plot([pos[u][0], pos[v][0]],
                            [pos[u][1], pos[v][1]],
                            [timestep, timestep],
                            color='#90CAF9', alpha=max(0.15, quality * 0.7),
                            linewidth=max(0.3, quality * 2.0))

        # ── Draw AMV positions ───────────────────────────────────────────────
        for amv in amvs:
            c = AMV_COLORS[amv.amv_id % len(AMV_COLORS)]
            ax.scatter(amv.position[0], amv.position[1], timestep,
                       color=c, marker='^', s=120, edgecolors='black',
                       linewidths=1, zorder=5)
            # Energy label — clean short percentage, white text above marker
            ax.text(amv.position[0], amv.position[1] + 15, timestep + 3,
                    f'{int(amv.energy)}%', fontsize=6, color='white',
                    fontweight='bold', ha='center')

        # ── Axis setup ───────────────────────────────────────────────────────
        ax.set_xlim(0, 1000)
        ax.set_ylim(0, 1000)
        ax.set_zlim(0, n_timesteps)
        ax.set_xlabel('X (m)', labelpad=8, fontsize=9)
        ax.set_ylabel('Y (m)', labelpad=8, fontsize=9)
        ax.set_zlabel('Timestep', labelpad=8, fontsize=9)
        ax.view_init(elev=25, azim=-60 + timestep * 0.1)

        # ── Status title ─────────────────────────────────────────────────────
        tasks_done = sum(1 for t in tasks if t.status == 'completed')
        ax.set_title(
            f't={timestep}/{n_timesteps}  │  Tasks: {tasks_done}/{config.N_TASKS}  '
            f'│  Deadlocks: {deadlock_count}  │  mt={mt}',
            fontsize=11, fontweight='bold', pad=15)

        # ── Render ───────────────────────────────────────────────────────────
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.01)

    # ─────────────────────────────────────────────────────────────────────────

    def close(self):
        """Hold the final view for 3 seconds, then close and switch to Agg."""
        try:
            plt.pause(3.0)
        except Exception:
            pass
        plt.close(self.fig)
        plt.ioff()
        matplotlib.use("Agg")
