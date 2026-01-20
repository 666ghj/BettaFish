"""
Anti-cheating test infrastructure.

Prevents fake implementations that:
1. Return hardcoded test data
2. Detect test environment and behave differently
3. Skip actual API calls
4. Pass tests but fail in production

Usage:
    from tests.anti_cheat import (
        NetworkCallValidator,
        DynamicQueryValidator,
        ResponseStructureValidator,
        ImplementationChecker,
        ASTChecker,
    )

    # Validate network calls are real
    result = await NetworkCallValidator.validate_async_network_call(
        my_async_func, iterations=3, min_variance_ms=50
    )
    assert result["pass"], "Likely mocked responses"

    # Validate implementation files
    result = ImplementationChecker.verify_implementation(Path("my_file.py"))
    assert result["pass"], "Implementation contains forbidden patterns"
"""

from .validators import (
    NetworkCallValidator,
    DynamicQueryValidator,
    ResponseStructureValidator,
)

from .checksum import (
    ImplementationChecker,
    ASTChecker,
)

__all__ = [
    # Validators
    "NetworkCallValidator",
    "DynamicQueryValidator",
    "ResponseStructureValidator",
    # Checksum/Implementation checkers
    "ImplementationChecker",
    "ASTChecker",
]
