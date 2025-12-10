"""
Mock AWS API responses for evaluation tests.

All mock data follows actual AWS API response structures.
"""

# =============================================================================
# LAMBDA API RESPONSES
# =============================================================================

MOCK_LAMBDA_FUNCTIONS = {
    "Functions": [
        {
            "FunctionName": "payment-processor",
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:payment-processor",
            "Runtime": "python3.12",
            "Role": "arn:aws:iam::123456789012:role/payment-processor-role",
            "Handler": "index.handler",
            "CodeSize": 5242880,
            "Description": "Processes payment transactions",
            "Timeout": 30,
            "MemorySize": 1024,
            "LastModified": "2024-01-15T10:30:00.000+0000",
            "CodeSha256": "abc123def456...",
            "Version": "$LATEST",
            "TracingConfig": {"Mode": "Active"},
            "RevisionId": "a1b2c3d4-5678-90ab-cdef-EXAMPLE11111",
            "Architectures": ["x86_64"],
            "EphemeralStorage": {"Size": 512},
            "PackageType": "Zip",
            "LoggingConfig": {
                "LogFormat": "Text",
                "LogGroup": "/aws/lambda/payment-processor",
            },
        },
    ]
}

# =============================================================================
# CLOUDWATCH METRICS API RESPONSES
# https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/
# =============================================================================

MOCK_CLOUDWATCH_GET_METRIC_DATA = {
    "Messages": [],
    "MetricDataResults": [
        {
            "Id": "invocations",
            "Label": "Invocations",
            "StatusCode": "Complete",
            "Timestamps": [1732924800, 1732838400, 1732752000],
            "Values": [52000, 48500, 49500],
        },
        {
            "Id": "errors",
            "Label": "Errors",
            "StatusCode": "Complete",
            "Timestamps": [1732924800, 1732838400, 1732752000],
            "Values": [12, 8, 15],
        },
        {
            "Id": "duration",
            "Label": "Duration",
            "StatusCode": "Complete",
            "Timestamps": [1732924800, 1732838400, 1732752000],
            "Values": [245.5, 238.2, 251.8],
        },
        {
            "Id": "throttles",
            "Label": "Throttles",
            "StatusCode": "Complete",
            "Timestamps": [1732924800, 1732838400, 1732752000],
            "Values": [0, 0, 0],
        },
        {
            "Id": "concurrent",
            "Label": "ConcurrentExecutions",
            "StatusCode": "Complete",
            "Timestamps": [1732924800, 1732838400, 1732752000],
            "Values": [15, 18, 12],
        },
    ],
}

MOCK_CLOUDWATCH_METRIC_STATISTICS = {
    "Invocations": {
        "Label": "Invocations",
        "Datapoints": [
            {"Timestamp": "2024-11-30T00:00:00Z", "Sum": 52000.0, "Unit": "Count"},
            {"Timestamp": "2024-11-29T00:00:00Z", "Sum": 48500.0, "Unit": "Count"},
            {"Timestamp": "2024-11-28T00:00:00Z", "Sum": 49500.0, "Unit": "Count"},
        ],
    },
    "Duration": {
        "Label": "Duration",
        "Datapoints": [
            {
                "Timestamp": "2024-11-30T00:00:00Z",
                "Average": 245.5,
                "Maximum": 890.0,
                "Minimum": 45.2,
                "SampleCount": 52000.0,
                "Unit": "Milliseconds",
            },
            {
                "Timestamp": "2024-11-29T00:00:00Z",
                "Average": 238.2,
                "Maximum": 856.3,
                "Minimum": 42.1,
                "SampleCount": 48500.0,
                "Unit": "Milliseconds",
            },
        ],
    },
    "Errors": {
        "Label": "Errors",
        "Datapoints": [
            {"Timestamp": "2024-11-30T00:00:00Z", "Sum": 12.0, "Unit": "Count"},
            {"Timestamp": "2024-11-29T00:00:00Z", "Sum": 8.0, "Unit": "Count"},
        ],
    },
    "Throttles": {
        "Label": "Throttles",
        "Datapoints": [
            {"Timestamp": "2024-11-30T00:00:00Z", "Sum": 0.0, "Unit": "Count"},
            {"Timestamp": "2024-11-29T00:00:00Z", "Sum": 0.0, "Unit": "Count"},
        ],
    },
    "ConcurrentExecutions": {
        "Label": "ConcurrentExecutions",
        "Datapoints": [
            {"Timestamp": "2024-11-30T00:00:00Z", "Maximum": 18.0, "Average": 12.5, "Unit": "Count"},
            {"Timestamp": "2024-11-29T00:00:00Z", "Maximum": 15.0, "Average": 10.2, "Unit": "Count"},
        ],
    },
}

# =============================================================================
# CLOUDWATCH LOGS API RESPONSES
# https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/
# =============================================================================

MOCK_LOGS_START_QUERY = {"queryId": "12ab3456-12ab-123a-789e-1234567890ab"}

MOCK_LOGS_QUERY_RESULTS = {
    "status": "Complete",
    "statistics": {"bytesScanned": 1048576, "recordsMatched": 150000, "recordsScanned": 150000},
    "results": [
        [
            {"field": "avgMemoryUsedMB", "value": "512.5"},
            {"field": "p90MemoryUsedMB", "value": "680.2"},
            {"field": "p99MemoryUsedMB", "value": "745.8"},
            {"field": "allocatedMemoryMB", "value": "1024"},
        ]
    ],
}


# =============================================================================
# PRICING API RESPONSES
# https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-list-api.html
# =============================================================================

MOCK_PRICING_LAMBDA_COMPUTE = {
    "PriceList": [
        '{"product":{"productFamily":"Serverless","attributes":{"servicecode":"AWSLambda","location":"US East (N. Virginia)","usagetype":"Lambda-GB-Second","group":"AWS-Lambda-Duration"}},"terms":{"OnDemand":{"XXXXXXXX.YYYYYYYY":{"priceDimensions":{"XXXXXXXX.YYYYYYYY.ZZZZZZZZ":{"unit":"Lambda-GB-Second","endRange":"Inf","description":"$0.0000166667 per GB-second","appliesTo":[],"rateCode":"XXXXXXXX.YYYYYYYY.ZZZZZZZZ","beginRange":"0","pricePerUnit":{"USD":"0.0000166667"}}}}}}}'
    ]
}

MOCK_PRICING_LAMBDA_REQUESTS = {
    "PriceList": [
        '{"product":{"productFamily":"Serverless","attributes":{"servicecode":"AWSLambda","location":"US East (N. Virginia)","usagetype":"Lambda-Request","group":"AWS-Lambda-Requests"}},"terms":{"OnDemand":{"XXXXXXXX.YYYYYYYY":{"priceDimensions":{"XXXXXXXX.YYYYYYYY.ZZZZZZZZ":{"unit":"Requests","endRange":"Inf","description":"$0.20 per 1M requests","appliesTo":[],"rateCode":"XXXXXXXX.YYYYYYYY.ZZZZZZZZ","beginRange":"0","pricePerUnit":{"USD":"0.0000002"}}}}}}}'
    ]
}
