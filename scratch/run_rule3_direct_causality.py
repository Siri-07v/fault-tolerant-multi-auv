import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus

def run_direct_rule3_causality():
    # Setup nominal run state to analyze
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    
    # Configure spoofing
    config.SPOOF_MESSAGES = ["auction"]
    config.SPOOF_MODE = "corrupt_payload"
    config.SPOOFED_TASK_ID = 9
    config.COMPROMISED_AMVS = [1]
    config.BYZANTINE_MODE = "mask_fault_state"

    import security.trust
    import importlib
    importlib.reload(security.trust)

    # Patch run_auction_round to inject state overrides at t=100
    old_auction = consensus.MieleConsensus.run_auction_round
    def mock_run_auction_round(self, amvs, tasks, comms, current_timestep):
        if current_timestep == 100:
            amv1 = [a for a in amvs if a.amv_id == 1][0]
            # Override energy to be low (21%) to trigger energy floor violation for Task 9
            amv1.energy = 21.0
            # Force AMV1 to be in Assignment seeking state
            if amv1.assigned_task is not None:
                amv1.assigned_task.status = "unassigned"
                amv1.assigned_task.assigned_to = None
                amv1.assigned_task = None
            amv1.enter_assignment()
            
            print(f"\n[INJECT STATE DEVIATION] t=100: Force AMV1 energy=21.0%, state=Assignment, target spoof Task 9")
            
        return old_auction(self, amvs, tasks, comms, current_timestep)
        
    consensus.MieleConsensus.run_auction_round = mock_run_auction_round

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    try:
        main.main()
    finally:
        sys.stdout = old_stdout
        
    print("LOG OUTCOME OF DIRECT RULE 3 CAUSALITY RUN:")
    lines = mystdout.getvalue().split("\n")
    
    # Filter lines between t=95 and t=120 to show the exact sequence of events
    show_logs = False
    for line in lines:
        if "t=100" in line:
            show_logs = True
        if "t=120" in line:
            show_logs = False
        if show_logs or any(k in line.lower() for k in ("stripped of t9", "rule:energy_floor | veto", "screened")):
            # Don't print spam of other vehicles if not relevant
            if "byzantine targeted" in line.lower() or "stripped" in line.lower() or "veto" in line.lower() or "screened" in line.lower() or "inject state deviation" in line.lower():
                print(line)

if __name__ == "__main__":
    run_direct_rule3_causality()
