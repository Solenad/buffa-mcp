# Buffa Plan: Token-Budget-Aware RAG for Large Local Codebases

## 1) Product Direction

Buffa solves the same broad problem as tools like ChunkHound (making large codebases usable by LLMs), but with a specific moat:

- Token-budget-aware context assembly, not just retrieval.
- Local-first and enterprise-friendly operation (NIM, air-gapped compatibility).
- Reliable behavior under constrained windows (for example 4k to 8k total context).

Core thesis:

1. Retrieve many candidates.
2. Rerank for relevance.
3. Pack into a strict token budget.
4. Compress lower-priority chunks only when needed.

If Buffa can consistently answer "what is the best context slice for this query under N tokens?", it is differentiated.

## 2) Validation of the Previous Plan

The original plan was directionally correct but too high-level for execution. Gaps identified:

- No explicit architecture decision between simple pipeline orchestration and graph orchestration.
- No formal token-budget contract (what gets reserved first, how overrides work, failure behavior).
- No quality harness to prove improvement against baseline chunking and retrieval.
- No production guidance for vector DB choice at larger scales.
- No explicit fallback behavior when NIM services are down or unreachable.
- No clear handling for schema hosting without a custom domain.

This updated plan resolves these gaps.

## 3) Goals and Non-Goals

### Goals

- Fit highest-value context in strict budgets with zero hard overflows.
- Improve retrieval precision using reranking and hybrid search.
- Keep all sensitive code local by default.
- Provide an MCP tool interface that can accept caller-provided budget constraints.
- Support practical large-repo workflows (incremental indexing, file watch, branch-aware refresh).
- Ground answers in retrieved repository context with explicit provenance instead of relying on model memory.

### Non-Goals (MVP)

- Full autonomous coding agent loop inside Buffa.
- Multi-step planning/reasoning workflow orchestration in the hot retrieval path.
- Perfect token counting for every model from day one (start with robust estimation plus safety margin).
- Fine-tuning as a substitute for retrieval correctness (fine-tuning can improve style, not factual grounding).

## 4) Best-Fit Architecture (Recommended)

### Decision Summary

- Primary architecture: Deterministic pipeline service (no LangGraph in the critical path for MVP).
- Model stack: NVIDIA NIM for embeddings, reranking, and optional generation.
- Retrieval stack: Hybrid retrieval (semantic + keyword) -> NIM reranker -> budget packer.
- Vector store:
  - Recommended for larger repos and filtering-heavy workloads: Qdrant.
  - Simpler local quickstart option: ChromaDB.
- Interface: MCP server exposing `search_codebase` with budget controls.

Rationale:

- Deterministic pipeline gives lower latency, easier debugging, and less orchestration overhead.
- NIM `query` vs `passage` embedding modes directly improve retrieval quality.
- Reranking plus packing is Buffa's main differentiator and must remain predictable.

### System Flow

Offline indexing flow:

`repo files -> cAST/AST chunking -> NIM embeddings (input_type=passage) -> vector DB upsert`

Online retrieval flow:

`query -> NIM embeddings (input_type=query) -> hybrid retrieval -> NIM reranker -> token packer + compression -> context payload`

Optional generation flow:

`context payload + user query -> NIM LLM`

### RAG Phase Framing (Ingestion, Retrieval, Synthesis)

To keep implementation disciplined, Buffa maps to the canonical RAG lifecycle:

- Ingestion:
  - Parse and chunk code into meaningful units.
  - Embed chunks and store vectors with metadata.
  - Maintain index freshness with incremental updates.
- Retrieval:
  - Retrieve candidate chunks from vector/keyword search.
  - Rerank and prune to high-signal candidates.
  - Assemble context under strict token constraints.
- Synthesis:
  - Generate from packed context only.
  - Return explicit uncertainty when retrieval is insufficient.

This framing is retained across all phases and helps avoid blending responsibilities.

## 5) Core Algorithms and Contracts

### 5.1 Token Budget Contract

Budget computation order:

