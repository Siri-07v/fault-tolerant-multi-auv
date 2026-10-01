import json

with open(r'C:\Users\siri0\.gemini\antigravity-ide\brain\23feb24a-67aa-4269-97a5-2319dcc24016\.system_generated\logs\transcript.jsonl', encoding='utf-8') as f:
    for i, line in enumerate(f):
        data = json.loads(line)
        content = json.dumps(data)
        if "Task 8" in content or "task 8" in content or "Task 7" in content:
            step = data.get("step_index")
            t = data.get("type")
            print(f"Step {step} ({t}):")
            text = data.get("content", "")
            if not text and data.get("tool_calls"):
                text = str(data["tool_calls"])
            print(text[:400])
            print("-" * 50)
