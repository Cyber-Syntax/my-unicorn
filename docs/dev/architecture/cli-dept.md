## Technical Debt

### High Priority

1. **Inconsistent Dependency Injection**
   - **Issue**: UpgradeHandler doesn't inherit BaseCommandHandler and creates dependencies inline
   - **Impact**: Harder to test, inconsistent with other handlers
   - **Effort**: Medium (refactor UpgradeHandler to use DI)
   - **Risk**: Low (well-isolated handler)

2. **ServiceContainer Complexity**
   - **Issue**: 11 properties + 5 factories approaching complexity threshold
   - **Impact**: Harder to maintain, test, and reason about
   - **Effort**: High (split into multiple containers or introduce sub-containers)
   - **Risk**: Medium (affects all handlers)

3. **Manual Cleanup Pattern**
   - **Issue**: Requires try/finally in every handler (error-prone)
   - **Impact**: Resource leaks if developers forget cleanup
   - **Effort**: Low (add context manager protocol to ServiceContainer)
   - **Risk**: Low (backward compatible)

### Medium Priority

1. **No Explicit Handler Protocol**
   - **Issue**: BaseCommandHandler uses ABC but no runtime protocol (duck typing)
   - **Impact**: No type checker enforcement of handler interface
   - **Effort**: Low (add Protocol alongside ABC)
   - **Risk**: Low (additive change)

2. **Verbose Logging Setup in Runner**
   - **Issue**: CLIRunner manually manipulates logger handlers
   - **Impact**: Logging configuration mixed with orchestration logic
   - **Effort**: Medium (abstract into logger module)
   - **Risk**: Low (isolated to runner)

3. **Duplicate Service Instantiation**
   - **Issue**: Some handlers create services inline (e.g., CatalogHandler creates CatalogService)
   - **Impact**: Inconsistent with DI pattern, harder to mock
   - **Effort**: Medium (move all service creation to ServiceContainer)
   - **Risk**: Low (per-handler change)

### Low Priority

1. **Magic Numbers in Progress Estimation**
   - **Issue**: UpdateHandler uses hardcoded value (10) for progress total
   - **Impact**: Inaccurate progress bars
   - **Effort**: Low (calculate based on operations)
   - **Risk**: Negligible (cosmetic)

2. **Helper Module Over-Engineering Risk**
   - **Issue**: helpers.py could accumulate unrelated utilities
   - **Impact**: Module becomes catch-all for misc functions
   - **Effort**: Low (strict code review for new helpers)
   - **Risk**: Negligible (YAGNI applied)

---

## Extension Points

### 1. Adding New Commands

**Process**:

1. Create handler class in `cli/commands/new_handler.py`
2. Inherit from BaseCommandHandler
3. Implement `execute(args)` method
4. Add parser method in CLIParser (e.g., `_add_new_command()`)
5. Register in CLIRunner._init_command_handlers()

**Example Skeleton**:

```python
# cli/commands/export.py
from argparse import Namespace
from .base import BaseCommandHandler

class ExportHandler(BaseCommandHandler):
    async def execute(self, args: Namespace) -> None:
        # Validate input
        output_path = Path(args.output)
        
        # Use services from base class
        app_configs = self.config_manager.list_installed_apps()
        
        # Business logic delegation
        export_data = {"apps": app_configs}
        
        # Display results
        print(f"Exported to {output_path}")
```

---

### 2. Adding New Services to ServiceContainer

**Process**:

1. Add private attribute in `__init__`: `self._new_service = None`
2. Create lazy-loaded property:

   ```python
   @property
   def new_service(self) -> NewService:
       if self._new_service is None:
           self._new_service = NewService(dependencies...)
       return self._new_service
   ```

3. (Optional) Add factory method for complex workflows
4. Update cleanup if service requires resource release

---

### 3. Custom Progress Reporters

**Process**:

1. Implement ProgressReporter protocol:

   ```python
   class CustomProgressReporter:
       def update(self, description: str, advance: int = 1) -> None:
           # Custom implementation
       
       def finish(self) -> None:
           # Finalization
   ```