1. Resolve effective budget:
   - request `token_budget` if provided, else `token_budget.default`
   - apply `per_model_overrides` if model-specific value exists
2. Reserve mandatory tokens:
   - `reserve_for_system_prompt`
   - `reserve_for_llm_output`
   - optional protocol/tool overhead reserve (configurable)
3. Remaining is `available_context_budget` for packed chunks.

Failure behavior:

- If `available_context_budget <= 0`, return structured error with remediation hint.
- Never exceed computed available budget.

### 5.2 Retrieval and Packing Loop

1. Embed query with NIM (`input_type=query`).
2. Retrieve `N` candidates (semantic + keyword hybrid).
3. Rerank candidates with `nvidia/llama-3.2-nv-rerankqa-1b-v2`.
4. Greedily pack by rerank score into remaining budget.
5. For chunk that does not fit, apply compression cascade in order:
   - strip comments
   - strip docstrings (configurable)
   - truncate long functions/classes (for example to `truncate_at_lines`)
6. Include provenance metadata for each packed chunk.

Optional extensions (post-MVP, controlled by feature flags):

- Small-to-large retrieval:
  - retrieve small units for precision
  - expand to parent symbol/body for synthesis context
- Retriever ensembling:
  - pool candidates from multiple retrieval strategies/chunk granularities
  - let reranker prune final candidate set

### 5.3 Chunk Metadata Contract

Every chunk should carry:

- `chunk_id`
- `file_path`
- `language`
- `symbol_name`
- `symbol_type` (function, class, method, interface, impl)
- `start_line`, `end_line`
- `hash` (content hash for incremental indexing)
- `raw_token_estimate`
- `compressed_token_estimate` (when applicable)

### 5.4 Prompt Assembly Policy (Lost-in-the-Middle Mitigation)

Buffa should explicitly account for long-context placement effects:

- Keep packed chunk count tight; avoid adding low-value middle context.
- Place highest-confidence chunk early in the prompt.
- Place second highest-confidence chunk near the end of context block.
- Keep per-chunk headers concise and standardized to reduce overhead.
- Preserve stable ordering rules so behavior is debuggable and testable.

## 6) NVIDIA NIM Integration Strategy

### Models

- Embedding: `nvidia/nv-embedqa-e5-v5`
- Reranker: `nvidia/llama-3.2-nv-rerankqa-1b-v2`
- LLM (example defaults):
  - `meta/llama-3.1-8b-instruct`
  - `meta/llama-3.1-70b-instruct`
  - `mistralai/mistral-7b-instruct-v0.3`

### Endpoint Strategy

- Default cloud endpoint: `https://integrate.api.nvidia.com/v1`
- On-prem endpoint: configurable `base_url` for local NIM deployment.
- API contract: OpenAI-compatible client usage where possible.

### Critical Implementation Detail

- Use `input_type=passage` when indexing code.
- Use `input_type=query` when embedding user questions.

This is mandatory for quality and must not be treated as an optional optimization.

## 7) Configuration Plan (`.buffa.json`)

The following shape is the canonical config contract for MVP and early production:

