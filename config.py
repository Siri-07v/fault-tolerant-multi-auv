"""
config.py — Central configuration for the AUV swarm simulation project.
All tunable constants are defined here; no hardcoded values elsewhere.
"""
import os

# ─── Dataset ───────────────────────────────────────────────────────────────────
DATASET_PATH = os.path.join("Dataset", "Dataset", "train")
SCALER_PATH = "scaler.pkl"
MODEL_PATH = "fault_classifier_best.pt"

FAULT_LABEL_MAP = {
    "Normal": ("normal", 0),
    "AddWeight": ("load_fault", 1),
    "PressureGain_constant": ("sensor_failure", 2),
    "PropellerDamage_bad": ("actuator_degraded_severe", 3),
    "PropellerDamage_slight": ("actuator_degraded_mild", 4),
}

INDEX_TO_LABEL = {v[1]: v[0] for v in FAULT_LABEL_MAP.values()}
LABEL_NAMES = [INDEX_TO_LABEL[i] for i in range(5)]

SENSOR_COLUMNS = ["depth", "w_row", "w_pitch", "w_yaw", "a_x", "a_y", "a_z"]

# ─── Preprocessing ─────────────────────────────────────────────────────────────
WINDOW_SIZE = 50
STRIDE = 10
TRAIN_SPLIT = 0.70
VAL_SPLIT = 0.15
TEST_SPLIT = 0.15

# ─── Training ──────────────────────────────────────────────────────────────────
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
MAX_EPOCHS = 100
EARLY_STOPPING_PATIENCE = 10
LR_SCHEDULER_PATIENCE = 5

# ─── Simulation ────────────────────────────────────────────────────────────────
N_AMVS = 5
N_TASKS = 15
MISSION_SPACE = 1000          # meters
SIMULATION_TIMESTEPS = 500
FAULT_UPDATE_INTERVAL = 10    # timesteps
TASK_COMPLETION_RADIUS = 15.0  # meters
ENERGY_INIT_MIN = 80
ENERGY_INIT_MAX = 100
ENERGY_MOVE_COST = 0.1
ENERGY_TASK_COST = 0.5
ENERGY_REALLOC_THRESHOLD = 15

# Speed per fault state (m/timestep)
SPEED = {
    "normal": 5.0,
    "actuator_degraded_mild": 3.0,
    "actuator_degraded_severe": 1.5,
    "sensor_failure": 1.5,
    "load_fault": 4.0,
}

# Availability per fault state
AVAILABILITY = {
    "normal": 1.0,
    "actuator_degraded_mild": 0.65,
    "actuator_degraded_severe": 0.25,
    "sensor_failure": 0.1,
    "load_fault": 0.5,
}

# ─── Comms ──────────────────────────────────────────────────────────────────────
ACOUSTIC_RANGE = 3000         # meters
SOUND_SPEED = 1500            # m/s
TIMESTEP_DURATION_MS = 100
GRAPH_REBUILD_INTERVAL = 10

# ─── Bidding weights ───────────────────────────────────────────────────────────
BID_W1 = 0.4   # distance
BID_W2 = 0.3   # energy
BID_W3 = 0.3   # availability
BID_AVAILABILITY_THRESHOLD = 0.25
PRIORITY_WEIGHT_MIN = 0.5
PRIORITY_WEIGHT_MAX = 1.5

# ─── CBBA (legacy, kept for reference) ──────────────────────────────────────────
MAX_CONSENSUS_ITERATIONS = 10
ALLOCATOR_MODE = "auction"  # "auction" | "cbba" | "vanilla_auction"
SAVE_PLOTS = True



# ─── Miele et al. benefit function parameters ──────────────────────────────────
BENEFIT_A = 0.15            # sigmoid steepness (shallower = more bidding competition)
BENEFIT_B = 300.0           # sigmoid midpoint (meters, scaled for 1000m space)
BENEFIT_EPSILON_A = 0.001   # auction price increment — slower conflict resolution
BENEFIT_TW = 40             # max waiting time before priority term activates (timesteps)
TASK_DWELL_TIME = 8         # timesteps AMV spends serving before task completes
MAX_AUCTION_ITERATIONS = 6  # fewer iterations, more unresolved conflicts
EDMC_RESET_ON_ASSIGNMENT = True
DEADLOCK_TIMEOUT = 30

# ─── FSM state names ───────────────────────────────────────────────────────────
FSM_HOMING = "Homing"
FSM_ASSIGNMENT = "Assignment"
FSM_REACHING = "Reaching"
FSM_SERVING = "Serving"
FSM_IDLE = "Idle"
FSM_DEADLOCK = "Deadlock"

