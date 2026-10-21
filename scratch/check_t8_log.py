with open('byz_simulation_run.log', encoding='utf-8', errors='ignore') as f:
    text = f.readlines()

for i, line in enumerate(text):
    if 'reached T8' in line:
        for j in range(max(0, i-5), min(len(text), i+30)):
            clean_line = text[j].strip().encode('ascii', errors='replace').decode('ascii')
            print(f"{j}: {clean_line}")