```json
{
  "nim": {
    "api_key": "${NVIDIA_API_KEY}",
    "base_url": "https://integrate.api.nvidia.com/v1",
    "embedding": {
      "model": "nvidia/nv-embedqa-e5-v5",
      "batch_size": 32,
      "dimensions": 1024
    },
    "reranking": {
      "enabled": true,
      "model": "nvidia/llama-3.2-nv-rerankqa-1b-v2",
      "top_k_candidates": 10
    },
    "llm": {
      "model": "meta/llama-3.1-8b-instruct",
      "temperature": 0.2,
      "max_tokens": 1024
    }
  },
  "token_budget": {
    "default": 3072,
    "reserve_for_system_prompt": 512,
    "reserve_for_llm_output": 1024,
    "compression": {
      "strip_comments": true,
      "strip_docstrings": false,
      "truncate_long_functions": true,
      "truncate_at_lines": 80
    },
    "per_model_overrides": {
      "meta/llama-3.1-8b-instruct": 3072,
      "meta/llama-3.1-70b-instruct": 6144,
      "mistralai/mistral-7b-instruct-v0.3": 2048
    }
  },
  "index": {
    "db_path": ".buffa/db",
    "include": ["./src", "./lib", "./app"],
    "exclude": [
      "node_modules",
      ".git",
      "dist",
      "build",
      "__pycache__",
      "*.min.js",
      "*.lock"
    ],
    "extensions": {
      "ast_parsed": [
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".go", ".rs", ".java", ".kt", ".c", ".cpp"
      ],
      "text_parsed": [
        ".md", ".txt", ".yaml", ".yml", ".json", ".toml"
      ]
    },
    "chunking": {
      "strategy": "cast",
      "min_chunk_tokens": 20,
      "max_chunk_tokens": 512,
      "overlap_tokens": 32,
      "node_types": [
        "function_definition",
        "class_definition",
        "method_definition",
        "interface_declaration",
        "impl_item"
      ]
    },
    "watch": {
      "enabled": true,
      "debounce_ms": 500,
      "on_git_branch_switch": "reindex_changed"
    }
  },
  "search": {
    "default_top_k": 5,
    "similarity_threshold": 0.72,
    "hybrid": {
      "enabled": true,
      "keyword_weight": 0.2,
      "semantic_weight": 0.8
    },
    "scope": {
      "allow_file_filter": true,
      "allow_type_filter": true
    }
  },
  "mcp": {
    "server_name": "buffa",
    "transport": "stdio",
    "tools": {
      "search_codebase": {
        "enabled": true,
        "expose_token_budget_param": true,
        "expose_file_filter_param": true
      },
      "index_status": {
        "enabled": true
      },
      "explain_chunk": {
        "enabled": false
      }
    }
  },
  "telemetry": {
    "enabled": false,
    "log_queries": false,
    "log_path": ".buffa/logs"
  }
}
```

Quickstart minimal config remains supported:

```json
{
  "nim": {
    "api_key": "${NVIDIA_API_KEY}"
  },
  "index": {
    "include": ["./"]
  }
}
```

Schema hosting options (no custom domain required):

- Omit `$schema` initially.
- Use a GitHub raw URL.
- Use local relative schema file.
- Migrate to GitHub Pages versioned URL later.

## 8) MCP Interface Contract

### `search_codebase`

Input:

- `query` (required string)
- `token_budget` (optional integer)
- `top_k` (optional integer)
- `file_filter` (optional)
- `type_filter` (optional)
- `model` (optional, used for budget override resolution)

Output:

- packed chunks with provenance
- budget usage summary (`available`, `used`, `remaining`)
- compression actions applied per chunk

### `index_status`

Output:

- index freshness
- chunk counts by language
- last update timestamp
- watcher state

## 9) LangGraph Evaluation

### Is LangGraph helpful here?

Yes, but not for the MVP critical path.

Where LangGraph helps:

- Multi-hop retrieval workflows with branching logic.
- Automated fallback chains (for example reranker unavailable -> degrade gracefully).
- Stateful orchestration and replay/debug for complex agentic flows.
- Advanced retrieval patterns such as multi-query and HyDE-style expansion with controlled branching.

Where it hurts (for this MVP):

- Adds orchestration complexity for a flow that is mostly deterministic.
- Increases moving parts and debugging surface area.
- Can add latency overhead in the hot query path.

Decision:

- Phase 1-4: implement deterministic pipeline without LangGraph.
- Phase 5+: optionally introduce LangGraph for advanced "research mode" and recovery orchestration.
- Guardrail: LangGraph path must call the same token-budget contract and packer logic as deterministic path.

## 10) Implementation Roadmap

### Phase 0: Foundations

- Config loader and validation model (with env expansion).
- NIM client wrapper (embedding, reranking, generation endpoints).
- Token estimator utility with safety margin.

Exit criteria:

- Valid config parsing with defaults and overrides.
- NIM health checks and authenticated requests verified.

### Phase 1: Indexing Engine

