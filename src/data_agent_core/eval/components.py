"""KFP pipeline components — reusable across domains.

Each component is a self-contained KFP step with its own dependencies.
Components must inline all logic (KFP serializes them independently).

MLflow init pattern (portable across RHOAI 3.4 and 3.5):
  1. set_tracking_uri + read SA token
  2. set_workspace (if provided)
  3. bypass workspace probe (store._workspace_support = True)
  4. try search_experiments — if gateway rejects, continue without experiment
"""

from typing import NamedTuple

from kfp import dsl
from kfp.dsl import component

DatasetOutput = NamedTuple("DatasetOutput", [("experiment_name", str), ("dataset_id", str)])
GenOutput = NamedTuple("GenOutput", [("experiment_name", str), ("dataset_id", str)])

BASE_IMAGE = "python:3.12-slim"

COMMON_PACKAGES = [
    "mlflow>=3.10",
    "nest-asyncio>=1.6.0",
    "pydantic>=2.0.0",
    "httpx>=0.27.0",
]

SDG_PACKAGES = COMMON_PACKAGES + [
    "sdg-hub>=0.7.0,<1.0",
    "pandas>=2.0",
    "pyyaml>=6.0",
]

AGENT_PACKAGES = COMMON_PACKAGES + [
    "langchain>=0.3",
    "langchain-openai>=0.3",
    "langchain-core>=0.3",
    "langgraph>=0.4",
    "trino>=0.329",
    "openai>=1.0",
]


def _init_mlflow(mlflow_tracking_uri: str, experiment_name: str, mlflow_workspace: str = ""):
    """Portable MLflow init — works on RHOAI 3.4 and 3.5."""
    import os
    from pathlib import Path
    import mlflow
    import mlflow.tracking.fluent as _fluent

    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"

    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    mlflow.set_tracking_uri(mlflow_tracking_uri)

    if mlflow_workspace:
        mlflow.set_workspace(mlflow_workspace)

    client = mlflow.MlflowClient()
    store = client._tracking_client.store
    if hasattr(store, "_workspace_support"):
        store._workspace_support = True

    try:
        exps = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if exps:
            _fluent._active_experiment_id = exps[0].experiment_id
        else:
            _fluent._active_experiment_id = client.create_experiment(experiment_name)
    except Exception as e:
        print(f"[mlflow] Experiment setup skipped: {e}", flush=True)


@component(base_image=BASE_IMAGE, packages_to_install=COMMON_PACKAGES)
def setup_mlflow_op(
    mlflow_tracking_uri: str,
    mlflow_experiment_name: str,
    mlflow_workspace: str = "",
) -> str:
    """Configure MLflow tracking and return experiment name."""
    import os
    from pathlib import Path
    import mlflow
    import mlflow.tracking.fluent as _fluent

    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"

    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    mlflow.set_tracking_uri(mlflow_tracking_uri)

    experiment_name = mlflow_experiment_name
    if not experiment_name.endswith("-eval"):
        experiment_name = f"{experiment_name}-eval"

    if mlflow_workspace:
        mlflow.set_workspace(mlflow_workspace)

    client = mlflow.MlflowClient()
    store = client._tracking_client.store
    if hasattr(store, "_workspace_support"):
        store._workspace_support = True

    try:
        exps = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if exps:
            _fluent._active_experiment_id = exps[0].experiment_id
        else:
            _fluent._active_experiment_id = client.create_experiment(experiment_name)
        print(f"MLflow: {mlflow_tracking_uri} | Experiment: {experiment_name}", flush=True)
    except Exception as e:
        print(f"MLflow experiment setup skipped ({type(e).__name__}): {e}", flush=True)
        print(f"MLflow: {mlflow_tracking_uri} | Will use default experiment", flush=True)

    return experiment_name


