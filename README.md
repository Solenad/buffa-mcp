# buffa-mcp

Buffa is a specialized Model Context Protocol (MCP) implementation designed to bridge the gap between massive local codebases and token-constrained LLMs.

## Bootstrap

Use the bootstrap script to install runtime and development dependencies, then run the initialization smoke gate:

```bash
python scripts/bootstrap.py
```

## Verification Gate

Run bootstrap verification manually when needed:

```bash
python scripts/verify_bootstrap.py
```

The verification gate checks:

- project scaffold files and directories
- baseline module imports
- environment contract behavior (required secrets + safe defaults)
- minimal smoke harness execution

## Environment Contract

Required variables:

- `NVIDIA_API_KEY`

Optional variables with safe defaults:

- `BUFFA_NIM_BASE_URL` (default: `https://integrate.api.nvidia.com/v1`)
- `BUFFA_CONFIG_PATH` (default: `.buffa.json`)
- `BUFFA_LOG_LEVEL` (default: `INFO`)
