import sys
import io

sys.path.append(".")
import scratch.test_message_integrity as tmi

res1, out1 = tmi.run_simulation_case(
    "corrupt_payload",
    spoof_messages=["auction"],
    spoof_mode="corrupt_payload",
    compromised_amvs=[1]
)

print("DETAILED TRACE FOR AMV1 VETOES (t=50 to t=250):")
for line in out1.split("\n"):
    if "AMV1" in line or "AMV 1" in line:
        if any(k in line.lower() for k in ("veto", "screened", "stripped", "rule")):
            print(line)
