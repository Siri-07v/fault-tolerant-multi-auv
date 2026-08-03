import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def run_case_stats(spoof, offset):
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    config.COMPROMISED_AMVS = [1]
    
    config.GPS_SPOOF_ENABLED = spoof
    config.GPS_SPOOF_OFFSET = offset
    config.GPS_SANITY_THRESHOLD = 99999.0

    import security.trust
    import importlib
    importlib.reload(security.trust)

    out = main.main()
    amv1 = [a for a in out["amvs"] if a.amv_id == 1][0]
    
    # We can calculate energy consumed by AMV1
    # Initial energy is always 100%
    energy_consumed = 100.0 - amv1.energy
    
    # We can count timesteps AMV1 spent in Reaching state
    # main.py updates amv.fsm_state. We can track its state history.
    # In AMV, self.trajectory has the length of timesteps.
    # Let's count how many timesteps it was not Idle/Assignment.
    # Actually, we can count the number of timesteps spent in FSM_REACHING and FSM_SERVING.
    # We can inspect the amv's history of states if we log it, or just read distance traveled.
    dist = amv1.distance_traveled
    
    return {
        "energy_consumed": energy_consumed,
        "distance_traveled": dist,
        "tasks_completed": amv1.tasks_completed.copy(),
        "final_energy": amv1.energy
    }

def test():
    base = run_case_stats(False, (0.0, 0.0))
    s50 = run_case_stats(True, (50.0, 0.0))
    s200 = run_case_stats(True, (200.0, 0.0))
    
    print("\nAMV1 QUANTIFIED METRICS:")
    print(f"Baseline:")
    print(f"  Tasks Completed:     {base['tasks_completed']}")
    print(f"  Energy Consumed:     {base['energy_consumed']:.2f}%")
    print(f"  Distance Traveled:   {base['distance_traveled']:.2f} meters")
    print(f"  Final Energy:        {base['final_energy']:.2f}%")
    
    print(f"50m Spoof:")
    print(f"  Tasks Completed:     {s50['tasks_completed']}")
    print(f"  Energy Consumed:     {s50['energy_consumed']:.2f}%")
    print(f"  Distance Traveled:   {s50['distance_traveled']:.2f} meters")
    print(f"  Final Energy:        {s50['final_energy']:.2f}%")
    print(f"  Energy Wasted:       {s50['energy_consumed'] - base['energy_consumed']:.2f}%")
    print(f"  Extra Dist Traveled: {s50['distance_traveled'] - base['distance_traveled']:.2f} meters")
    
    print(f"200m Spoof:")
    print(f"  Tasks Completed:     {s200['tasks_completed']}")
    print(f"  Energy Consumed:     {s200['energy_consumed']:.2f}%")
    print(f"  Distance Traveled:   {s200['distance_traveled']:.2f} meters")
    print(f"  Final Energy:        {s200['final_energy']:.2f}%")
    print(f"  Energy Wasted:       {s200['energy_consumed'] - base['energy_consumed']:.2f}%")
    print(f"  Extra Dist Traveled: {s200['distance_traveled'] - base['distance_traveled']:.2f} meters")

if __name__ == "__main__":
    test()
