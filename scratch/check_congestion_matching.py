import sys
import os
import io

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import main
import comms
import metrics

def check_congestion():
    print("=== Checking Congestion Drop Counter Matching ===")
    
    # Reset module level variable
    comms.RAW_CONGESTION_DROPS = 0
    
    # Nominal scenario with fixed seed 42
    config.ALLOCATOR_MODE = "auction"
    config.STRESS_SCENARIO = "none"
    config.FIXED_SEED = 42
    config.COMPROMISED_AMVS = []
    config.LIVE_VIZ_ENABLED = False
    config.SAVE_PLOTS = False
    
    # Capture print output so we can verify the text printed by print_report
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    
    try:
        results = main.main()
    finally:
        sys.stdout = old_stdout
        
    output_log = mystdout.getvalue()
    
    # Get values
    res_congestion_drops = results['congestion_drops']
    raw_congestion_drops = comms.RAW_CONGESTION_DROPS
    total_sent = results['total_sent']
    
    calculated_rate = (res_congestion_drops / max(total_sent, 1)) * 100.0
    
    # Find congestion drop rate in the output log
    congestion_rate_line = ""
    for line in output_log.split("\n"):
        if "Congestion Drop Rate" in line:
            congestion_rate_line = line.strip()
            break
            
    print("\n--- Congestion Counters ---")
    print(f"Results Dict 'congestion_drops'  : {res_congestion_drops}")
    print(f"Module-level RAW_CONGESTION_DROPS: {raw_congestion_drops}")
    print(f"Calculated Congestion Drop Rate : {calculated_rate:.4f}%")
    print(f"Metrics Report line              : {congestion_rate_line}")
    
    # Verify match
    if res_congestion_drops == raw_congestion_drops:
        print("\n>>> PASS: Results dict matches raw module-level counter exactly! <<<")
    else:
        print("\n>>> FAIL: Mismatch between results dict and raw counter! <<<")

if __name__ == "__main__":
    check_congestion()
