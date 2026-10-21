import json, sys

with open(r'C:\Users\siri0\.gemini\antigravity-ide\brain\23feb24a-67aa-4269-97a5-2319dcc24016\.system_generated\logs\transcript.jsonl', encoding='utf-8') as f:
    lines = [json.loads(line) for line in f]

for l in lines:
    if l.get('step_index') == 288:
        tc = l.get('tool_calls', [{}])[0]
        args = tc.get('args', {})
        print("StartLine:", args.get('StartLine'), "EndLine:", args.get('EndLine'))
        print("TargetContent:\n", args.get('TargetContent'))
        print("ReplacementContent:\n", args.get('ReplacementContent'))
