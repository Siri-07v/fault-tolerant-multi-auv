import sys
import io
import numpy as np

sys.path.append(".")
import config
import main

out_lines = []

def log_print(msg):
    out_lines.append(msg)

def run_causality_analysis():
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "mass_fault"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.TRUST_THRESHOLD = 0.4
    config.TRUST_DECAY_RATE = 0.3
    config.ACOUSTIC_RANGE_SURFACE = 600
    config.ACOUSTIC_RANGE_DEEP = 400
    
    # Enable Case 1 corrupt_payload
    config.SPOOF_MESSAGES = ["auction"]
    config.SPOOF_MODE = "corrupt_payload"
    config.COMPROMISED_AMVS = [1]
    
    import security.trust
    import importlib
    importlib.reload(security.trust)
    
    old_is_safe = main.SymbolicRuleEngine.is_assignment_safe
    
    def mock_is_assignment_safe(self, amv, task, all_amvs, remaining_tasks=15):
        res = old_is_safe(self, amv, task, all_amvs, remaining_tasks)
        amv_id = getattr(amv, "amv_id", -1)
        task_id = getattr(task, "task_id", -1)
        
        pos = getattr(amv, "estimated_position", amv.position)
        task_pos = getattr(task, "position", None)
        dist = np.linalg.norm(pos - task_pos) if task_pos is not None else 0.0
        energy_needed = dist * 0.05
        energy = getattr(amv, "energy", 100.0)
        
        t = len(getattr(amv, "fsm_history", []))
        if amv_id == 1 and task_id in (3, 5, 8, 7):
            log_print(f"  [CAUSALITY TRACE] t={t}: AMV1 checked for Task {task_id}: dist={dist:.1f}m, energy={energy:.1f}%, needed={energy_needed:.1f}%, safe={res}")
        return res
        
    main.SymbolicRuleEngine.is_assignment_safe = mock_is_assignment_safe
    
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    try:
        main.main()
    finally:
        sys.stdout = old_stdout
        
    for line in mystdout.getvalue().split("\n"):
        line_l = line.lower()
        if any(k in line_l for k in ("veto", "screened", "stripped", "causality trace", "outbid")):
            log_print(line)

if __name__ == "__main__":
    run_causality_analysis()
    with open("C:/Users/siri0/.gemini/antigravity-ide/brain/1f972419-47ac-4dc7-951b-62447b741553/scratch/causality.log", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