@component(base_image=BASE_IMAGE, packages_to_install=COMMON_PACKAGES)
def create_dataset_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_name: str,
    seed_questions_json: str,
    mlflow_workspace: str = "",
) -> NamedTuple("DatasetOutput", [("experiment_name", str), ("dataset_id", str)]):
    """Create evaluation dataset in MLflow from seed questions."""
    import os
    import json
    from typing import NamedTuple
    from pathlib import Path
    import mlflow
    import mlflow.tracking.fluent as _fluent
    from mlflow.genai.datasets import create_dataset

    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"
    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    if mlflow_workspace:
        mlflow.set_workspace(mlflow_workspace)

    client = mlflow.MlflowClient()
    store = client._tracking_client.store
    if hasattr(store, "_workspace_support"):
        store._workspace_support = True

    try:
        exps = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if exps:
            _fluent._active_experiment_id = exps[0].experiment_id
    except Exception:
        pass

    test_cases = json.loads(seed_questions_json)

    from datetime import datetime
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dataset_name = f"{dataset_name}_{run_ts}"

    dataset = create_dataset(
        name=run_dataset_name,
        tags={"stage": "validation", "seeds": str(len(test_cases))},
    )
    dataset = dataset.merge_records(test_cases)
    print(f"Dataset: {run_dataset_name} | {len(test_cases)} seeds | ID: {dataset.dataset_id}", flush=True)

    from typing import NamedTuple
    DatasetOutput = NamedTuple("DatasetOutput", [("experiment_name", str), ("dataset_id", str)])
    return DatasetOutput(experiment_name=experiment_name, dataset_id=dataset.dataset_id)


