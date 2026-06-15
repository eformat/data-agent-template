# Architecture

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User / Browser                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                    Chainlit Agent (app.py)                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │ LangGraph    │  │ MLflow        │  │ SpiceDB              │ │
│  │ ReAct Agent  │  │ Tracing +     │  │ Permission           │ │
│  │              │  │ Prompt Reg.   │  │ Checks               │ │
│  └──────┬───────┘  └───────────────┘  └──────────────────────┘ │
│         │ Tool calls                                            │
│  ┌──────▼───────────────────────────────────────────────────┐  │
│  │ Tools: query_trino, describe_datasets, get_methodology,  │  │
│  │        check_dataset_permission                           │  │
│  └──────┬───────────────────────────────────────────────────┘  │
└─────────┼──────────────────────────────────────────────────────┘
          │ SQL
┌─────────▼──────────────────────────────────────────────────────┐
│                    Trino (Iceberg Lakehouse)                    │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │ Iceberg     │  │ Nessie        │  │ MinIO (S3)           │ │
│  │ Catalog     │  │ Catalog Mgmt  │  │ Object Storage       │ │
│  └─────────────┘  └───────────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────────────┘

                    ┌───────────────────────┐
                    │ MCP Server (optional)  │
                    │ FastMCP + Enrichment   │
                    │ /health endpoint       │
                    └───────────────────────┘

                    ┌───────────────────────┐
                    │ Eval Pipeline (KFP)    │
                    │ 4 deterministic +      │
                    │ 7 LLM-as-judge scorers │
                    └───────────────────────┘
```

## Data Flow

1. **User asks a question** via Chainlit WebSocket
2. **Agent checks permissions** via SpiceDB gRPC
3. **Agent queries data** via Trino SQL (Iceberg tables on MinIO)
4. **Agent retrieves methodology** for context-aware reasoning
5. **Agent generates response** with `<reasoning>` block and confidence card
6. **MLflow traces** the full conversation (spans, tool calls, prompts)

## Key Design Decisions

- **No code generation:** Domain projects import `data-agent-core` library
- **Config-driven:** All domain-specific data lives in `agent-config.yaml`
- **Enrichment contract:** Every tool response includes methodology, caveats, citations
- **Deterministic confidence:** HIGH/MODERATE/LOW computed from tool trace, not LLM-generated
- **Permission-first:** `check_dataset_permission` must precede `query_trino`
