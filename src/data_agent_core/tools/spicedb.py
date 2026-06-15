"""SpiceDB permission check tool — 100% shared across domains."""

from __future__ import annotations

import json
import os


def create_mock_permission_tool():
    """Create a LangChain @tool that always returns allowed=True.

    For local development — no gRPC or authzed dependency needed.
    """
    from langchain_core.tools import tool

    @tool
    def check_dataset_permission(subject_id: str, resource_id: str, permission: str) -> str:
        """Check if a user has a specific permission on a dataset.

        Args:
            subject_id: The user ID to check (e.g., 'admin', 'viewer').
            resource_id: The dataset name (e.g., 'notifications', 'population').
            permission: The permission to check (e.g., 'query', 'view_metadata', 'export').

        Returns:
            JSON with 'allowed' (true/false) and details.
        """
        return json.dumps({
            "allowed": True,
            "subject": f"user:{subject_id}",
            "resource": f"dataset:{resource_id}",
            "permission": permission,
            "note": "Dev mode — all permissions granted.",
        })

    return check_dataset_permission


def create_check_permission_tool():
    """Create a LangChain @tool that checks SpiceDB permissions.

    This tool is domain-independent — it checks if a user has a specific
    permission on a dataset resource via SpiceDB gRPC.
    """
    import grpc
    from langchain_core.tools import tool
    from authzed.api.v1 import Client as SpiceDBClient

    class _BearerInterceptor(grpc.UnaryUnaryClientInterceptor):
        def __init__(self, token):
            self._metadata = [("authorization", f"Bearer {token}")]

        def intercept_unary_unary(self, continuation, client_call_details, request):
            metadata = list(client_call_details.metadata or []) + self._metadata
            new_details = client_call_details._replace(metadata=metadata)
            return continuation(new_details, request)

    endpoint = os.environ.get("SPICEDB_ENDPOINT", "dev:50051")
    token = os.environ.get("SPICEDB_TOKEN", "averysecretpresharedkey")

    channel = grpc.intercept_channel(
        grpc.insecure_channel(endpoint),
        _BearerInterceptor(token),
    )
    client = SpiceDBClient.__new__(SpiceDBClient)
    client.init_stubs(channel)

    @tool
    def check_dataset_permission(subject_id: str, resource_id: str, permission: str) -> str:
        """Check if a user has a specific permission on a dataset using SpiceDB.

        Args:
            subject_id: The user ID to check (e.g., 'admin', 'viewer').
            resource_id: The dataset name (e.g., 'notifications', 'population').
            permission: The permission to check (e.g., 'query', 'view_metadata', 'export').

        Returns:
            JSON with 'allowed' (true/false) and details.
        """
        from authzed.api.v1 import (
            CheckPermissionRequest, CheckPermissionResponse,
            ObjectReference, SubjectReference,
        )

        resp = client.CheckPermission(
            CheckPermissionRequest(
                resource=ObjectReference(object_type="dataset", object_id=resource_id),
                permission=permission,
                subject=SubjectReference(
                    object=ObjectReference(object_type="user", object_id=subject_id)
                ),
            )
        )
        allowed = resp.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION

        return json.dumps({
            "allowed": allowed,
            "subject": f"user:{subject_id}",
            "resource": f"dataset:{resource_id}",
            "permission": permission,
        })

    return check_dataset_permission