@component(base_image=BASE_IMAGE, packages_to_install=SDG_PACKAGES)
def generate_variants_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_id: str,
    llm_base_url: str,
    gen_model: str,
    domain_context: str = "",
    variants_per_seed: int = 3,
    mlflow_workspace: str = "",
) -> NamedTuple("GenOutput", [("experiment_name", str), ("dataset_id", str)]):
    """Generate question variants from seeds using SDG Hub with HTTP fallback."""
    import os
    import sys
    import json
    import tempfile
    from typing import NamedTuple
    from pathlib import Path

    os.environ["PYTHONUNBUFFERED"] = "1"
    sys.stdout.reconfigure(line_buffering=True)
    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"

    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    import mlflow
    import mlflow.tracking.fluent as _fluent
    from mlflow.genai.datasets import get_dataset

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    if mlflow_workspace:
        mlflow.set_workspace(mlflow_workspace)

    client = mlflow.MlflowClient()
    store = client._tracking_client.store
    if hasattr(store, "_workspace_support"):
        store._workspace_support = True

    try:
        exps = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if exps:
            _fluent._active_experiment_id = exps[0].experiment_id
    except Exception:
        pass

    dataset = get_dataset(dataset_id=dataset_id)
    df = dataset.to_df()
    seed_count = len(df)
    print(f"Dataset: {dataset.name} | {seed_count} seeds", flush=True)

    import pandas as pd
    seeds = []
    for _, row in df.iterrows():
        inputs = row.get("inputs", {})
        expectations = row.get("expectations", {})
        if isinstance(inputs, str):
            inputs = json.loads(inputs)
        if isinstance(expectations, str):
            expectations = json.loads(expectations)
        seeds.append({
            "question": inputs.get("question", ""),
            "question_type": expectations.get("question_type", "data_retrieval"),
            "expected_keywords": json.dumps(expectations.get("expected_keywords", [])),
        })
    seed_df = pd.DataFrame(seeds)

    gen_base = llm_base_url.rstrip("/")
    if not gen_base.endswith("/v1"):
        gen_base = gen_base + "/v1"
    api_key = os.environ.get("OPENAI_API_KEY", "")

    context = domain_context or "a data agent with SQL access to a lakehouse"

    all_variants = []

    work_dir = Path(tempfile.mkdtemp())
    prompts_dir = work_dir / "prompts"
    prompts_dir.mkdir()

    prompt_yaml = prompts_dir / "question_gen.yaml"
    import yaml as _yaml
    prompt_config = [
        {"role": "system", "content": (
            f"You are an expert evaluation question generator for {context}.\n"
            "Question types: data_retrieval, cross_dataset, scope_boundary, "
            "geographic_resolution, methodology_comparison."
        )},
        {"role": "user", "content": (
            "{{ question_type }} question variant generation.\n\n"
            "Seed: {{ question }}\nExpected keywords: {{ expected_keywords }}\n\n"
            f"Generate exactly {variants_per_seed} variant questions testing the same capability "
            "but with different parameters.\n\n"
            'Respond with a JSON object containing a "variants" array. '
            'Each variant needs: "question", "question_type", "expected_keywords". No markdown.'
        )},
    ]
    with open(prompt_yaml, "w") as f:
        _yaml.dump(prompt_config, f, default_flow_style=False)

    flow_def = {
        "metadata": {"name": "Question Variant Generator", "version": "1.0.0",
                      "dataset_requirements": {"required_columns": ["question", "question_type", "expected_keywords"]}},
        "blocks": [
            {"block_type": "PromptBuilderBlock", "block_config": {
                "block_name": "build_prompt",
                "input_cols": {"question": "question", "question_type": "question_type", "expected_keywords": "expected_keywords"},
                "output_cols": "gen_messages", "prompt_config_path": str(prompt_yaml)}},
            {"block_type": "LLMChatBlock", "block_config": {
                "block_name": "generate", "input_cols": "gen_messages", "output_cols": "gen_response",
                "async_mode": True, "temperature": 0.7, "max_tokens": 1024}},
            {"block_type": "LLMResponseExtractorBlock", "block_config": {
                "block_name": "extract", "input_cols": "gen_response",
                "field_prefix": "gen_", "extract_content": True}},
        ],
    }
    flow_yaml_path = work_dir / "question_gen_flow.yaml"
    with open(flow_yaml_path, "w") as f:
        _yaml.dump(flow_def, f)

    try:
        from sdg_hub.core.flow import Flow
        from pydantic import SecretStr

        flow = Flow.from_yaml(str(flow_yaml_path))
        flow.set_model_config(model=f"openai/{gen_model}", api_key=SecretStr(api_key), api_base=gen_base)

        print(f"Running SDG Hub flow with {gen_model} via {gen_base}...", flush=True)
        result_df = flow.generate(seed_df, runtime_params={
            "generate": {"api_key": SecretStr(api_key), "api_base": gen_base, "model": f"openai/{gen_model}"}
        }, max_concurrency=2)

        content_col = next((c for c in result_df.columns if "content" in c.lower()), None)
        if content_col:
            for _, row in result_df.iterrows():
                try:
                    raw = row[content_col]
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    for v in parsed.get("variants", [])[:variants_per_seed]:
                        q = v.get("question", "")
                        if q:
                            all_variants.append({"inputs": {"question": q}, "expectations": {
                                "expected_keywords": v.get("expected_keywords", []),
                                "question_type": v.get("question_type", "data_retrieval"),
                                "forbidden_content": v.get("forbidden_content", []),
                            }})
                except Exception as e:
                    print(f"  Parse error: {e}", flush=True)
        print(f"Generated {len(all_variants)} variants via SDG Hub", flush=True)

    except Exception as e:
        print(f"SDG Hub error: {e}", flush=True)
        print("Falling back to direct HTTP generation...", flush=True)
        import httpx
        url = f"{gen_base}/chat/completions"
        for seed in seeds:
            prompt = (
                f"Generate {variants_per_seed} variant evaluation questions for {context}.\n\n"
                f"Seed: {seed['question']}\nType: {seed['question_type']}\n\n"
                "Change parameters while keeping the same question type.\n\n"
                'Respond with a JSON object containing a "variants" array. '
                'Each variant needs: "question", "question_type", "expected_keywords". No markdown.'
            )
            try:
                r = httpx.post(url, json={
                    "model": gen_model, "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7, "max_tokens": 1024,
                }, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, timeout=30)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                clean = content.strip()
                if clean.startswith("```"):
                    lines = [l for l in clean.split("\n") if not l.strip().startswith("```")]
                    clean = "\n".join(lines)
                parsed = json.loads(clean)
                for v in parsed.get("variants", [])[:variants_per_seed]:
                    q = v.get("question", "")
                    if q:
                        all_variants.append({"inputs": {"question": q}, "expectations": {
                            "expected_keywords": v.get("expected_keywords", []),
                            "question_type": v.get("question_type", seed["question_type"]),
                        }})
            except Exception as ex:
                print(f"  HTTP error for '{seed['question'][:40]}': {ex}", flush=True)
        print(f"Generated {len(all_variants)} variants via HTTP fallback", flush=True)

    if all_variants:
        dataset = dataset.merge_records(all_variants)
        total = len(dataset.to_df())
        print(f"Dataset: {seed_count} seeds + {len(all_variants)} variants = {total} total", flush=True)
    else:
        print("No variants generated, using seeds only", flush=True)

    from typing import NamedTuple
    GenOutput = NamedTuple("GenOutput", [("experiment_name", str), ("dataset_id", str)])
    return GenOutput(experiment_name=experiment_name, dataset_id=dataset.dataset_id)


