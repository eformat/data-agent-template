"""Kubeflow Pipeline factory for data agent evaluation.

Creates a 5-step KFP pipeline parameterized by DomainConfig:
1. setup_mlflow — configure tracking
2. create_dataset — seed questions from config
3. generate_variants — SDG Hub variant generation
4. run_eval — agent predictor + 11 scorers (4 deterministic + 7 LLM judge)
5. report_results — print scorecard

Usage:
    from data_agent_core.eval.pipeline import create_eval_pipeline
    pipeline = create_eval_pipeline(config)
    from kfp import compiler
    compiler.Compiler().compile(pipeline, "eval-pipeline.yaml")
"""

import json

from kfp import dsl
from kfp import kubernetes

from data_agent_core.config.models import DomainConfig
from data_agent_core.eval.components import (
    setup_mlflow_op,
    create_dataset_op,
    generate_variants_op,
    run_eval_op,
    report_results_op,
)


def create_eval_pipeline(config: DomainConfig):
    """Create a KFP pipeline function for evaluating the domain agent."""

    seed_questions_json = json.dumps([
        {
            "inputs": {"question": sq.question},
            "expectations": {
                "expected_keywords": sq.expected_keywords,
                "question_type": sq.question_type,
                "forbidden_content": sq.forbidden_content,
            },
        }
        for sq in config.seed_questions
    ])

    datasets_json = json.dumps({"datasets": [
        {"name": ds.formal_name or ds.name, "years": ds.years_available}
        for ds in config.datasets.values()
    ]})

    d = config.deployment
    default_namespace = d.namespace or config.domain_name
    default_trino_host = d.trino_host or "trino"
    default_trino_port = d.trino_port or 8080
    default_mlflow_uri = d.mlflow_tracking_uri or "https://mlflow.redhat-ods-applications.svc:8443/mlflow"
    default_mlflow_workspace = d.mlflow_workspace or default_namespace

    fallback_prompt = config.system_prompt[:2000] if config.system_prompt else ""

    @dsl.pipeline(
        name=f"{config.domain_display_name} Evaluation",
        description=f"Evaluate {config.domain_name} agent on 7 capability dimensions using LLM-as-judge",
    )
    def eval_pipeline(
        mlflow_tracking_uri: str = default_mlflow_uri,
        mlflow_workspace: str = default_mlflow_workspace,
        mlflow_experiment_name: str = config.mlflow_experiment_name or config.domain_name,
        dataset_name: str = f"{config.domain_name}_eval",
        llm_base_url: str = d.model_endpoint or "",
        agent_model: str = d.model_name or "kimi-k2-6",
        judge_model: str = "gemma4",
        trino_host: str = default_trino_host,
        trino_port: int = default_trino_port,
        llm_secret_name: str = f"{config.domain_name}-maas-key",
    ):
        # Step 1: Setup MLflow
        setup = setup_mlflow_op(
            mlflow_tracking_uri=mlflow_tracking_uri,
            mlflow_experiment_name=mlflow_experiment_name,
            mlflow_workspace=mlflow_workspace,
        )
        setup.set_caching_options(False)

        # Step 2: Create dataset from seed questions
        dataset = create_dataset_op(
            mlflow_tracking_uri=mlflow_tracking_uri,
            experiment_name=setup.output,
            dataset_name=dataset_name,
            seed_questions_json=seed_questions_json,
            mlflow_workspace=mlflow_workspace,
        )
        dataset.set_caching_options(False)

        # Step 3: Generate question variants via SDG Hub
        sdg_task = generate_variants_op(
            mlflow_tracking_uri=mlflow_tracking_uri,
            experiment_name=dataset.outputs["experiment_name"],
            dataset_id=dataset.outputs["dataset_id"],
            llm_base_url=llm_base_url,
            gen_model=judge_model,
            domain_context=config.domain_description,
            variants_per_seed=3,
            mlflow_workspace=mlflow_workspace,
        )
        sdg_task.set_caching_options(False)
        kubernetes.use_secret_as_env(
            sdg_task,
            secret_name=llm_secret_name,
            secret_key_to_env={"OPENAI_API_KEY": "OPENAI_API_KEY"},
        )

        # Step 4: Run evaluation
        eval_task = run_eval_op(
            mlflow_tracking_uri=mlflow_tracking_uri,
            experiment_name=sdg_task.outputs["experiment_name"],
            dataset_id=sdg_task.outputs["dataset_id"],
            llm_base_url=llm_base_url,
            agent_model=agent_model,
            judge_model=judge_model,
            trino_host=trino_host,
            trino_port=trino_port,
            trino_catalog=config.trino_catalog,
            trino_schema=config.trino_schema,
            prompt_name=config.mlflow_prompt_name,
            datasets_json=datasets_json,
            system_prompt_fallback=fallback_prompt,
            mlflow_workspace=mlflow_workspace,
        )
        eval_task.set_caching_options(False)
        kubernetes.use_secret_as_env(
            eval_task,
            secret_name=llm_secret_name,
            secret_key_to_env={"OPENAI_API_KEY": "OPENAI_API_KEY"},
        )

        # Step 5: Report results
        report_results_op(
            metrics=eval_task.output,
            mlflow_tracking_uri=mlflow_tracking_uri,
        )

    return eval_pipeline
