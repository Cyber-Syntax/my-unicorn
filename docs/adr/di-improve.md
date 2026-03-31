## Strategic Architecture Improvement Plan for `ServiceContainer` DI

### Current State Assessment

Your `ServiceContainer` is a well-structured **hand-rolled composition root** with lazy singleton properties and factory methods. The fundamentals are sound - you should keep this approach. Here's what works well and what needs attention.

**What's working well:**

- Lazy initialization via `@property` - clean, Pythonic
- Clear separation: CLI layer creates containers, core layer stays unaware
- Good docstrings and well-organized service graph
- Singleton semantics for shared resources (session, clients)
- Dedicated `cleanup()` for resource management

---

### Issue 1: Duplicate Service Wiring (HIGH priority)

`InstallApplicationService` has **its own lazy initialization** that duplicates the container's role:

In install_service.py:

```python
# InstallApplicationService creates its OWN DownloadService, 
# FileOperations, PostDownloadProcessor, InstallHandler internally
@property
def download_service(self) -> DownloadService:
    if self._download_service is None:
        self._download_service = DownloadService(
            self.session, self.progress_reporter
        )  # ← Bypasses container's singleton!
    return self._download_service
```

Meanwhile, the container also has `self.download_service` as a singleton property. When `create_install_application_service()` is called, the service gets `session` and `github_client` from the container but then creates its **own parallel** `DownloadService` and `InstallHandler` -- missing `auth_manager`, `verification_service`, and `backup_service` that the container's versions include.

**Recommendation:** Choose one of:

- **Option A (recommended):** Make `InstallApplicationService` accept fully-constructed dependencies (inject `InstallHandler` directly instead of raw primitives). The service becomes a pure orchestrator with no wiring responsibility.
- **Option B:** Remove `InstallApplicationService`'s lazy properties and inject all services from the container factory method.

This same analysis applies to how `InstallHandler.create_default()` duplicates wiring in handler.py - that factory method should be deprecated in favor of container-driven construction.

---

### Issue 2: No Async Context Manager (MEDIUM priority)

Every command handler repeats this pattern:

```python
container = ServiceContainer(config_manager=..., progress_reporter=...)
try:
    service = container.create_install_application_service()
    results = await service.install(targets, options)
finally:
    await container.cleanup()
```

The Pythonic approach is `__aenter__`/`__aexit__`:

```python
async with ServiceContainer(
    config_manager=self.config_manager,
    progress_reporter=progress_display,
) as container:
    service = container.create_install_application_service()
    results = await service.install(targets, options)
```

**Implementation:** Add `__aenter__` and `__aexit__` to `ServiceContainer`:

```python
async def __aenter__(self) -> "ServiceContainer":
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
    await self.cleanup()
```

Keep `cleanup()` as public API for backward compatibility. This is zero-risk and reduces boilerplate across all 3 command handlers.

---

### Issue 3: Inconsistent Factory vs Singleton Semantics (MEDIUM priority)

| Method | Behavior | Confusing? |
|--------|----------|------------|
| `create_install_handler()` | Creates **new** instance each call | No |
| `create_install_application_service()` | Creates **new** instance each call | No |
| `create_update_manager()` | Creates **new** instance each call | No |
| `create_update_application_service()` | Creates **new** instance each call | No |
| `create_remove_service()` | Returns **singleton** (delegates to `self.remove_service`) | **Yes** |

`create_remove_service()` violates the `create_*` naming contract. It's a factory method name that returns a cached singleton.

**Recommendation:** Either:

- Rename to just expose `self.remove_service` directly (callers already use `container.remove_service` via the property)
- Or have all `create_*` methods return new instances consistently

Since `RemoveHandler` is the only caller, just use `container.remove_service` directly and deprecate `create_remove_service()`.

---

### Issue 4: Testing Requires Excessive Patching (MEDIUM priority)

Tests in test_container.py require patching 8+ classes per test:

```python
with (
    patch("my_unicorn.cli.container.aiohttp.ClientSession"),
    patch("my_unicorn.cli.container.GitHubAuthManager.create_default"),
    patch("my_unicorn.cli.container.DownloadService"),
    patch("my_unicorn.cli.container.FileOperations"),
    patch("my_unicorn.cli.container.GitHubClient"),
    patch("my_unicorn.cli.container.VerificationService"),
    patch("my_unicorn.cli.container.BackupService"),
    patch("my_unicorn.cli.container.PostDownloadProcessor"),
    patch("my_unicorn.cli.container.InstallHandler") as mock_handler,
):
```

**Recommendation:** Allow service overrides via constructor or setter:

```python
class ServiceContainer:
    def __init__(
        self,
        config_manager: ConfigManager | None = None,
        progress_reporter: ProgressReporter | None = None,
        *,
        # Optional overrides for testing
        session: aiohttp.ClientSession | None = None,
        auth_manager: GitHubAuthManager | None = None,
    ) -> None:
        self.config = config_manager or ConfigManager()
        self.progress = progress_reporter or NullProgressReporter()
        self._session = session          # Pre-injected if provided
        self._auth_manager = auth_manager
        # ... etc
```

This lets tests inject mocks directly without patching:

```python
container = ServiceContainer(
    config_manager=mock_config,
    session=mock_session,
    auth_manager=mock_auth,
)
```

Alternatively, a more Pythonic approach is a `with_overrides()` method or a separate `TestServiceContainer` subclass.

---

### Issue 5: Concrete Dependencies Instead of Protocols (LOW-MEDIUM priority)

Only `ProgressReporter` has a Protocol interface. All other services (`DownloadService`, `GitHubClient`, `VerificationService`, etc.) are concrete types. This means:

- The container is tightly coupled to implementations
- Protocol-based testing isn't possible (everything needs `patch()`)

**Recommendation (incremental):** For the most-mocked services, introduce protocols:

```python
# core/protocols/download.py
class DownloadProtocol(Protocol):
    async def download_file(
        self, url: str, dest: Path, ...
    ) -> Path: ...
```

Start with 2-3 key protocols for the services that are most painful to test. This isn't urgent but improves architecture over time.

---

### Issue 6: Container Created Per-Command, Not Shared (LOW priority, informational)

Each command handler creates its own `ServiceContainer` instance. For a CLI tool that runs one command per invocation, this is **fine and correct**. No change needed here - just noting it's intentional and appropriate for your use case.

---

### Implementation Roadmap

| Phase | Changes | Risk | Effort |
|-------|---------|------|--------|
| **Phase 1** | Add `__aenter__`/`__aexit__` to `ServiceContainer`, update 3 command handlers | Very Low | ~1 hour |
| **Phase 2** | Fix `create_remove_service()` naming inconsistency | Very Low | ~30 min |
| **Phase 3** | Add constructor overrides for testing (`session=`, `auth_manager=`) | Low | ~2 hours |
| **Phase 4** | Refactor `InstallApplicationService` to accept injected `InstallHandler` instead of creating its own | Medium | ~4 hours |
| **Phase 5** | Deprecate `InstallHandler.create_default()` static factory | Low | ~1 hour |
| **Phase 6** | Introduce 2-3 key Protocols for most-patched services | Low | ~3 hours |

### What NOT to Change

- **Don't adopt a DI framework** (like `dependency-injector`, `inject`, `python-inject`). Your project is a CLI tool, not a web server. Hand-rolled DI is the Pythonic way for this scale. Frameworks add complexity, magic, and another dependency for marginal benefit.
- **Don't make the container a singleton module-level object.** Per-command creation is correct for CLI tools.  
- **Don't refactor the lazy `@property` pattern.** It's clean, readable, and idiomatic Python.

---
