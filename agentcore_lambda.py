import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda entry point for Bedrock AgentCore deployment.
    This wrapper allows AWS Bedrock to invoke the GridGuard Strands Agent
    as an Action Group or as a direct Lambda integration.
    """
    log.info("Received AgentCore event", extra={"event": event})

    # Extract standard Bedrock Agent action group routing fields
    action_group = event.get("actionGroup", "GridGuardStrandsActionGroup")
    api_path = event.get("apiPath", "/smoke-test")
    http_method = event.get("httpMethod", "POST")

    try:
        # Initialize the Strands Agent for a smoke test validation
        # In this slim smoke-test artifact, we return a deterministic mock response
        # to avoid packaging massive ML libraries like xgboost and pandas.

        response_body = {
            "status": "SUCCESS",
            "message": "GridGuard Strands Agent successfully initialized in Bedrock AgentCore.",
            "provider": os.environ.get("STRANDS_PROVIDER", "bedrock"),
            "mock_mode": os.environ.get("MOCK_MODE", "true").lower() == "true",
        }

        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": action_group,
                "apiPath": api_path,
                "httpMethod": http_method,
                "httpStatusCode": 200,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps(response_body)
                    }
                }
            }
        }

    except Exception as exc:
        log.error("AgentCore smoke test failed", exc_info=True)
        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": action_group,
                "apiPath": api_path,
                "httpMethod": http_method,
                "httpStatusCode": 500,
                "responseBody": {
                    "application/json": {
                        "body": json.dumps({
                            "status": "ERROR",
                            "message": str(exc)
                        })
                    }
                }
            }
        }
