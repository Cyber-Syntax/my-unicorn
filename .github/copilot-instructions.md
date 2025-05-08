You are an expert in Python for async-first, modular CLI applications, focused on package management and secure system operations.

## Project Structure

- Put code in `src/`.
- Put tests in `tests/`.
- Put docs in `docs/`.
- Put configs in `config/`.
- Use `__init__.py` files to define package boundaries.
- Order imports: standard library, third-party, then local.
- Use absolute imports over relative imports.

## Code Style

- Follow Single Responsibility Principle (SRP).
- Use DRY responsibility principle.
- Prioritize code clarity over cleverness.
- Use snake_case naming convention.
- Keep functions under 50 lines.
- Use f-strings for string formatting.
- Use pathlib for all file path operations.
- Replace magic numbers with named constants.
- Use guard clauses to avoid nested conditionals.
- Specify file encoding explicitly.
- Use logging over print.
- Avoid premature optimization.
- Avoid circular imports and tightly coupled modules.

## Typing & Documentation

- Add type hints to all functions.
- Add return type annotations explicitly.
- Write docstrings for public modules, classes, and functions.
- Keep docstrings concise and under 100 characters per line.
- Show usage examples in module docstrings.
- Use Google-style docstrings.

## Comments

- Explain why code exists.
- Clarify complex logic.
- Don't comment on obvious code.

## Functions & Design

- One function one responsibility.
- Validate parameters at function start.
- Prefer pure functions; separate stateful logic.
- Prefer immutable data structures.
- Use context managers for resources.
- Use contextvars for async state.
- Leverage Python's built-in functions and standard library.
- Use `match/case` for complex conditionals when appropriate.
- Avoid singleton patterns for better testability.

## Classes & OOP

- Desing single-purpose classes and methods.
- Prefer dataclasses for simple data containers.
- Favor composition over inheritance.
- Use `@property` instead of getters/setters.
- Implement `__eq__` and `__hash__` when needed.
- Use `__slots__` to save memory when many instances.
- Avoid god objects.

## Error Handling

- Handle errors and edge cases at the beginning of functions.
- Use early returns for error conditions to avoid deeply nested if statements.
- Create custom exception classes.
- Catch specific exception types.
- Preserve error context with `raise...from`.
- Log exceptions with tracebacks.
- Log with `logging.exception()` without secrets.
- Redact secrets from logs and prints.
- Validate inputs at system boundaries.
- Keep try blocks minimal.
- Use `with` or `finally` for cleanup.
- Check return values from functions that might fail.
- Use structured logging for traces.
- Use assertions to check assumptions.

## Security

- Validate and sanitize all external inputs.
- Use parameterized database queries.
- Validate file paths and names.
- Prevent directory traversal by validating paths.
- Avoid eval() with untrusted input.
- Load secrets from environment variables.
- Use bcrypt/Argon2 for password hashing.
- Generate unique salts per password.
- Use HTTPS for network communication.
- Make sure secrets aren't printed or logged.
- Secrets should be stored in a secure vault or service.

## Performance

- Use asyncio for I/O tasks.
- Profile code before optimizing.
- Choose appropriate data structures.
- Use generators for large datasets.
- Cache pure functions with `@lru_cache`.
- Avoid globals in hot paths.
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

- Use pytest for all tests with fixtures.
- Mock external services in tests.
- Test error paths explicitly.
- Use Hypothesis for property testing.
- Run static type checks in CI.
- Focus on important behaviors, not coverage.
- Use dependency injection for testability.
- All tests should have typing annotations and docstrings.
