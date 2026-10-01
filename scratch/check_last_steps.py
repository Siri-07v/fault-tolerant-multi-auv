import json

with open(r'C:\Users\siri0\.gemini\antigravity-ide\brain\23feb24a-67aa-4269-97a5-2319dcc24016\.system_generated\logs\transcript.jsonl', encoding='utf-8') as f:
    lines = [json.loads(line) for line in f]

print("Total lines:", len(lines))
for i, l in enumerate(lines[-25:]):
    idx = l.get('step_index')
    t = l.get('type')
    tc = l.get('tool_calls')
    if tc:
        name = tc[0].get('name')
        args = tc[0].get('args', {})
        print(f"{idx}: {t} -> call {name}({list(args.keys())})")
        if name in ('replace_file_content', 'multi_replace_file_content', 'write_to_file', 'run_command'):
            if 'CommandLine' in args:
                print("   cmd:", args['CommandLine'][:120])
            if 'TargetFile' in args:
                print("   target:", args['TargetFile'])
            if 'Instruction' in args:
                print("   inst:", args['Instruction'])
    else:
        content = l.get('content', '')
        print(f"{idx}: {t} -> {content[:200]}")
