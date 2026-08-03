import sys
import numpy as np

sys.path.append(".")
import config
import main

# Run a baseline simulation and inspect task positions and AMV energy/distance at t=150
config.ALLOCATOR_MODE = "auction"
config.STRESS_SCENARIO = "mass_fault"
config.FIXED_SEED = 42
config.COMPROMISED_AMVS = [] # Run clean first to inspect
config.SPOOF_MESSAGES = []
config.LIVE_VIZ_ENABLED = False
config.SAVE_PLOTS = False

# We will intercept at t=150
# Let's write a custom step runner or run main.main() and check the state.
# Actually, let's write a script that runs the simulation up to t=150,
# and prints out the positions of AMVs and unassigned tasks, and their energy needs.

def inspect_state_at_150():
    # Let's run a modified main loop
    import main
    # We will hook into the simulation
    # To do this easily, let's mock main.main to run up to t=150 and print data
    # Or just run the setup and step through it.
    pass

if __name__ == "__main__":
    # Let's write a script to inspect distances at t=150.
    # To do this, we can run main.main but intercept stdout, or just write a small script that
    # sets up the simulator and runs 150 steps.
    import main
    import io
    
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    try:
        # Run main and get the simulator or final result
        # To get the state, we can modify main to return the simulator or we can run step-by-step
        res = main.main()
    finally:
        sys.stdout = old_stdout
        
    print("Tasks at end of clean run:")
    for t in res["tasks"]:
        if not t.is_dummy:
            print(f"  Task {t.task_id} position: {t.position}")
            
    print("\nAMV states at end of clean run:")
    for a in res["amvs"]:
        print(f"  AMV {a.amv_id} final pos: {a.position}, energy: {a.energy:.2f}")
