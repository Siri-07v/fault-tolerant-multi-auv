class ByzantineContext:
    """
    Context manager to inject Byzantine behavior (falsified bids/states) 
    during benefit calculation for compromised AMVs.
    """
    def __init__(self, amv, task):
        self.amv = amv
        self.task = task
        self.original_fault_state = None
        self.original_availability = None
        self.original_priority_weight = None
        self.swapped = False

    def __enter__(self):
        import config
        # Track what state the AUV declares to the fleet
        self.amv.declared_fault_state = self.amv.fault_state

        if config.COMPROMISED_AMVS and self.amv.amv_id in config.COMPROMISED_AMVS:
            spoofed_tid = getattr(config, "SPOOFED_TASK_ID", None)
            if spoofed_tid is not None and self.task.task_id == spoofed_tid:
                self.swapped = True
                self.original_priority_weight = self.task.priority_weight
                self.task.priority_weight = 999.0
                print(f"  [BYZANTINE TARGETED] AMV{self.amv.amv_id} forcing bid on spoofed task T{self.task.task_id} by inflating priority to 999.0")
            elif config.BYZANTINE_MODE is not None:
                self.swapped = True
                
                if config.BYZANTINE_MODE == "mask_fault_state":
                    # Save original physical/simulated values
                    self.original_fault_state = self.amv.fault_state
                    self.original_availability = self.amv.availability
                    
                    # Falsify availability to bid as if normal
                    self.amv.fault_state = "normal"
                    self.amv.availability = 1.0 * (self.amv.energy / 100.0)
                    self.amv.declared_fault_state = "normal"
                    print(f"  [BYZANTINE MASK] AMV{self.amv.amv_id} masking fault state '{self.original_fault_state}' as 'normal' (availability: {self.amv.availability:.2f})")
                    
                elif config.BYZANTINE_MODE == "inflate_priority":
                    # Save original task priority weight
                    self.original_priority_weight = self.task.priority_weight
                    
                    # Falsify to maximum priority weight
                    self.task.priority_weight = config.PRIORITY_WEIGHT_MAX  # 1.5
                    print(f"  [BYZANTINE INFLATE] AMV{self.amv.amv_id} inflating task T{self.task.task_id} priority from {self.original_priority_weight:.2f} to {self.task.priority_weight:.2f}")
                
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.swapped:
            # Restore true physical states so they don't break simulation/FSM logic
            if self.original_fault_state is not None:
                self.amv.fault_state = self.original_fault_state
                self.amv.availability = self.original_availability
            if self.original_priority_weight is not None:
                self.task.priority_weight = self.original_priority_weight
