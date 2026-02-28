"""CloudWatch Metrics tool for AgentCore Gateway.

Handles cloudwatch_get_metric_statistics and cloudwatch_list_metrics
tool calls routed via Gateway.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

cloudwatch_client = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DELIMITER = "___"


def _create_error_response(error_message):
    return {
        "success": False,
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    original_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = original_tool_name[original_tool_name.index(DELIMITER) + len(DELIMITER) :]

    if tool_name == "cloudwatch_get_metric_statistics":
        return cloudwatch_get_metric_statistics(event)
    elif tool_name == "cloudwatch_list_metrics":
        return cloudwatch_list_metrics(event)
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def cloudwatch_get_metric_statistics(event):
    namespace = event.get("namespace", "")
    metric_name = event.get("metric_name", "")
    start_time = event.get("start_time", "")
    end_time = event.get("end_time", "")
    period = event.get("period", 0)
    statistics = event.get("statistics", [])
    dimensions = event.get("dimensions", [])

    if not all([namespace, metric_name, start_time, end_time, period, statistics]):
        return _create_error_response(
            "Missing required parameters: namespace, metric_name, start_time, end_time, period, statistics"
        )

    try:
        params = {
            "Namespace": namespace,
            "MetricName": metric_name,
            "StartTime": start_time,
            "EndTime": end_time,
            "Period": int(period),
            "Statistics": statistics,
        }
        if dimensions:
            params["Dimensions"] = [{"Name": d["name"], "Value": d["value"]} for d in dimensions]

        response = cloudwatch_client.get_metric_statistics(**params)
        datapoints = []
        for dp in response.get("Datapoints", []):
            point = {"timestamp": dp["Timestamp"].isoformat()}
            for stat in ["Average", "Sum", "Minimum", "Maximum", "SampleCount"]:
                if stat in dp:
                    point[stat.lower()] = dp[stat]
            datapoints.append(point)

        datapoints.sort(key=lambda x: x["timestamp"])

        return {
            "success": True,
            "namespace": namespace,
            "metric_name": metric_name,
            "datapoints": datapoints,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"CloudWatch GetMetricStatistics error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")


def cloudwatch_list_metrics(event):
    namespace = event.get("namespace", "")
    metric_name = event.get("metric_name", "")
    dimensions = event.get("dimensions", [])

    try:
        params = {}
        if namespace:
            params["Namespace"] = namespace
        if metric_name:
            params["MetricName"] = metric_name
        if dimensions:
            params["Dimensions"] = [{"Name": d["name"], "Value": d.get("value", "")} for d in dimensions]

        response = cloudwatch_client.list_metrics(**params)
        metrics = []
        for m in response.get("Metrics", []):
            metrics.append(
                {
                    "namespace": m.get("Namespace"),
                    "metric_name": m.get("MetricName"),
                    "dimensions": [{"name": d["Name"], "value": d["Value"]} for d in m.get("Dimensions", [])],
                }
            )

        return {
            "success": True,
            "metrics": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"CloudWatch ListMetrics error: {error_code} - {error_message}")
        return _create_error_response(f"{error_code}: {error_message}")