2. Inject into ServiceContainer:

   ```python
   progress = CustomProgressReporter()
   container = ServiceContainer(config_manager, progress)
   ```

---

### 4. Alternative Argument Parsers

**Process** (to replace argparse):

1. Implement CLIParser-compatible interface:

   ```python
   class NewCLIParser:
       def __init__(self, global_config: dict[str, Any]): ...
       def parse_args(self) -> Namespace: ...
   ```

2. Replace in CLIRunner initialization:

   ```python
   self.parser = NewCLIParser(self.global_config)
   ```

---

## Appendix

### A. File Manifest

```
cli/
├── __init__.py                    # Package exports
├── parser.py                      # 541 LOC - Argument parsing
├── runner.py                      # 169 LOC - Command orchestration
├── container.py                   # 449 LOC - DI container
├── upgrade.py                     # Standalone upgrade handler
└── commands/
    ├── __init__.py
    ├── base.py                    # 58 LOC - Abstract base handler
    ├── helpers.py                 # 97 LOC - Shared utilities
    ├── install.py                 # Install command handler
    ├── update.py                  # Update command handler
    ├── catalog.py                 # Catalog command handler
    ├── remove.py                  # Remove command handler
    ├── backup.py                  # Backup command handler
    ├── cache.py                   # Cache command handler
    ├── migrate.py                 # Migration command handler
    ├── token.py                   # Token management handler
    ├── auth.py                    # Auth status handler
    ├── config.py                  # Config display handler
    └── upgrade.py                 # Upgrade command handler
```

---

### B. Related Documentation

- **Architecture Decisions**: See `docs/` for ADRs (TBD - not yet created)
- **Testing Guide**: See `tests/README.md` (TBD)
- **Configuration Schema**: See `docs/config.md`
- **Development Workflow**: See `docs/developers.md`

---

### C. Metrics Summary

```
Component Statistics:
  Total Files: 17
  Total LOC: ~3,044
  Average LOC/File: ~179
  Largest File: parser.py (541 LOC)
  Smallest Handler: ~50 LOC

Design Pattern Usage:
  Command Pattern: 11 handlers
  Dependency Injection: ServiceContainer + BaseCommandHandler
  Factory Pattern: 5 factory methods
  Template Method: BaseCommandHandler.execute()
  Strategy Pattern: Service layer implementations
  Scoped Instances: 11 lazy-loaded container-scoped services (not global singletons)

Test Coverage (estimated):
  Handlers: ~90% (thin coordinators, well-tested)
  Parser: ~85% (subcommand variations)
  Runner: ~80% (routing logic)
  ServiceContainer: ~70% (factory methods)
```

---

## Responsible AI (RAI) Footer

**Documentation Metadata**:

- **Generated By**: Architecture Documentation Specialist Agent
- **Model**: Claude Sonnet 4.5 (GitHub Copilot)
- **Generation Date**: 2026-02-03
- **Human Review Required**: Yes (technical accuracy, completeness)
- **Known Limitations**:
    - Diagrams use Mermaid syntax (requires renderer support)
    - LOC counts based on terminal output (not verified line-by-line)
    - Code examples simplified for clarity (not production-ready)
    - Extension point examples are skeletons (not tested implementations)

**Usage Guidelines**:

- This document is a **living blueprint** subject to updates as CLI module evolves
- Diagrams should be validated against current codebase before making architectural decisions
- Code examples are illustrative—always refer to actual implementation for production use
- Technical debt section reflects point-in-time assessment (re-evaluate quarterly)

**Feedback Loop**:

- Report inaccuracies via GitHub issues with label `docs:architecture`
- Suggest improvements to architecture via ADR process
- Update this blueprint when making structural changes to CLI module

## Single-Instance Feature (New)

For a focused high-level architecture of the single-instance behavior,
see `docs/dev/architecture/single-instance.md`.

This companion doc covers the `CLIRunner` → `LockManager` boundary,
locking contract, execution flow, and user-visible failure modes.
