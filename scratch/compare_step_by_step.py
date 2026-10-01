import sys, os, io
sys.path.insert(0, '.')
import random, torch, numpy as np, pickle, pandas as pd
import config, main, simulation, consensus, comms
from symbolic_rules import SymbolicRuleEngine

def run_step_by_step():
    # Let's compare two simulations step by step
    # 1. Initialize simulation with openset OFF
    # 2. Initialize simulation with openset ON (threshold 70.0)
    pass
