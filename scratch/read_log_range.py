with open('byz_simulation_run.log', 'r', encoding='utf-8') as f:
    current_timestep = 0
    for line in f:
        line_str = line.strip()
        # Track current timestep
        if line_str.startswith('[T='):
            try:
                current_timestep = int(line_str.split(']')[0].split('=')[1])
            except:
                pass
        
        # Only print events up to t=300
        if current_timestep > 300:
            break
            
        # Check if line has interesting keywords
        if '[TRUST' in line_str or 'AMV1' in line_str or 'Task 5' in line_str:
            # Skip the verbose masking prints to keep output clean
            if '[BYZANTINE MASK]' in line_str:
                continue
            print(f"t={current_timestep}: {line_str}")
