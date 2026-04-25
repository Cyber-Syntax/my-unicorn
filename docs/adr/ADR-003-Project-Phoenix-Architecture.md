# ADR-003: Project Phoenix - Clean Architecture & Strict Typing

## Status

Proposed

## Context

The current implementation of `my-unicorn` suffers from several architectural "smells":

1. **Shared State Mutation**: The GitHub client mutates state (task IDs) inside async blocks, leading to race conditions.
2. **Primitive Obsession**: Results are passed as `dict[str, Any]`, losing type safety.
3. **Blocking Logging**: File I/O in the logger blocks the `asyncio` event loop.
4. **God Objects**: The `ServiceContainer` and `VerificationService` handle too many responsibilities.

## Decision

We will rewrite the core using a **Hexagonal/Clean Architecture** approach with the following strict constraints:

### 1. Functional "Result" Pattern

Instead of swallowing exceptions or returning dicts, every service operation will return a `Result[T, E]` object or a dedicated `@dataclass`. This forces callers to handle failure cases and provides full IDE autocompletion.

### 2. Context-Scoped State (ContextVars)

To solve the progress-tracking race conditions, we will use `contextvars`. This allows the GitHub client to remain a stateless singleton while still knowing which specific "Progress Task" it is currently reporting for in the current async execution context.

### 3. Async-Safe Logging

We will implement a `QueueHandler` + `QueueListener` pattern. Log calls will be non-blocking; a background thread will handle the actual writing to the `RotatingFileHandler`.

### 4. Logic/Effect Separation

The core "Business Logic" (calculating paths, comparing versions) will be separated from "Side Effects" (writing to disk, calling APIs). This makes unit testing trivial as the logic becomes pure functions.

### 5. Proper Resilience

Retries will implement **Exponential Backoff with Jitter**.

## Rationale

- **Result Pattern**: Eliminates the "guessing game" of what a service returns.
- **ContextVars**: The standard way to handle request-scoped data in async Python without mutating shared objects.
- **Queue Logging**: Prevents UI stuttering during heavy log-to-file operations.

## Consequences

### Positive

- Zero race conditions in the event loop.
- High testability with minimal mocking.
- Faster execution due to removed I/O blocks.

### Negative

- Higher initial boilerplate (defining Result types and dataclasses).
- Steeper learning curve for contributors unfamiliar with functional-lite Python.

Project Phoenix: Architectural Refinement Plan
This plan outlines the strategic shift from an "Enterprise-lite" architecture, which has introduced unnecessary complexity and technical debt, towards a more functional, domain-driven, and strictly typed approach. The core principle is to simplify the codebase, enhance testability, and improve performance by embracing Python's asynchronous capabilities and modern design patterns, while preserving the proven Command Design Pattern for CLI operations.

I. Core Principles & Retained Patterns
Retain Command Design Pattern: The BaseCommandHandler and the overall command execution flow will be preserved. This pattern effectively decouples command invocation from its implementation, which is a solid and appropriate design for a CLI application.
Functional Core, Imperative Shell: Business logic should be as functional and stateless as possible, residing in a "core." Side effects (I/O, API calls, state changes) should be managed in an "imperative shell" that orchestrates these functional components.
Strict Typing & Immutability: Leverage Python's type hinting and dataclasses to ensure type safety, improve IDE support, and promote immutability for data structures.
Asynchronous by Design: All I/O-bound operations will be non-blocking, utilizing asyncio and aiohttp to maximize concurrency and responsiveness.
II. Elimination of Unnecessary Enterprise Patterns & Proposed Solutions
The following "enterprise design patterns" and architectural "smells" will be systematically addressed and replaced with more suitable, Pythonic, and functional approaches:

1. Monolithic Dependency Injection Container (ServiceContainer)
Problem: The current ServiceContainer has grown into a "God Object" with too many responsibilities, leading to high complexity, difficult testing, and a violation of the Single Responsibility Principle. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-001-CLI-Technical-Debt-Resolution.md, /home/developer/Documents/my-repos/my-unicorn/docs/adr/di-improve.md]
Solution: Decompose the ServiceContainer into a layered service architecture. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-001-CLI-Technical-Debt-Resolution.md] This will involve creating smaller, focused containers (e.g., CoreServices, InfrastructureServices, BusinessServices, UtilityServices) that manage specific sets of dependencies. Constructor injection with explicit dependency declarations will be the standard. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-001-CLI-Technical-Debt-Resolution.md]
Functional Aspect: Services within these decomposed containers should, where possible, expose methods that are pure functions, minimizing internal state and side effects.
2. Shared Mutable State & Race Conditions
Problem: The GitHub client currently mutates state (task IDs) within async blocks, which can lead to race conditions and unpredictable behavior in a concurrent environment. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md]
Solution: Implement contextvars for managing context-scoped state. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md] This allows components like the GitHub client to remain stateless singletons while still having access to execution-context-specific data (e.g., the current progress task ID).
3. Primitive Obsession & Weakly-Typed Dictionaries
Problem: Results and data are frequently passed around as dict[str, Any], leading to a loss of type safety, reduced IDE assistance, and a "guessing game" about data structure. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md]
Solution: Adopt a "Functional 'Result' Pattern" using Result[T, E] objects or dedicated @dataclass instances for all service operations and data transfer. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md] This enforces explicit handling of success and failure cases and provides full type safety.
4. Blocking I/O in Logging
Problem: File I/O operations within the logging system currently block the asyncio event loop, leading to performance degradation and UI stuttering. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md]
Solution: Implement an "Async-Safe Logging" mechanism using a QueueHandler and QueueListener pattern. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md] Log calls will be non-blocking, with a dedicated background thread handling the actual writing to the RotatingFileHandler.
5. "God Objects" & Overly Large Service Classes
Problem: Several core services, such as VerificationService, UpdateManager, BackupService, and DesktopEntry, exceed the established 500 LOC limit and handle too many responsibilities. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-002-Core-Technical-Debt-Resolution.md]
Solution: Apply "Logic/Effect Separation" and decompose these large services into smaller, more focused, and ideally pure functions or smaller classes. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md, /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-002-Core-Technical-Debt-Resolution.md] This will involve using patterns like the Strategy Pattern for different verification methods and splitting operations by responsibility (e.g., BackupCreator, BackupRestorer).
III. Implementation Roadmap
This rewrite will be executed in a phased approach, prioritizing foundational changes and high-impact refactorings.

Phase 1: Foundational Architecture & Tooling (High Impact, Low Risk)

Implement Result Pattern: Define generic Result[T, E] types and refactor initial service outputs to use them.
Integrate contextvars: Set up contextvars for progress reporting and other request-scoped data.
Async-Safe Logging: Implement the QueueHandler and QueueListener pattern for non-blocking logging.
Strict Typing Enforcement: Achieve 100% type hint coverage and configure mypy for strict enforcement.
Phase 2: CLI Dependency Injection Decomposition (Medium Impact, Medium Risk)

Decompose ServiceContainer: Break down the monolithic ServiceContainer into smaller, layered containers (e.g., CoreServices, InfrastructureServices, BusinessServices).
Standardize Constructor Injection: Ensure all services and handlers use explicit constructor injection.
Automated Resource Management: Implement **aenter** and **aexit** methods for service containers to manage resource cleanup automatically.
Phase 3: Core Service Decomposition & Functional Refinement (High Impact, High Risk)

Refactor "God Objects": Systematically decompose VerificationService, UpdateManager, BackupService, DesktopEntry, and other large services into smaller, more focused units.
Apply Logic/Effect Separation: Identify and separate pure business logic from side-effecting operations within these services.
Introduce Protocols: Define Protocol interfaces for key services to further decouple implementations and facilitate testing.
Phase 4: Continuous Improvement & Performance Optimization

Resilience Implementation: Implement exponential backoff with jitter for all GitHub API calls.
Performance Benchmarking: Continuously monitor and optimize performance, especially for concurrent operations.
Refinement: Identify further opportunities to introduce pure functions, reduce state, and enhance immutability across the codebase.
IV. Expected Benefits
Zero Race Conditions: Elimination of shared mutable state will prevent concurrency-related bugs. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md]
High Testability: Smaller, more focused, and functional components will be significantly easier to unit test with minimal mocking. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md, /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-001-CLI-Technical-Debt-Resolution.md]
Faster Execution: Non-blocking I/O and optimized architecture will lead to a more responsive and performant application. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-003-Project-Phoenix-Architecture.md]
Improved Maintainability: Clearer separation of concerns, smaller files, and strict typing will reduce cognitive load and make the codebase easier to understand and evolve. [cite: /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-001-CLI-Technical-Debt-Resolution.md, /home/developer/Documents/my-repos/my-unicorn/docs/adr/ADR-002-Core-Technical-Debt-Resolution.md]
Enhanced Reliability: Atomicity of operations and robust error handling will ensure a more stable user experience. [cite: /home/developer/Documents/my-repos/my-unicorn/PRD-001-Rewrite-Vision.md]