@component(base_image=BASE_IMAGE, packages_to_install=AGENT_PACKAGES)
def run_eval_op(
    mlflow_tracking_uri: str,
    experiment_name: str,
    dataset_id: str,
    llm_base_url: str,
    agent_model: str,
    judge_model: str,
    trino_host: str = "trino",
    trino_port: int = 8080,
    trino_catalog: str = "lakehouse",
    trino_schema: str = "",
    prompt_name: str = "",
    datasets_json: str = "[]",
    system_prompt_fallback: str = "",
    mlflow_workspace: str = "",
) -> dict:
    """Run agent evaluation with deterministic + LLM-as-judge scorers."""
    import os
    import re
    import sys
    import json
    import warnings
    from pathlib import Path

    os.environ["PYTHONUNBUFFERED"] = "1"
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    warnings.filterwarnings("ignore")

    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"
    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "2"
    os.environ["MLFLOW_GENAI_EVAL_MAX_SCORER_WORKERS"] = "2"
    os.environ["MLFLOW_GENAI_EVAL_MAX_RETRIES"] = "3"
    os.environ["MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION"] = "True"
    os.environ["TRINO_QUERY_HOST"] = trino_host
    os.environ["TRINO_QUERY_PORT"] = str(trino_port)

    judge_base = llm_base_url.rstrip("/")
    judge_chat_url = judge_base + "/chat/completions"

    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        sa_token_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
        if sa_token_path.exists():
            os.environ["MLFLOW_TRACKING_TOKEN"] = sa_token_path.read_text().strip()

    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass

    import mlflow
    import mlflow.tracking.fluent as _fluent
    from mlflow.genai.scorers import scorer
    from mlflow.genai.datasets import get_dataset

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    if mlflow_workspace:
        mlflow.set_workspace(mlflow_workspace)

    client = mlflow.MlflowClient()
    store = client._tracking_client.store
    if hasattr(store, "_workspace_support"):
        store._workspace_support = True

    try:
        exps = client.search_experiments(filter_string=f"name = '{experiment_name}'")
        if exps:
            _fluent._active_experiment_id = exps[0].experiment_id
    except Exception:
        pass

    # -- Deterministic scorers --
    @scorer
    def contains_expected(inputs: dict, outputs: str, expectations: dict) -> bool:
        keywords = expectations.get("expected_keywords", [])
        if not keywords:
            return True
        out = str(outputs).lower()
        return any(kw.lower() in out for kw in keywords)

    @scorer
    def no_forbidden_content(inputs: dict, outputs: str, expectations: dict) -> bool:
        forbidden = expectations.get("forbidden_content", [])
        if not forbidden:
            return True
        out = str(outputs).lower()
        return not any(f.lower() in out for f in forbidden)

    @scorer
    def confidence_card_present(outputs: str) -> bool:
        return "data confidence" in str(outputs).lower()

    @scorer
    def response_adequate_length(outputs: str) -> float:
        return 1.0 if len(str(outputs)) >= 100 else 0.5

    # -- LLM-as-Judge scorers (direct HTTP) --
    import httpx
    api_key = os.environ.get("OPENAI_API_KEY", "")
    print(f"Judge: {judge_model} via {judge_chat_url}", flush=True)

    def _call_judge(question: str, response: str, criterion: str) -> bool:
        prompt = f"Question: {question}\nResponse: {response}\n\n{criterion}\n\nReply with only YES or NO."
        try:
            r = httpx.post(judge_chat_url, json={
                "model": judge_model, "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10, "temperature": 0,
            }, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, timeout=30)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip().upper().startswith("YES")
        except Exception as e:
            print(f"  Judge error: {e}", flush=True)
            return False

    @scorer
    def cross_dataset_reasoning(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response state which dataset or table was used and why?")

    @scorer
    def methodology_awareness(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response describe the data collection methodology?")

    @scorer
    def scope_adherence(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response stay within scope and avoid causal claims or health advice?")

    @scorer
    def causal_inference_boundaries(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response correctly avoid causal claims from observational data?")

    @scorer
    def geographic_resolution(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response correctly state geographic resolution and explain limitations?")

    @scorer
    def terminology_fluency(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Are lay terms correctly mapped to domain-specific indicators?")

    @scorer
    def confidence_calibration(inputs: dict, outputs: str) -> bool:
        return _call_judge(str(inputs), str(outputs), "Does the response include a Data Confidence level (HIGH/MODERATE/LOW)?")

    all_scorers = [
        contains_expected, no_forbidden_content, confidence_card_present, response_adequate_length,
        cross_dataset_reasoning, methodology_awareness, scope_adherence,
        causal_inference_boundaries, geographic_resolution, terminology_fluency, confidence_calibration,
    ]

    # -- Agent predictor --
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool
    from trino.dbapi import connect as trino_connect

    BLOCKED_SQL = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", re.IGNORECASE)
    _catalog = trino_catalog
    _schema = trino_schema

    @tool
    def query_trino(sql: str) -> str:
        """Execute a read-only SQL query against the Iceberg lakehouse in Trino. Only SELECT allowed."""
        if BLOCKED_SQL.search(sql):
            return json.dumps({"error": "Only SELECT queries allowed."})
        try:
            conn = trino_connect(host=trino_host, port=trino_port, user="admin", catalog=_catalog, schema=_schema)
            cur = conn.cursor()
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(500)
            conn.close()
            return json.dumps({"results": [dict(zip(columns, r)) for r in rows], "row_count": len(rows)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def describe_datasets(topic: str = "") -> str:
        """List available datasets."""
        return datasets_json

    @tool
    def get_methodology(dataset_name: str) -> str:
        """Get data collection methodology for a dataset."""
        return json.dumps({"surveillance_type": "Passive", "collection_design": "Reported/laboratory-confirmed cases"})

    agent_base_url = llm_base_url.replace(f"/{judge_model}", f"/{agent_model}")
    if not agent_base_url.endswith("/v1"):
        agent_base_url = agent_base_url + "/v1"
    print(f"Agent: {agent_model} via {agent_base_url}", flush=True)

    agent_llm = ChatOpenAI(
        model=agent_model, base_url=agent_base_url,
        api_key=os.environ.get("OPENAI_API_KEY", "x"),
        temperature=0.3, max_tokens=4096, streaming=False,
        model_kwargs={"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    )

    system_prompt = None
    if prompt_name:
        try:
            prompt_obj = mlflow.genai.load_prompt(f"prompts:/{prompt_name}@production", allow_missing=True)
            if prompt_obj:
                system_prompt = prompt_obj.template
                print(f"Loaded prompt: {prompt_name} v{prompt_obj.version}", flush=True)
        except Exception as e:
            print(f"Could not load prompt: {e}", flush=True)

    if not system_prompt:
        system_prompt = system_prompt_fallback or "You are a data agent. Use query_trino to answer questions."
        print("Using fallback prompt", flush=True)

    agent = create_react_agent(model=agent_llm, tools=[query_trino, describe_datasets, get_methodology], prompt=system_prompt)

    _q_count = [0]

    def predict_fn(question: str) -> str:
        _q_count[0] += 1
        print(f"[predict {_q_count[0]}] Q: {question[:80]}...", flush=True)
        try:
            with mlflow.start_span(name="agent_eval") as span:
                span.set_inputs({"question": question[:200]})
                result = agent.invoke({"messages": [HumanMessage(content=question)]})
                for m in reversed(result.get("messages", [])):
                    if hasattr(m, "type") and m.type == "ai" and not getattr(m, "tool_calls", None):
                        answer = m.content or ""
                        span.set_outputs({"answer_length": len(answer)})
                        print(f"[predict {_q_count[0]}] A: {len(answer)} chars", flush=True)
                        return answer
            return "No response"
        except Exception as e:
            print(f"[predict {_q_count[0]}] Error: {e}", flush=True)
            return f"Error: {e}"

    # -- Run evaluation --
    dataset = get_dataset(dataset_id=dataset_id)
    print(f"Dataset: {dataset.name} | Records: {len(dataset.to_df())}", flush=True)
    print(f"Scorers: {len(all_scorers)} (4 deterministic + 7 LLM judges)", flush=True)

    result = mlflow.genai.evaluate(data=dataset, predict_fn=predict_fn, scorers=all_scorers)

    metrics = {}
    if hasattr(result, "metrics") and result.metrics:
        for k, v in result.metrics.items():
            metrics[k] = round(v, 4) if isinstance(v, float) else v

    print(f"\nResults: {metrics}")
    return metrics


@component(base_image=BASE_IMAGE, packages_to_install=["pydantic>=2.0.0"])
def report_results_op(metrics: dict, mlflow_tracking_uri: str) -> str:
    """Print evaluation scorecard."""
    print("=" * 60)
    print("DATA AGENT EVALUATION REPORT")
    print("=" * 60)
    for k, v in sorted(metrics.items()):
        if isinstance(v, float):
            print(f"  {k}: {v:.2%}")
        else:
            print(f"  {k}: {v}")
    print(f"\nView in MLflow: {mlflow_tracking_uri}")
    return f"Evaluation complete. {len(metrics)} metrics. View at {mlflow_tracking_uri}"