- cAST chunker for core languages.
- Batch embedding pipeline (`input_type=passage`).
- Local vector DB integration.
- Incremental reindex using file hashes.
- Chunking fallback strategy (for parser failures): recursive/text chunking with lower confidence flag.

Exit criteria:

- Full index build for medium repo completes successfully.
- Re-index only changed files on updates.

### Phase 2: Retrieval and Context Assembly

- Query embedding (`input_type=query`).
- Hybrid retrieval and similarity filtering.
- NIM reranker integration.
- Budget packer with compression cascade.
- Small-to-large context expansion experiment (feature flagged, off by default).
- Prompt ordering policy to mitigate long-context middle drop-off.

Exit criteria:

- No context overflows in test harness.
- Improved relevance over baseline semantic-only retrieval.

### Phase 3: MCP Surface

- Expose `search_codebase` and `index_status`.
- Add budget telemetry in responses.
- Add structured error responses for budget and retrieval failures.

Exit criteria:

- MCP client can call tools with custom budget and filters.
- Responses include provenance and usage data.

### Phase 4: Hardening and Evaluation

- Benchmark harness with representative queries.
- Quality metrics and latency tracking.
- Failure-mode tests (NIM outage, empty retrieval, malformed query).
- Retrieval strategy bake-off: baseline vs reranker vs ensemble (if enabled).
- Context-order A/B tests to validate placement policy impact.

Exit criteria:

- Meets target quality and latency SLOs.
- Known failure modes handled gracefully.

### Phase 5: Optional LangGraph Layer

- Add graph-based orchestration for advanced multi-step workflows.
- Keep deterministic direct pipeline as default path.

Exit criteria:

- LangGraph path demonstrates measurable value over deterministic path for complex queries.

## 11) Quality, Metrics, and Acceptance Criteria

Primary metrics:

- Context fit rate: 100% within computed budget (no hard overflow).
- Retrieval quality: measurable uplift vs naive fixed-size chunk baseline.
- Latency: p50 and p95 tracked per stage (embed, retrieve, rerank, pack).
- Compression impact: percent of queries requiring compression and quality delta.

Recommended quantitative retrieval metrics:

- Precision@k
- Recall@k
- MRR or nDCG for ranking quality
- Hit rate for symbol-targeted queries

Recommended response-grounding metrics:

- Faithfulness (answer grounded in retrieved context)
- Answer relevance to user query
- Context relevance score

Operational metrics:

- Index freshness lag under watcher mode.
- NIM error rate and retry success rate.
- Chunk parse failure rate by language.

## 12) Key Risks and Mitigations

- Token estimation mismatch:
  - Mitigation: conservative safety reserve and model-specific calibration.
- Parser brittleness across languages:
  - Mitigation: fallback text parser and parser error telemetry.
- Vector DB performance at scale:
  - Mitigation: prefer Qdrant for large datasets, benchmark before lock-in.
- NIM dependency outages:
  - Mitigation: health checks, retries, and graceful degraded modes.
- Over-compression harming answer quality:
  - Mitigation: compression thresholds plus offline quality evaluation.
- Too many retrieved chunks hurting synthesis quality:
  - Mitigation: strict top-k caps, rerank pruning, and placement policy validation.

## 14) References and Alignment Notes

- The plan aligns with canonical RAG decomposition (ingestion -> retrieval -> synthesis) and advanced retrieval/reranking patterns discussed in:
  - https://medium.com/@tejpal.abhyuday/retrieval-augmented-generation-rag-from-basics-to-advanced-a2b068fd576c
- Buffa-specific constraints remain unchanged from this plan:
  - local-first NIM stack
  - deterministic budget-aware packing as the primary moat
  - LangGraph deferred to post-MVP advanced orchestration

## 13) Initial Build Priorities

1. Implement config + NIM clients + indexer skeleton.
2. Implement retrieval -> rerank -> pack core loop.
3. Expose MCP `search_codebase` with budget parameter.
4. Add evaluation harness before optimization work.
5. Defer LangGraph until deterministic pipeline baseline is stable.
