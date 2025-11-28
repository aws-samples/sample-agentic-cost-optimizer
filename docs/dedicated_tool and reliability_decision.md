# S3 Storage Tool and Agent Reliability Improvements

## Overview

This document details the design, implementation, and fixes delivered in the `s3-tool`, which includes two major improvements to the cost optimization agent:

1. **S3 Storage Tool**: A dedicated Strands tool for S3 file operations, replacing complex `use_aws` calls
2. **Timestamp Calculation Fix**: Resolution of persistent CloudWatch Logs query failures

These changes improve agent reliability, simplify the codebase, and enable successful cost optimization analysis.

## Problem Statement

### Challenge 1: S3 Write Operations

The agent was using the `use_aws` tool for S3 write operations, requiring:
- AWS API call construction in the prompt
- Manual session ID path management
- Parameter handling by prompt
- Reliable Error handling

**Impacts**:
- **Error-Prone Path Construction**: Manual session ID concatenation in the prompt increased risk of path errors (e.g., missing slashes, incorrect prefixes)
- **Testing Difficulty**: S3 operations couldn't be tested independently from the full agent workflow
- **Debugging Challenges**: S3 failures were difficult to trace without dedicated logging and error handling
- **Lack of Operation Validation**: No validation layer between agent and AWS APIs - the agent could potentially call any AWS operation with any parameters
- **No Input Sanitization**: Direct AWS API calls meant no opportunity to sanitize or validate inputs before they reached AWS services
- **Difficult Permission Scoping**: IAM policies had to grant permissions for all potential `use_aws` operations rather than specific Service actions
- **No Retry Logic**: Generic tool didn't implement S3-specific retry strategies for transient failures
- **Silent Failures**: S3 write failures could go unnoticed if not explicitly checked in the prompt


### Challenge 2: CloudWatch Logs Query Failures

The agent consistently failed to query CloudWatch Logs with `MalformedQueryException` errors:

```
An error occurred (MalformedQueryException) when calling the StartQuery operation: 
Query's end date and time is either before the log groups creation time or 
exceeds the log groups log retention settings ([0,110])
```

**Impact**:
- No log-based right-sizing recommendations
- Incomplete cost optimization reports
- Agent appeared unreliable to users

## Root Cause Analysis

### S3 Operations Complexity

**Previous State** (using `use_aws`):
```markdown
- Use use_aws to write to S3:
  - operation_name: "put_object"
  - parameters:
      Bucket: {s3_bucket_name}
      Key: "<session_id>/cost_report.txt"
      Body: <report_content>
      ContentType: "text/plain"
```

**Problems**:
- Agent must construct AWS API parameters
- Manual session ID path management
- No abstraction or reusability
- Error handling mixed with business logic

### Timestamp Calculation Issue

**Telemetry Analysis** (5 consecutive failures):

**Trace 1** (7-day query):
```json
{
  "startTime": 1729169295,  // October 17, 2024
  "endTime": 1729774095,    // October 24, 2024
}
```

**Trace 2-5**: All used October 2024 dates, progressively shorter windows (3→2→1 days)

**Current Date**: October 22, 2025 (Unix timestamp: ~1761149264)

**Root Cause**: The agent was using a fixed reference date from **one year ago** (October 24, 2024) and calculating backwards from that date, instead of using the current date.

**Why It Failed**:
- Log groups were created after October 24, 2024
- Querying for October 2024 data = querying before log group existed
- Even 1-day window failed because reference date was wrong
- LLMs don't have inherent awareness of current date/time

### Prompt Instruction Challenge

**Before**: "Calculate time ranges relative to the current time"
- LLM doesn't know what "current time" is
- May use training data dates as reference
- No way to verify calculations are correct

## Solution

1. **Separation of Concerns**: Extract S3 operations into dedicated tool
2. **Explicit Context**: Provide current timestamp directly to agent
3. **Clear Instructions**: Make all calculations unambiguous (To be handed over to the calculator tool)
4. **Fail-Safe Retry**: Provide exact formulas for error recovery
5. **Consistent Patterns**: Follow established tool patterns.


## Implementation Details

### Part 1: S3 Storage Tool

**File**: `src/tools/storage.py`

**Architecture**:
```python
@tool(context=True)
def storage(action: str, filename: str, tool_context: ToolContext, content: str = "") -> Dict[str, Any]:
    """Read or write text content to S3 with automatic session-based path management."""
    if action == "read":
        return _read_from_s3(filename, tool_context)
    elif action == "write":
        return _write_to_s3(filename, content, tool_context)
```

**Key Features**:

1. **Automatic Session Management**:
```python
# Retrieve session_id from invocation state
session_id = tool_context.invocation_state.get("session_id")

# Construct S3 key: {session_id}/{filename}
key = f"{session_id}/{filename}"
```

2. **Simple Interface**:
```python
# Before (using use_aws)
use_aws(
    operation_name="put_object",
    parameters={
        "Bucket": bucket_name,
        "Key": f"{session_id}/cost_report.txt",
        "Body": content,
        "ContentType": "text/plain"
    }
)

# After (using storage tool)
storage(action="write", filename="cost_report.txt", content=report_content)
```

3. **Comprehensive Error Handling**:
```python
try:
    bucket.put_object(Key=key, Body=content_bytes, ContentType="text/plain")
    return {
        "success": True,
        "s3_uri": f"s3://{bucket_name}/{key}",
        "size_bytes": size_bytes,
        ...
    }
except ClientError as e:
    return {
        "success": False,
        "error": f"S3 ClientError: {error_code} - {error_message}",
        ...
    }
```

