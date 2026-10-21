import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import main

config.ALLOCATOR_MODE = "auction"
config.STRESS_SCENARIO = "none"
config.FIXED_SEED = 42
config.COMPROMISED_AMVS = []
config.BYZANTINE_MODE = None
config.GPS_SPOOF_ENABLED = False
config.LIVE_VIZ_ENABLED = False
config.SAVE_PLOTS = False
config.OPENSET_DETECTOR_ENABLED = True

# Hook into symbolic rules or inspect when unknown fault fires
from symbolic_rules import SymbolicRuleEngine, RuleVerdict

orig_check = SymbolicRuleEngine.check_confidence_gate
fire_events = []
def hooked_check(self, amv):
    v = orig_check(self, amv)
    if not v.allowed and v.modification.get('unknown_fault'):
        fire_events.append({
            'amv_id': amv.amv_id,
            'm_dist': getattr(amv, '_last_mahalanobis_dist', None),
            'fsm': amv.fsm_state,
            'reason': v.reason
        })
    return v

SymbolicRuleEngine.check_confidence_gate = hooked_check

res = main.main()
print(f"\nTotal Rule 4 UNKNOWN_FAULT veto events: {len(fire_events)}")
for e in fire_events[:20]:
    print(e)
