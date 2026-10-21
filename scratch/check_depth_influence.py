import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main
import torch
import numpy as np
import pickle

with open(config.SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

# Let's inspect what happens in main.py by adding a print when _m_dist > 15.0 in main.py
# Or let's see why AMV0 in trace_amv_dist was <14.0 but in main.py was 26.18!
# What is the difference between trace_amv_dist and main.py?
# In main.py:
# Does AMV depth change? YES! amv.move_toward_task calls amv._update_dive_profile() which changes amv.depth!
# Does amv.depth change the sensor buffer?
# WAIT! Does amv.depth affect sensor_buffer?
# Let's check where amv.depth is used in simulation.py!
