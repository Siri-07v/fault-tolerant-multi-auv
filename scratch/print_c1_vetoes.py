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

print("ALL VETO / SCREENED / STRIPPED / CHECKSUM LINES:")
for line in out1.split("\n"):
    line_l = line.lower()
    if any(k in line_l for k in ("veto", "screened", "stripped", "checksum", "rule")):
        print(line)
