import sys
import numpy as np

sys.path.append(".")
import config
import main
import consensus

def find_rule3_target_t300():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = [] 
    config.SPOOF_MESSAGES = []
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False

    class InspectException(Exception):
        def __init__(self, amvs, tasks):
            self.amvs = amvs
            self.tasks = tasks
            super().__init__()

    old_auction = consensus.MieleConsensus.run_auction_round
    def mock_run_auction_round(self, amvs, tasks, comms, current_timestep):
        if current_timestep == 300:
            raise InspectException(amvs, tasks)
        return old_auction(self, amvs, tasks, comms, current_timestep)
        
    consensus.MieleConsensus.run_auction_round = mock_run_auction_round
    
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        main.main()
    except InspectException as ie:
        sys.stdout = old_stdout
        print("INTERCEPTED AT t=300")
        amvs = ie.amvs
        tasks = ie.tasks
        
        # Get AMV1 and AMV4
        amv1 = [a for a in amvs if a.amv_id == 1][0]
        amv4 = [a for a in amvs if a.amv_id == 4][0]
        
        print(f"AMV1 energy={amv1.energy:.2f}%, pos={amv1.position}")
        print(f"AMV4 energy={amv4.energy:.2f}%, pos={amv4.position}")
        
        from symbolic_rules import SymbolicRuleEngine
        re = SymbolicRuleEngine()
        
        unassigned_tasks = [t for t in tasks if t.status == 'unassigned' and not t.is_dummy]
        print(f"Unassigned tasks: {[t.task_id for t in unassigned_tasks]}")
        
        print("\nSafety Checks for Unassigned Tasks at t=300:")
        for t in unassigned_tasks:
            # Check AMV1
            v1 = re.evaluate_pre_assignment(amv1, t, amvs, len(unassigned_tasks))
            r1_allowed = all(v.allowed for v in v1)
            r1_reasons = [v.reason for v in v1 if not v.allowed]
            
            # Check AMV4
            v4 = re.evaluate_pre_assignment(amv4, t, amvs, len(unassigned_tasks))
            r4_allowed = all(v.allowed for v in v4)
            r4_reasons = [v.reason for v in v4 if not v.allowed]
            
            print(f"Task {t.task_id} pos={t.position}:")
            print(f"  AMV1: allowed={r1_allowed}, reasons={r1_reasons}")
            print(f"  AMV4: allowed={r4_allowed}, reasons={r4_reasons}")
    finally:
        sys.stdout = old_stdout

if __name__ == "__main__":
    find_rule3_target_t300()
