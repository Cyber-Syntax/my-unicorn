# Python Development Guidelines

## Project Structure

- Put code in `src/`.
- Put tests in `tests/`.
- Put docs in `docs/`.
- Put configs in `config/`.
- Use `__init__.py` files to define package boundaries.
- Place reusable functions in their own modules.
- Order imports: standard library, third-party, then local.
- Use absolute imports over relative imports.
- Define public API with `__all__`.

## Code Style

- Prioritize code clarity over cleverness.
- Use snake_case naming convention.
- Avoid wildcard imports.
- Keep functions under 50 lines.
- Use f-strings for string formatting.
- Use pathlib for file operations.
- Replace magic numbers with named constants.
- Use guard clauses to reduce nesting.
- Extract repeated code into functions.
- Make code modular to improve testing and maintenance.
- Use ruff rulestyle for linting and formatting.
- Use match/case for pattern matching.
- Specify file encoding explicitly.

## Typing & Documentation

- Add type hints to all functions.
- Specify return type annotations.
- Use union types instead of Optional[].
- Write docstrings for public modules, classes, and functions.
- Keep docstrings under 100 characters per line.
- Show usage examples in module docstrings.
- Use Google-style docstrings.

## Comments

- Explain why code exists.
- Clarify complex logic.
- Don't comment on obvious code.

## Functions & Design

- Design single-purpose functions.
- Validate parameters at function start.
- Separate pure and stateful code.
- Prefer immutable data structures.
- Use context managers for resources.
- Use contextvars for async state.
- Use dataclasses for simple data holders.
- Leverage Python's built-in functions and standard library.

## Classes & OOP

- Apply single responsibility to modules and classes.
- Favor composition over inheritance.
- Use `@property` instead of getters/setters.
- Implement `__eq__` and `__hash__` when needed.
- Use `__slots__` to save memory when many instances.
- Avoid god classes.

## Error Handling

- Create custom exception classes.
- Catch specific exception types.
- Preserve error context with `raise...from`.
- Log exceptions with tracebacks.
- Log with `logging.exception()` without secrets.
- Redact secrets from logs.
- Validate inputs at system boundaries.
- Keep try blocks minimal.
- Use `with` or `finally` for cleanup.
- Check return values from functions that might fail.
- Use structured logging for traces.
- Use assertions to check assumptions.

## Security

- Validate and sanitize all external inputs.
- Use parameterized database queries.
- Validate file paths rigorously.
- Prevent directory traversal by validating paths.
- Avoid eval() with untrusted input.
- Load secrets from environment variables.
- Use bcrypt/Argon2 for password hashing.
- Generate unique salts per password.
- Use HTTPS for network communication.
- Never commit secrets.

## Configuration

- Keep config separate from code.
- Use environment variables for settings.
- Validate config at startup.
- Maintain separate configs per environment.

## Performance

- Profile code before optimizing.
- Choose appropriate data structures.
- Use generators for large datasets.
- Cache pure functions with `@lru_cache`.
- Avoid globals in hot paths.
- Use asyncio for I/O tasks.
- Limit threads for CPU tasks.
- Set timeouts on all blocking calls.
- Use `''.join()` for many strings.
- Consider JIT or Cython only for real bottlenecks.

## API Development

- Use `Bearer` for token auth.
- Validate request data rigorously.
- Validate inputs with Pydantic.
- Implement rate limiting.
- Implement OAuth2 or token-based auth.
- Return consistent error responses.

## Testing Guidelines

- All tests should be in ./tests directory
- Write pytest for all tests with fixtures.
- Mock external services in tests.
- Test error paths explicitly.
- Use Hypothesis for property testing.
- Run static type checks in CI.
- Focus on important behaviors, not coverage.
- Use dependency injection for testability.
- All tests should have typing annotations and docstrings
- Create __init__.py files in test directories if they don't exist