# ─── Physics / Ocean Environment ───────────────────────────────────────────────
DEPTH_MIN = 10.0              # meters — shallowest operating depth
DEPTH_MAX = 150.0             # meters — deepest operating depth
AMV_VOLUME = 0.05             # m³ — vehicle displaced volume
AMV_MASS = 52.0               # kg — vehicle dry mass
THERMOCLINE_DEPTH = 80.0      # meters — centre of thermocline transition
THERMOCLINE_WIDTH = 20.0      # meters — sigmoid transition width
SURFACE_TEMP = 28.0           # °C
DEEP_TEMP = 4.0               # °C
SALINITY = 35.0               # PSU (practical salinity units)
DRAG_INFLUENCE = 0.05         # fraction of current added to movement
DEPTH_FAULT_ESCALATION_PROB = 0.008  # per-timestep chance at high pressure

# ─── Depth-aware Communications ────────────────────────────────────────────────
ACOUSTIC_RANGE_SURFACE = 600   # meters at surface
ACOUSTIC_RANGE_DEEP = 400      # meters at 150m depth
THERMOCLINE_PENALTY = 0.15     # extra packet loss across thermocline
EPSILON_LAMBDA = 0.05          # algebraic connectivity threshold

# ─── Live 3D Visualization ─────────────────────────────────────────────────────
LIVE_VIZ_ENABLED = True

# ─── Idle Energy Drain ────────────────────────────────────────────────────────
IDLE_ENERGY_DRAIN = 0.01       # percent per timestep for onboard systems

# ─── Patrol Behavior ─────────────────────────────────────────────────────────
FSM_PATROL = "Patrol"
PATROL_SPEED_FRACTION = 0.4    # fraction of normal speed in patrol mode
PATROL_RADIUS = 50.0           # meters — orbit radius if all tasks complete

# ─── Dynamic Task Respawn ─────────────────────────────────────────────────────
DYNAMIC_TASK_RESPAWN = False
N_RESPAWN_TASKS = 5            # number of new tasks to spawn per batch

# ─── DVL Navigation Drift ─────────────────────────────────────────────────────
DVL_DRIFT_RATE = 0.12          # meters of drift per meter traveled (12% DVL error)
DVL_FAULT_DRIFT_MULTIPLIER = 8.0  # drift multiplier when sensor_failure active
DVL_RESET_ON_SURFACE = True    # drift resets at <10m depth (simulated GPS fix)

# ─── Misclassification Injection ──────────────────────────────────────────
INJECT_MISCLASSIFICATION = False
MISCLASSIFICATION_TARGET_AMV = 1

# ─── Stress Testing ──────────────────────────────────────────────────────
STRESS_SCENARIO = 'none'       # options: 'none', 'amv_loss', 'comm_blackout', 'mass_fault'
STRESS_START_TIMESTEP = 150
STRESS_END_TIMESTEP = 300

# ─── Acoustic Bandwidth Constraint ───────────────────────────────────────
MAX_MESSAGES_PER_LINK = 5

# ─── Fixed Seed (set to None for time-based, or an int for deterministic) ─
FIXED_SEED = None

# ─── Telemetry Logging ──────────────────────────────────────────────────
TELEMETRY_LOG_PATH = None

# ─── Security / Adversarial Settings ───────────────────────────────────────
COMPROMISED_AMVS = []  # List of AMV IDs that are compromised
BYZANTINE_MODE = None  # Options: None, "inflate_priority", "mask_fault_state"

# TrustScore Settings
TRUST_UPDATE_INTERVAL = 10
TRUST_DECAY_RATE = 0.3
TRUST_THRESHOLD = 0.4
TRUST_TOLERANCE = 0.30  # ±30% speed deviation tolerance

# Message Integrity Spoofing / Tampering
SPOOF_MESSAGES = []  # List of message types (e.g. ["auction"]) or link tuples (e.g. [(1, 2)]) to spoof
SPOOF_MODE = None  # None | "corrupt_payload" | "bypass_checksum"
SPOOFED_TASK_ID = None  # Optional task ID to force in spoofed auction bids

# GPS Spoofing / Tampering at Surface
GPS_SPOOF_ENABLED = False
GPS_SPOOF_OFFSET = (0.0, 0.0)  # (dx, dy) in meters
GPS_SANITY_THRESHOLD = 30.0    # maximum allowed discrepancy between GPS and DVL estimate (meters)



