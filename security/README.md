# Security Module

This module contains the security and adversarial components of the AUV allocator system, separating Byzantine simulation and verification code from the core allocation algorithms.

## Folder Structure

- `byzantine.py`: Simulates Byzantine behavior by enabling compromised agents to falsify their state or task parameters during auctions.
- `trust.py`: (Stub) Prepares for TrustScore tracking of agents.
- `message_integrity.py`: (Stub) Prepares for cryptographic verification of messages.
- `scenarios.py`: Configures sweeps with varying numbers of compromised AUVs and strategies.

## Integration Hooks

The module plugs into the core simulator dynamically via `ByzantineContext` inside the benefit computation. When `config.COMPROMISED_AMVS` is active, compromised agents swap in falsified parameters at the moment of bidding and restore their true status immediately afterwards.
