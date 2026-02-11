"""Pytest configuration and fixtures for E2E tests."""

import pytest

from tests.e2e.runner import E2ERunner
from tests.e2e.sandbox import SandboxEnvironment


@pytest.fixture
def sandbox_name(request: pytest.FixtureRequest) -> str:
    """Generate unique sandbox name from test function name.

    Creates a sandbox directory name based on the current test function
    name, enabling unique isolation for each test.

    Args:
        request: Pytest fixture request containing test metadata

    Returns:
        Test function name to use as sandbox directory name

    Example:
        def test_install_app(sandbox_name: str) -> None:
            # sandbox_name will be "test_install_app"
            with SandboxEnvironment(name=sandbox_name) as sandbox:
                ...
    """
    return str(request.node.name)


@pytest.fixture
def sandbox_env(sandbox_name: str) -> SandboxEnvironment:
    """Provide a configured SandboxEnvironment instance.

    Creates a SandboxEnvironment for test isolation with a unique name
    derived from the test function name.

    Args:
        sandbox_name: Unique sandbox name from sandbox_name fixture

    Returns:
        SandboxEnvironment instance ready for use in context manager

    Example:
        def test_install_app(sandbox_env: SandboxEnvironment) -> None:
            with sandbox_env:
                runner = E2ERunner(sandbox_env)
                result = runner.install("qownnotes")
                assert result.returncode == 0
    """
    return SandboxEnvironment(name=sandbox_name)


@pytest.fixture
def e2e_runner(sandbox_env: SandboxEnvironment) -> E2ERunner:
    """Provide an E2ERunner instance with sandbox environment.

    Creates an E2ERunner configured to execute CLI commands in the
    provided sandbox environment.

    Args:
        sandbox_env: SandboxEnvironment instance from sandbox_env fixture

    Returns:
        E2ERunner instance ready for CLI execution

    Note:
        Must be used within sandbox_env context manager:

        def test_install_app(
            sandbox_env: SandboxEnvironment,
            e2e_runner: E2ERunner
        ) -> None:
            with sandbox_env:
                result = e2e_runner.install("qownnotes")
                assert result.returncode == 0

    Example:
        def test_install_app(
            sandbox_env: SandboxEnvironment,
            e2e_runner: E2ERunner
        ) -> None:
            with sandbox_env:
                result = e2e_runner.install("qownnotes")
                # Verify installation succeeded
                assert result.returncode == 0
    """
    return E2ERunner(sandbox_env)
