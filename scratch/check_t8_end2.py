with open('byz_simulation_run.log', encoding='utf-8', errors='ignore') as f:
    text = f.readlines()

for j in range(1430, min(len(text), 1500)):
    clean_line = text[j].strip().encode('ascii', errors='replace').decode('ascii')
    print(f"{j}: {clean_line}")
