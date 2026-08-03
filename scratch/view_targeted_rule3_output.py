import sys
import io

sys.path.append(".")
import config
import main
import consensus

def view_output():
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
            amv1.energy = 21.0
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
        
    lines = mystdout.getvalue().split("\n")
    
    filtered_lines = []
    # Print lines around t=100 specifically
    print_lines = False
    for line in lines:
        if "t=100" in line or "[T=100]" in line:
            print_lines = True
        if "t=106" in line or "[T=106]" in line:
            print_lines = False
        if print_lines or any(k in line for k in ("stripped of T9", "Rule:energy_floor | VETO")):
            # Don't print byzantine mask logs to avoid spam
            if "byzantine mask" not in line.lower():
                filtered_lines.append(line)
                
    with open("C:/Users/siri0/.gemini/antigravity-ide/brain/1f972419-47ac-4dc7-951b-62447b741553/scratch/rule3_outcome.log", "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines))

if __name__ == "__main__":
    view_output()
