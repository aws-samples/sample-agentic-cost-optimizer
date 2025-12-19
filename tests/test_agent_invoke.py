"""Unit tests for the agent invoke function with fire-and-forget async behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.main import background_task, invoke


@pytest.fixture
def mock_context():
    """Create a mock RequestContext with session_id."""
    context = MagicMock()
    context.session_id = "session-456"
    return context


@pytest.fixture
def mock_create_task():
    """Create a mock for asyncio.create_task that properly handles coroutines."""

    def consume_coroutine(coro):
        coro.close()
        return AsyncMock()

    return consume_coroutine


class TestInvokeFunction:
    """Test cases for the invoke function with fire-and-forget async behavior."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_successful_task_creation(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test successful task creation: invoke returns immediate success message."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_task_creation_failure(self, mock_create_task_patch, mock_record_event, mock_context):
        """Test task creation failure: invoke returns error message."""

        def consume_and_raise(coro):
            coro.close()
            raise Exception("Task creation failed")

        mock_create_task_patch.side_effect = consume_and_raise
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert "Error starting background processing: Task creation failed" in result["error"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_default_prompt_when_missing(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that default prompt 'Hello' is used when prompt is missing from payload."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_session_id_from_context(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that session_id is retrieved from context."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "test"}

        result = await invoke(payload, mock_context)

        assert "Started processing request for session session-456" in result["message"]
        assert result["session_id"] == "session-456"


class TestAgentConfiguration:
    """Test cases for agent configuration and setup."""

    def test_create_agent_requires_system_prompt(self):
        """Test that agent creation fails without a system prompt."""
        from src.agents.main import create_agent

        with pytest.raises(ValueError, match="system_prompt is required"):
            create_agent(system_prompt="")

        with pytest.raises(ValueError, match="system_prompt is required"):
            create_agent(system_prompt=None)

    @patch("src.agents.main.Agent")
    @patch("src.agents.main.BedrockModel")
    def test_create_agent_uses_default_boto_config(self, mock_bedrock_model, mock_agent):
        """Test that agent creation uses default boto config when not provided."""
        from src.agents.main import create_agent

        create_agent(system_prompt="Test prompt")

        mock_bedrock_model.assert_called_once()
        call_kwargs = mock_bedrock_model.call_args.kwargs
        assert "boto_client_config" in call_kwargs
        assert call_kwargs["boto_client_config"] is not None

    @patch("src.agents.main.Agent")
    @patch("src.agents.main.BedrockModel")
    def test_create_agent_uses_provided_boto_config(self, mock_bedrock_model, mock_agent):
        """Test that agent creation uses provided boto config."""
        from botocore.config import Config as BotocoreConfig

        from src.agents.main import create_agent

        custom_config = BotocoreConfig(retries={"max_attempts": 5})
        create_agent(system_prompt="Test prompt", boto_config=custom_config)

        mock_bedrock_model.assert_called_once()
        call_kwargs = mock_bedrock_model.call_args.kwargs
        assert call_kwargs["boto_client_config"] == custom_config

    @patch("src.agents.main.Agent")
    @patch("src.agents.main.BedrockModel")
    def test_create_agent_defaults_to_empty_tools(self, mock_bedrock_model, mock_agent):
        """Test that agent creation defaults to empty tools list."""
        from src.agents.main import create_agent

        create_agent(system_prompt="Test prompt")

        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args.kwargs
        assert call_kwargs["tools"] == []


class TestGraphBuilder:
    """Test cases for build_cost_optimization_graph function."""

    @patch("src.agents.main.GraphBuilder")
    def test_build_cost_optimization_graph(self, mock_graph_builder_class):
        """Test that build_cost_optimization_graph constructs graph correctly."""
        from src.agents.main import build_cost_optimization_graph

        mock_analysis_agent = MagicMock()
        mock_report_agent = MagicMock()

        mock_builder = MagicMock()
        mock_graph = MagicMock()
        mock_builder.build.return_value = mock_graph
        mock_graph_builder_class.return_value = mock_builder

        result = build_cost_optimization_graph(mock_analysis_agent, mock_report_agent)

        # Verify GraphBuilder was instantiated
        mock_graph_builder_class.assert_called_once()

        # Verify nodes were added
        assert mock_builder.add_node.call_count == 2
        mock_builder.add_node.assert_any_call(mock_analysis_agent, "analysis")
        mock_builder.add_node.assert_any_call(mock_report_agent, "report")

        # Verify edge was added
        mock_builder.add_edge.assert_called_once_with("analysis", "report")

        # Verify entry point was set
        mock_builder.set_entry_point.assert_called_once_with("analysis")

        # Verify timeout was set
        mock_builder.set_execution_timeout.assert_called_once_with(900)

        # Verify build was called
        mock_builder.build.assert_called_once()

        # Verify graph was returned
        assert result == mock_graph


class TestBackgroundTask:
    """Test cases for background_task function."""

    @pytest.mark.asyncio
    @patch("src.agents.main.record_event")
    @patch("asyncio.create_task")
    async def test_background_task_is_started(
        self, mock_create_task_patch, mock_record_event, mock_context, mock_create_task
    ):
        """Test that background task is started when invoke is called."""
        mock_create_task_patch.side_effect = mock_create_task
        payload = {"prompt": "hello"}

        result = await invoke(payload, mock_context)

        assert (
            result["message"]
            == "Started processing request for session session-456. Processing will continue in background."
        )
        assert result["session_id"] == "session-456"
        assert result["status"] == "started"
        mock_create_task_patch.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.agents.main.build_cost_optimization_graph")
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_success(self, mock_create_agent, mock_record_event, mock_build_graph):
        """Test successful background task execution with graph pattern."""
        mock_analysis_agent = MagicMock()
        mock_report_agent = MagicMock()
        mock_report_response = MagicMock()
        mock_report_response.message = "Report generated successfully"

        mock_create_agent.side_effect = [mock_analysis_agent, mock_report_agent]

        # Mock graph execution
        mock_graph = MagicMock()
        mock_graph_result = MagicMock()
        mock_graph_result.status.value = "completed"
        mock_graph_result.failed_nodes = 0
        mock_graph_result.completed_nodes = 2
        mock_graph_result.total_nodes = 2
        mock_graph_result.execution_time = 1000
        mock_node_result = MagicMock()
        mock_node_result.result = mock_report_response
        mock_graph_result.results = {"report": mock_node_result}

        mock_graph.invoke_async = AsyncMock(return_value=mock_graph_result)
        mock_build_graph.return_value = mock_graph

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result == mock_report_response
        mock_build_graph.assert_called_once_with(mock_analysis_agent, mock_report_agent)
        mock_graph.invoke_async.assert_called_once()
        assert mock_record_event.call_count == 1

    @pytest.mark.asyncio
    @patch("src.agents.main.build_cost_optimization_graph")
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_no_credentials_error(self, mock_create_agent, mock_record_event, mock_build_graph):
        """Test background task handles NoCredentialsError."""
        from botocore.exceptions import NoCredentialsError

        mock_analysis_agent = MagicMock()
        mock_report_agent = MagicMock()
        mock_create_agent.side_effect = [mock_analysis_agent, mock_report_agent]

        # Mock graph to raise NoCredentialsError during execution
        mock_graph = MagicMock()
        mock_graph.invoke_async = AsyncMock(side_effect=NoCredentialsError())
        mock_build_graph.return_value = mock_graph

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "NoCredentialsError"
        assert result["error_code"] == "NoCredentialsError"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]

    @pytest.mark.asyncio
    @patch("src.agents.main.build_cost_optimization_graph")
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_client_error(self, mock_create_agent, mock_record_event, mock_build_graph):
        """Test background task handles ClientError (e.g., ThrottlingException)."""
        from botocore.exceptions import ClientError

        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )
        mock_analysis_agent = MagicMock()
        mock_report_agent = MagicMock()
        mock_create_agent.side_effect = [mock_analysis_agent, mock_report_agent]

        # Mock graph to raise ClientError during execution
        mock_graph = MagicMock()
        mock_graph.invoke_async = AsyncMock(side_effect=throttling_error)
        mock_build_graph.return_value = mock_graph

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "ClientError"
        assert result["error_code"] == "ThrottlingException"
        assert result["error_message"] == "Rate exceeded"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]

    @pytest.mark.asyncio
    @patch("src.agents.main.build_cost_optimization_graph")
    @patch("src.agents.main.record_event")
    @patch("src.agents.main.create_agent")
    async def test_background_task_generic_exception(self, mock_create_agent, mock_record_event, mock_build_graph):
        """Test background task handles generic Exception."""
        mock_analysis_agent = MagicMock()
        mock_report_agent = MagicMock()
        mock_create_agent.side_effect = [mock_analysis_agent, mock_report_agent]

        # Mock graph to raise ValueError during execution
        mock_graph = MagicMock()
        mock_graph.invoke_async = AsyncMock(side_effect=ValueError("Invalid input"))
        mock_build_graph.return_value = mock_graph

        session_id = "test-session-123"
        user_message = "Analyze costs"

        result = await background_task(user_message, session_id)

        assert result["error"] == "Exception"
        assert result["error_type"] == "ValueError"
        assert result["error_message"] == "Invalid input"
        assert result["session_id"] == session_id
        assert result["status"] == "failed"

        assert mock_record_event.call_count == 1
        call_args = mock_record_event.call_args[1]
        assert "FAILED" in call_args["status"]
