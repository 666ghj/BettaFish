"""
Anti-cheating test infrastructure.

Prevents fake implementations that:
1. Return hardcoded test data
2. Detect test environment and behave differently
3. Skip actual API calls
4. Pass tests but fail in production
"""
