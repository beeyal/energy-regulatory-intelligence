"""
Configuration and authentication for the Energy Compliance Hub.
Supports both Databricks App OAuth (production) and local profile (development).
"""

import os

from databricks.sdk import WorkspaceClient

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))


def get_workspace_client() -> WorkspaceClient:
    """Get an authenticated WorkspaceClient."""
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    else:
        profile = os.environ.get("DATABRICKS_PROFILE", "DEFAULT")
        return WorkspaceClient(profile=profile)


def get_oauth_token() -> str:
    """Get OAuth token for API calls."""
    client = get_workspace_client()
    auth_headers = client.config.authenticate()
    if auth_headers and "Authorization" in auth_headers:
        return auth_headers["Authorization"].replace("Bearer ", "")
    return ""


def get_workspace_host() -> str:
    """Get workspace host URL with https:// prefix."""
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    client = get_workspace_client()
    return client.config.host


def get_catalog() -> str:
    return os.environ.get("COMPLIANCE_CATALOG", "main")


def get_schema() -> str:
    return os.environ.get("COMPLIANCE_SCHEMA", "compliance")


def get_fqn(table: str) -> str:
    """Get fully qualified table name."""
    return f"{get_catalog()}.{get_schema()}.{table}"


def get_model_endpoint() -> str:
    """Get the Foundation Model API endpoint name for chat."""
    return os.environ.get("LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
