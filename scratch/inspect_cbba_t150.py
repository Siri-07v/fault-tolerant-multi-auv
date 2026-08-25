import sys
import os

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main
import cbba

def patch_and_run():
    print("=== Intercepting CBBA at t=150 ===")
    # Configure for CBBA Nominal scenario
    config.ALLOCATOR_MODE = "cbba"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = []
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    
    old_run = cbba.CBBAAllocator.run_auction_round
    
    def mock_run_auction_round(self, amvs, tasks, comms_mesh, current_timestep):
        if current_timestep == 150:
            print("\n=== CBBA Task States at t=150 ===")
            
            # Count task states
            completed = [t.task_id for t in tasks if t.status == "completed"]
            active = [t.task_id for t in tasks if t.status == "active"]
            unassigned = [t.task_id for t in tasks if t.status == "unassigned" and not t.is_dummy]
            
            print(f"Completed tasks ({len(completed)}): {completed}")
            print(f"Active/Locked tasks ({len(active)}): {active}")
            print(f"Unassigned/Contestable tasks ({len(unassigned)}): {unassigned}")
            
            # Print each AMV assignment and its state
            for amv in amvs:
                assign = amv.assigned_task
                tid = assign.task_id if assign else None
                print(f"  AMV{amv.amv_id} FSM state: {amv.fsm_state} | Assigned: {tid}")
                
            print("=================================\n")
            sys.exit(0) # Exit early after printing
            
        return old_run(self, amvs, tasks, comms_mesh, current_timestep)
        
    cbba.CBBAAllocator.run_auction_round = mock_run_auction_round
    
    try:
        main.main()
    except SystemExit:
        pass

if __name__ == "__main__":
    patch_and_run()
