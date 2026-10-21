import sys
import io
import numpy as np

sys.path.append(".")
import config
import main
import consensus
import simulation

def run_case_rigorous(spoof, offset):
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

    out = main.main()
    amv1 = [a for a in out["amvs"] if a.amv_id == 1][0]
    
    # Track timesteps active (not Idle/Assignment)
    # Actually, we can count the number of timesteps amv1 was Reaching or Serving
    # In main.py, we can patch simulation.AMV to count its states
    # Let's count how many times FSM state is not Idle
    
    energy_consumed = 100.0 - amv1.energy
    dist = amv1.distance_traveled
    final_error = float(np.linalg.norm(amv1.position - amv1.estimated_position))
    tasks = len(set(amv1.tasks_completed))
    
    return {
        "energy_consumed": energy_consumed,
        "distance_traveled": dist,
        "tasks_completed": tasks,
        "final_error": final_error,
        "final_energy": amv1.energy
    }

def test():
    base = run_case_rigorous(False, (0.0, 0.0))
    s50 = run_case_rigorous(True, (50.0, 0.0))
    s200 = run_case_rigorous(True, (200.0, 0.0))
    
    # We will write the comparative table to stdout so we can copy it to walkthrough.md
    print("\n| Metric | Baseline | 50m Spoof (Unmitigated) | 200m Spoof (Unmitigated) |")
    print("| --- | :---: | :---: | :---: |")
    print(f"| **AMV1 Final Navigation Error** | {base['final_error']:.2f} m | {s50['final_error']:.2f} m | {s200['final_error']:.2f} m |")
    print(f"| **AMV1 Unique Tasks Completed** | {base['tasks_completed']} | {s50['tasks_completed']} | {s200['tasks_completed']} |")
    print(f"| **AMV1 Distance Traveled** | {base['distance_traveled']:.2f} m | {s50['distance_traveled']:.2f} m | {s200['distance_traveled']:.2f} m |")
    print(f"| **AMV1 Energy Consumed** | {base['energy_consumed']:.2f}% | {s50['energy_consumed']:.2f}% | {s200['energy_consumed']:.2f}% |")
    print(f"| **Extra Distance Traveled (Waste)** | 0.00 m | {s50['distance_traveled'] - base['distance_traveled']:.2f} m | {s200['distance_traveled'] - base['distance_traveled']:.2f} m |")
    print(f"| **Extra Energy Consumed (Waste)** | 0.00% | {s50['energy_consumed'] - base['energy_consumed']:.2f}% | {s200['energy_consumed'] - base['energy_consumed']:.2f}% |")

if __name__ == "__main__":
    test()
