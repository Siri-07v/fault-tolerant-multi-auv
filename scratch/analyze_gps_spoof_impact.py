import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def run_and_analyze(spoof, offset, case_name):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = spoof
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = 99999.0  # unmitigated

    import security.trust
    import importlib
    importlib.reload(security.trust)

    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    main_output = main.main()
    sys.stdout = old_stdout
    
    amv1 = [a for a in main_output["amvs"] if a.amv_id == 1][0]
    
    # Analyze tasks completed by AMV1
    completed_tasks = amv1.tasks_completed.copy()
    
    # Calculate navigation error at end
    final_error = float(np.linalg.norm(amv1.position - amv1.estimated_position))
    
    # Find all surface events
    surface_events = []
    lines = mystdout.getvalue().split("\n")
    for line in lines:
        if f"AMV1 at surface" in line or f"rejected" in line:
            surface_events.append(line.strip())
            
    return {
        "case_name": case_name,
        "true_pos": amv1.position.copy(),
        "est_pos": amv1.estimated_position.copy(),
        "error": final_error,
        "tasks_completed": completed_tasks,
        "energy": amv1.energy,
        "distance": amv1.distance_traveled,
        "surface_events": surface_events
    }

def analyze():
    baseline = run_and_analyze(False, (0.0, 0.0), "Baseline")
    spoof_50 = run_and_analyze(True, (50.0, 0.0), "50m Spoof")
    spoof_200 = run_and_analyze(True, (200.0, 0.0), "200m Spoof")
    
    for r in (baseline, spoof_50, spoof_200):
        print(f"\n{r['case_name'].upper()}:")
        print(f"  Final True Position:      [{r['true_pos'][0]:.2f}, {r['true_pos'][1]:.2f}]")
        print(f"  Final Believed Position:  [{r['est_pos'][0]:.2f}, {r['est_pos'][1]:.2f}]")
        print(f"  Final Navigation Error:   {r['error']:.2f} meters")
        print(f"  AMV1 Completed Tasks:     {r['tasks_completed']}")
        print(f"  AMV1 Final Energy:        {r['energy']:.2f}%")
        print(f"  AMV1 Distance Traveled:   {r['distance']:.2f} meters")
        print(f"  AMV1 Surface Events:")
        for se in r["surface_events"][:5]:
            print(f"    {se}")

if __name__ == "__main__":
    analyze()
