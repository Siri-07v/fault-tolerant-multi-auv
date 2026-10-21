# Adversarial/Compromised scenarios configurations

SCENARIOS = {
    "none": {
        "compromised_amvs": [],
        "byzantine_mode": None
    },
    "one_compromised": {
        "compromised_amvs": [1],
        "byzantine_mode": "mask_fault_state"
    },
    "two_compromised": {
        "compromised_amvs": [1, 2],
        "byzantine_mode": "mask_fault_state"
    },
    "inflate_priority_one": {
        "compromised_amvs": [1],
        "byzantine_mode": "inflate_priority"
    }
}