4. **Structured Responses**:
```python
# Success
{
    "success": True,
    "s3_uri": "s3://bucket/session_id/filename.txt",
    "bucket": "bucket-name",
    "key": "session_id/filename.txt",
    "size_bytes": 12345,
    "timestamp": "2025-10-22T16:07:44Z"
}

# Error
{
    "success": False,
    "error": "Error message with context",
    "error_code": "NoSuchBucket",
    "timestamp": "2025-10-22T16:07:44Z"
}
```

**Benefits**:
- **Simplified Prompt**: Agent just calls `storage(action, filename, content)`
- **Automatic Path Management**: Session ID handled automatically
- **Bidirectional Operations**: Supports both read and write actions
- **Consistent Pattern**: Matches journal tool design
- **Better Testing**: Tool can be unit tested independently


**Security Improvements**:

1. **Input Validation and Sanitization**:
```python
# Validate required parameters
if not filename:
    return {"success": False, "error": "Missing required parameter: filename"}

if not content:
    return {"success": False, "error": "Missing required parameter: content"}

# Validate session_id exists
session_id = tool_context.invocation_state.get("session_id")
if not session_id:
    return {"success": False, "error": "Session ID not found"}
```

2. **Controlled S3 Key Construction**:
```python
# Before: Agent constructs key in prompt (risk of path traversal)
Key: f"{session_id}/../../sensitive/file.txt"  # Potential security issue

# After: Tool controls key construction
key = f"{session_id}/{filename}"  # Controlled, predictable pattern
```

3. **Operation-Specific Audit Trail**:
```python
# Structured logging for security audits
logger.info(f"--> Storage tool invoked - Session: {session_id}, File: {filename}")
logger.info(f"--> Successfully wrote {size_bytes} bytes to {s3_uri}")
logger.error(f"--> S3 write failed - Bucket: {bucket}, Key: {key}, Error: {error_code}")
```

### Part 2: Timestamp Calculation Fix

**File**: `src/agents/main.py`

**Time Injection**:
```python
import time
from datetime import datetime, timezone

# Calculate current time information at module level
current_timestamp = int(time.time())
current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# Read prompts
ANALYSIS_PROMPT = open(os.path.join(os.path.dirname(__file__), "analysis_prompt.md")).read()

# Inject into system prompt
ANALYSIS_PROMPT = ANALYSIS_PROMPT.replace("{current_timestamp}", str(current_timestamp))
ANALYSIS_PROMPT = ANALYSIS_PROMPT.replace("{current_datetime}", current_datetime)
```

**Example Values**:
```
Current Unix timestamp: 1761149264
Current date and time: 2025-10-22 16:07:44 UTC
```

**Why This Works**:

1. **Eliminates Ambiguity**: Explicit Unix timestamp provided (e.g., 1761149264)
2. **Provides Exact Formulas**: Pre-calculated constants (1296000 = 15 * 86400)
3. **Enables Verification**: Expected timestamps are predictable from telemetry
4. **Supports Retry Logic**: Each retry uses correct current timestamp

### Part 3: Prompt Improvements

**S3 Write Requirements Section**:

**Before**:
```markdown
- Save the full report as text to s3://{s3_bucket_name}/<session_id>/cost_report.txt
- Save supporting evidence to s3://{s3_bucket_name}/<session_id>/evidence.txt
- Overwrite is allowed; ensure idempotency by using the same keys
```

**After**:
```markdown
- Use the storage tool to save files to S3:
  - Save the full report by calling storage with action="write", filename="cost_report.txt", and content
  - Save supporting evidence by calling storage with action="write", filename="evidence.txt", and content
- The storage tool automatically handles:
  - Session ID prefixing - files are saved under the session_id prefix
  - S3 bucket configuration - uses the S3_BUCKET_NAME environment variable
  - UTF-8 encoding and proper content type
- Check storage tool responses:
  - If success is true, extract the s3_uri field
  - If success is false, log the error message in "Gaps & Limitations"
- If storage operations fail, include error details but continue with workflow
```

**Benefits**:
- **Clearer Instructions**: Focus on what to do, not how to do it
- **Error Handling**: Explicit guidance on checking responses
- **Graceful Degradation**: Continue workflow even if S3 writes fail
- **Reduced Complexity**: No AWS API details in prompt


## Key Learnings

### 1. Tool Abstraction Value

**Lesson**: Dedicated tools simplify prompts and improve maintainability
- Extract AWS operations into reusable tools
- Provide semantic interfaces (storage vs use_aws)
- Enable independent testing and debugging
- Follow consistent patterns across tools

**Best Practice**: Create specialized tools for common operations rather than using generic AWS tools

### 2. LLM Time Awareness

**Lesson**: LLMs don't have inherent time awareness
- Cannot assume LLM knows "current date"
- Must explicitly provide temporal context
- Ambiguous instructions lead to unpredictable behavior
- Provide exact values, not calculations

**Best Practice**: Always inject current timestamp for time-sensitive operations

### 3. Explicit Over Implicit

**Lesson**: Explicit values are better than implicit calculations
- "Use {current_timestamp}" > "Calculate current time"
- Exact formulas > General instructions
- Pre-calculated constants > Runtime arithmetic
- Verifiable behavior > Assumed behavior

**Best Practice**: Provide exact values and formulas in prompts
