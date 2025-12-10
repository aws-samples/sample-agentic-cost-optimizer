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


# =============================================================================
# MOCK ANALYSIS RESULT (for Report Agent tests)
# This represents the output from the Analysis Agent stored in S3
# =============================================================================

MOCK_ANALYSIS_RESULT = """
# AWS Lambda Cost Optimization Analysis Complete

## Executive Summary

I analyzed your AWS Lambda environment and identified **$2.72 USD in monthly cost savings** (43% reduction) for your `payment-processor` function through three key optimizations:

## Key Findings

### Function Inventory
- **1 Lambda function analyzed**: `payment-processor`
- **High-usage function**: 1.5M invocations/month
- **Current monthly cost**: $6.35 USD

### Primary Optimization Opportunities

1. **Memory Right-sizing** → **$1.51/month savings**
   - Reduce from 1024 MB to 768 MB
   - Function uses only 680 MB at P90, providing 33.6% headroom
   - Low risk with 13% safety buffer maintained

2. **Architecture Migration** → **$1.21/month savings**
   - Migrate from x86_64 to ARM64 (Graviton2)
   - Python 3.12 runtime is fully compatible
   - ~20% better price-performance

3. **Timeout Optimization** → **Risk reduction**
   - Reduce from 30 seconds to 5 seconds
   - Maximum observed duration: 890ms
   - Prevents runaway execution costs

## Immediate Action Items

**Highest Impact, Lowest Risk:**
1. **Reduce memory to 768 MB** - Test first in development
2. **Optimize timeout to 5 seconds** - Monitor for 48 hours
3. **Plan ARM64 migration** - Requires compatibility testing

## Cost Impact
- **Current**: $6.35/month
- **Optimized**: $3.63/month
- **Savings**: $2.72/month ($32.64/year)
- **Reduction**: 43%

## Data Quality
- Analysis based on **actual CloudWatch metrics and logs**
- **150,000 invocations** analyzed over 3-day period
- Memory usage data from **CloudWatch Logs** with P90/P99 percentiles
- Current **AWS Pricing API** data fetched for accurate calculations

## Discovery Data

### Lambda Functions Inventory
| Function Name | Runtime | Memory (MB) | Timeout (s) | Architecture |
|--------------|---------|-------------|-------------|--------------|
| payment-processor | python3.12 | 1024 | 30 | x86_64 |

Function ARN: arn:aws:lambda:us-east-1:123456789012:function:payment-processor
Log Group: /aws/lambda/payment-processor

## Metrics Data (Last 30 Days)

### Invocation Metrics
- Total Invocations: 150,000 (3-day sample)
- Projected Monthly: ~1,500,000 invocations
- Error Rate: 0.013% (~20 errors)
- Throttles: 0

### Duration Metrics
- Average Duration: 242 ms
- Maximum Duration: 890 ms

### Memory Metrics (from CloudWatch Logs Insights)
- Average Memory Used: 512.5 MB
- P90 Memory Used: 680.2 MB
- P99 Memory Used: 745.8 MB
- Allocated Memory: 1024 MB
- P90 Headroom: 33.6%

### Concurrency
- Average Concurrent Executions: 11
- Maximum Concurrent Executions: 18

## Detailed Recommendations

### Recommendation 1: Memory Right-sizing (1024 MB → 768 MB)
**Priority**: HIGH
**Monthly Savings**: $1.51

**Evidence**:
- P90 memory usage: 680.2 MB
- Headroom at P90: 33.6%
- Proposed allocation: 768 MB (13% buffer above P90)

**Cost Calculation**:
- Current: 1.0 GB × 1,500,000 × 0.242s × $0.0000166667 = $6.05
- Optimized: 0.75 GB × 1,500,000 × 0.242s × $0.0000166667 = $4.54
- Savings: $1.51/month

**Risk Assessment**: LOW
- 13% safety buffer maintained above P90
- Monitor P99 after change

**Implementation Steps**:
1. Update function memory configuration to 768 MB
2. Deploy to development/staging first
3. Monitor memory metrics for 48 hours
4. Roll out to production with canary deployment

### Recommendation 2: ARM64 Architecture Migration
**Priority**: MEDIUM
**Monthly Savings**: $1.21

**Evidence**:
- Current architecture: x86_64
- Runtime: python3.12 (fully compatible with ARM64/Graviton2)
- No native dependencies detected

**Cost Calculation**:
- x86_64 compute: $6.05/month
- ARM64 compute: $4.84/month (20% reduction)
- Savings: $1.21/month

**Risk Assessment**: LOW
- Python runtime is architecture-agnostic
- No code changes required
- Easy rollback via alias/version

**Implementation Steps**:
1. Update function configuration: Architectures = ["arm64"]
2. Deploy and test with 10% traffic using aliases
3. Monitor performance metrics for 24-48 hours
4. Gradually shift traffic to 100%

### Recommendation 3: Timeout Optimization (30s → 5s)
**Priority**: LOW
**Monthly Savings**: $0 (risk reduction)

**Evidence**:
- Maximum observed duration: 890ms
- Current timeout: 30 seconds
- Recommended timeout: 5 seconds (5.6x max duration)

**Risk Assessment**: LOW
- 5 second timeout provides 5.6x headroom above max observed
- Prevents runaway executions from accumulating costs

**Implementation Steps**:
1. Update timeout to 5 seconds
2. Monitor for timeout errors
3. Adjust if legitimate long-running invocations occur

## Evidence Appendix

### CloudWatch Queries Used
```
# Memory Usage Query
fields @timestamp, @requestId, @maxMemoryUsed, @memorySize, @billedDuration
| filter @type = "REPORT"
| stats count() as invocations,
        avg(@maxMemoryUsed) as avgMemoryUsedMB,
        pct(@maxMemoryUsed, 50) as p50MemoryUsedMB,
        pct(@maxMemoryUsed, 90) as p90MemoryUsedMB,
        pct(@maxMemoryUsed, 99) as p99MemoryUsedMB,
        max(@maxMemoryUsed) as maxMemoryUsedMB,
        avg(@memorySize) as allocatedMemoryMB

# Cold Start Analysis Query
filter @type = "REPORT"
| fields @timestamp, @initDuration, @duration, @maxMemoryUsed
| filter ispresent(@initDuration)
| stats count() as coldStarts,
        avg(@initDuration) as avgInitDurationMs,
        pct(@initDuration, 50) as p50InitDurationMs,
        pct(@initDuration, 95) as p95InitDurationMs,
        pct(@initDuration, 99) as p99InitDurationMs,
        max(@initDuration) as maxInitDurationMs
```

### Pricing Data Retrieved
- Lambda GB-Second (x86): $0.0000166667
- Lambda GB-Second (ARM): $0.0000133334
- Lambda Requests: $0.20 per 1M ($0.0000002 per request)
- Pricing Region: US East (N. Virginia)
- Pricing Timestamp: 2024-12-01T00:00:00Z
"""
