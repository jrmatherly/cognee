"""Tests for API error handling utilities."""

import pytest
from unittest.mock import patch, MagicMock

from cognee.api.shared.error_handling import (
    create_error_response,
    create_validation_error_response,
    SAFE_ERROR_MESSAGES,
    DEFAULT_ERROR_MESSAGE,
)


class TestCreateErrorResponse:
    """Tests for create_error_response function."""

    def test_returns_json_response(self):
        """Should return a JSONResponse."""
        from fastapi.responses import JSONResponse

        error = ValueError("test error")
        response = create_error_response(error)

        assert isinstance(response, JSONResponse)

    def test_uses_default_status_code_500(self):
        """Should use status code 500 by default."""
        error = ValueError("test error")
        response = create_error_response(error)

        assert response.status_code == 500

    def test_uses_custom_status_code(self):
        """Should use provided status code."""
        error = ValueError("test error")
        response = create_error_response(error, status_code=400)

        assert response.status_code == 400

    def test_includes_error_id_by_default(self):
        """Should include correlation error_id by default."""
        error = ValueError("test error")
        response = create_error_response(error)

        # Parse response body
        import json
        body = json.loads(response.body)

        assert "error_id" in body
        assert len(body["error_id"]) == 8  # UUID[:8]

    def test_excludes_error_id_when_disabled(self):
        """Should not include error_id when include_error_id=False."""
        error = ValueError("test error")
        response = create_error_response(error, include_error_id=False)

        import json
        body = json.loads(response.body)

        assert "error_id" not in body

    def test_sanitizes_value_error(self):
        """Should return safe message for ValueError."""
        error = ValueError("sensitive internal details here")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[ValueError]
        assert "sensitive" not in body["error"]

    def test_sanitizes_type_error(self):
        """Should return safe message for TypeError."""
        error = TypeError("internal type mismatch")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[TypeError]

    def test_sanitizes_permission_error(self):
        """Should return safe message for PermissionError."""
        error = PermissionError("secret file access denied")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[PermissionError]
        assert "secret" not in body["error"]

    def test_sanitizes_file_not_found_error(self):
        """Should return safe message for FileNotFoundError."""
        error = FileNotFoundError("/etc/passwd not found")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[FileNotFoundError]
        assert "passwd" not in body["error"]

    def test_sanitizes_key_error(self):
        """Should return safe message for KeyError."""
        error = KeyError("internal_secret_key")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[KeyError]
        assert "internal_secret" not in body["error"]

    def test_sanitizes_connection_error(self):
        """Should return safe message for ConnectionError."""
        error = ConnectionError("database at 10.0.0.5:5432 refused")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[ConnectionError]
        assert "10.0.0.5" not in body["error"]

    def test_sanitizes_timeout_error(self):
        """Should return safe message for TimeoutError."""
        error = TimeoutError("connection to internal-service timed out")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == SAFE_ERROR_MESSAGES[TimeoutError]
        assert "internal-service" not in body["error"]

    def test_uses_default_message_for_unknown_error(self):
        """Should use default message for unmapped exceptions."""

        class CustomInternalError(Exception):
            pass

        error = CustomInternalError("super secret internal details")
        response = create_error_response(error)

        import json
        body = json.loads(response.body)

        assert body["error"] == DEFAULT_ERROR_MESSAGE
        assert "secret" not in body["error"]

    def test_logs_full_error_details(self):
        """Should log full error details server-side."""
        error = ValueError("sensitive internal details")

        with patch("cognee.api.shared.error_handling.logger") as mock_logger:
            create_error_response(error)

            # Verify logger was called with full details
            mock_logger.error.assert_called_once()
            call_args = str(mock_logger.error.call_args)
            assert "ValueError" in call_args
            assert "sensitive" in call_args

    def test_logs_with_custom_level(self):
        """Should log with specified log level."""
        error = ValueError("test")

        with patch("cognee.api.shared.error_handling.logger") as mock_logger:
            create_error_response(error, log_level="warning")
            mock_logger.warning.assert_called_once()

    def test_logs_with_error_id(self):
        """Should include error_id in log message."""
        error = ValueError("test")

        with patch("cognee.api.shared.error_handling.logger") as mock_logger:
            response = create_error_response(error)

            import json
            body = json.loads(response.body)
            error_id = body["error_id"]

            call_args = str(mock_logger.error.call_args)
            assert error_id in call_args


class TestCreateValidationErrorResponse:
    """Tests for create_validation_error_response function."""

    def test_returns_json_response(self):
        """Should return a JSONResponse."""
        from fastapi.responses import JSONResponse

        response = create_validation_error_response("Invalid email format")
        assert isinstance(response, JSONResponse)

    def test_uses_default_status_code_400(self):
        """Should use status code 400 by default."""
        response = create_validation_error_response("Invalid input")
        assert response.status_code == 400

    def test_uses_custom_status_code(self):
        """Should use provided status code."""
        response = create_validation_error_response("Not found", status_code=404)
        assert response.status_code == 404

    def test_includes_error_message(self):
        """Should include the provided error message."""
        response = create_validation_error_response("Email is required")

        import json
        body = json.loads(response.body)

        assert body["error"] == "Email is required"

    def test_includes_field_when_provided(self):
        """Should include field name when provided."""
        response = create_validation_error_response(
            "Email is required",
            field="email"
        )

        import json
        body = json.loads(response.body)

        assert body["error"] == "Email is required"
        assert body["field"] == "email"

    def test_excludes_field_when_not_provided(self):
        """Should not include field key when not provided."""
        response = create_validation_error_response("Invalid input")

        import json
        body = json.loads(response.body)

        assert "field" not in body


class TestSafeErrorMessages:
    """Tests for SAFE_ERROR_MESSAGES constant."""

    def test_all_common_exceptions_mapped(self):
        """Should have mappings for common exception types."""
        expected_types = [
            ValueError,
            TypeError,
            PermissionError,
            FileNotFoundError,
            KeyError,
            ConnectionError,
            TimeoutError,
        ]
        for exc_type in expected_types:
            assert exc_type in SAFE_ERROR_MESSAGES

    def test_messages_are_generic(self):
        """Safe messages should not reveal implementation details."""
        for exc_type, message in SAFE_ERROR_MESSAGES.items():
            # Messages should be generic and not contain technical terms
            assert "exception" not in message.lower()
            assert "error" not in message.lower() or message == "Invalid input provided"
            assert "stack" not in message.lower()
            assert "traceback" not in message.lower()

    def test_default_message_is_generic(self):
        """Default message should be generic."""
        assert DEFAULT_ERROR_MESSAGE == "An internal error occurred"
