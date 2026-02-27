"""Gateway interceptor for request filtering and response redaction."""

import json
import logging
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BLOCKED_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"disregard\s+(previous|all)\s+instructions",
    r"forget\s+(previous|all)\s+instructions",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"jailbreak",
    r"bypass\s+(security|filter|restriction)",
    r"<script[^>]*>",
    r"javascript:",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__",
    r"os\.system",
    r"subprocess",
]

PII_PATTERNS = {
    "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]"),
    "phone": (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE_REDACTED]"),
    "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    "credit_card": (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CC_REDACTED]"),
    "ip_address": (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[IP_REDACTED]"),
}


def check_malicious_content(text):
    text_lower = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, pattern
    return False, ""


def redact_pii(text):
    for _name, (pattern, replacement) in PII_PATTERNS.items():
        text = re.sub(pattern, replacement, text)
    return text


def redact_dict(obj):
    if isinstance(obj, str):
        return redact_pii(obj)
    elif isinstance(obj, dict):
        return {k: redact_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [redact_dict(item) for item in obj]
    return obj


def lambda_handler(event, context):
    logger.info(f"Interceptor event: {json.dumps(event)}")

    mcp_data = event.get("mcp", {})
    gateway_response = mcp_data.get("gatewayResponse")

    if gateway_response is not None:
        return handle_response(mcp_data, gateway_response)
    else:
        return handle_request(mcp_data)


def extract_session_id_from_meta(request_body):
    """Extract session_id from OTEL baggage in _meta field of tools/call requests."""
    params = request_body.get("params", {})
    if not isinstance(params, dict):
        return None
    meta = params.get("_meta", {})
    if not isinstance(meta, dict):
        return None
    baggage_str = meta.get("baggage", "")
    for pair in baggage_str.split(","):
        kv = pair.strip().split("=", 1)
        if len(kv) == 2 and kv[0] == "session.id":
            return kv[1]
    return None


def handle_request(mcp_data):
    gateway_request = mcp_data.get("gatewayRequest", {})
    request_body = gateway_request.get("body", {})
    content_to_check = json.dumps(request_body)

    is_malicious, matched_pattern = check_malicious_content(content_to_check)

    if is_malicious:
        logger.warning(f"Blocked malicious request matching: {matched_pattern}")
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayResponse": {
                    "statusCode": 403,
                    "body": {
                        "jsonrpc": "2.0",
                        "id": request_body.get("id", 1),
                        "error": {
                            "code": -32600,
                            "message": "Request blocked: potentially harmful content detected",
                        },
                    },
                }
            },
        }

    if request_body.get("method") == "tools/call":
        session_id = extract_session_id_from_meta(request_body)
        if session_id:
            params = request_body.get("params", {})
            arguments = params.get("arguments", {})
            arguments["session_id"] = session_id
            params["arguments"] = arguments
            request_body["params"] = params

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {"transformedGatewayRequest": {"body": request_body}},
    }


def handle_response(mcp_data, gateway_response):
    response_body = gateway_response.get("body") or {}
    status_code = gateway_response.get("statusCode", 200)
    redacted_body = redact_dict(response_body)

    return {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": status_code,
                "body": redacted_body,
            }
        },
    }
