# ADR-001: CLI Technical Debt Resolution

## Status

Proposed

## Context

The CLI module of my-unicorn has accumulated technical debt across several key areas that impact maintainability, testability, and consistency. This debt manifests in three primary forms:

### 1. Inconsistent Dependency Injection Patterns

The current CLI architecture employs a ServiceContainer-based dependency injection system with BaseCommandHandler as the foundation for most command handlers. However, several inconsistencies undermine this pattern:

- **UpgradeHandler Non-Compliance**: The UpgradeHandler doesn't inherit from BaseCommandHandler and creates dependencies inline, breaking the established DI pattern and making it harder to test in isolation
- **Direct Service Instantiation**: Some handlers (e.g., CatalogHandler) create services directly rather than utilizing the ServiceContainer, leading to inconsistent dependency management
- **Mixed Injection Patterns**: The current system uses both constructor injection (ServiceContainer → BaseCommandHandler) and property-based lazy loading within the container

### 2. ServiceContainer Complexity Threshold

The current ServiceContainer has grown to approach complexity limits:

- **Size Metrics**: 11 properties + 5 factory methods approaching the maintainability threshold
- **Single Responsibility Violation**: The container manages too many diverse services (config, auth, cache, HTTP, progress, workflows, desktop integration, backup, icon management, file operations, removal)
- **Testing Challenges**: The large container makes unit testing difficult as many unrelated services get instantiated together

### 3. Manual Resource Management Anti-Pattern

The current system requires manual cleanup patterns that are error-prone:

- **Try/Finally Requirement**: Every handler must implement try/finally blocks for resource cleanup
- **Developer Error Risk**: Forgotten cleanup can lead to resource leaks
- **Code Duplication**: Cleanup logic is repeated across handlers

### Business Impact

- **Maintenance Overhead**: Inconsistent patterns increase cognitive load for developers
- **Testing Friction**: Dependency injection inconsistencies make mocking and unit testing more complex  
- **Reliability Risk**: Manual cleanup patterns can lead to resource leaks
- **Extensibility Concerns**: Adding new commands or services requires navigating complex container relationships

## Decision

We will implement a standardized dependency injection architecture with automated resource management through the following approach:

### 1. ServiceContainer Decomposition Strategy

**Replace the monolithic ServiceContainer with a layered service architecture:**

```
CoreServices (foundational services)
├── ConfigManager
├── GitHubAuthManager  
├── HttpSessionManager
└── LoggerManager

InfrastructureServices (platform integration)
├── FileOperationsService
├── DesktopEntryService
├── IconService
└── ProgressReporterService

BusinessServices (domain workflows)  
├── InstallWorkflow
├── UpdateWorkflow
├── RemoveWorkflow
└── BackupService

UtilityServices (supporting functionality)
├── ReleaseCacheManager
└── TokenStorage
```

### 2. Dependency Injection Standardization

**Adopt constructor injection with explicit dependency declarations:**

- All command handlers will inherit from BaseCommandHandler
- Dependencies will be explicitly declared in constructor parameters
- ServiceContainers will use factory methods for complex service construction
- Lazy loading will be preserved only for expensive-to-create services

### 3. Automated Resource Management  

**Implement context manager protocol for automatic cleanup:**

```python
class ServiceContainer:
    async def __aenter__(self) -> 'ServiceContainer':
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Automatic cleanup of all services
        await self._cleanup_resources()
```

### 4. Handler Standardization Protocol

**Establish explicit handler interface with runtime enforcement:**

```python
from typing import Protocol

class CommandHandler(Protocol):
    async def execute(self, args: Namespace) -> None: ...
    async def cleanup(self) -> None: ...
```

## Rationale

### Why ServiceContainer Decomposition?

- **Single Responsibility**: Each container focuses on a specific domain (core, infrastructure, business, utilities)
- **Testability**: Smaller containers enable more focused unit tests with fewer mock dependencies
- **Maintainability**: Clear service boundaries reduce cognitive overhead when adding new functionality
- **Performance**: Lazy loading can be applied selectively to expensive services rather than all-or-nothing

### Why Constructor Injection Over Property Injection?

- **Explicit Dependencies**: Constructor parameters make dependencies visible at compile time
- **Immutability**: Services can be immutable after construction
- **Testing**: Easier to mock specific dependencies without affecting others
- **Type Safety**: Better static analysis and IDE support

### Why Context Manager Approach?

- **Automatic Cleanup**: Eliminates manual try/finally patterns
- **Pythonic**: Leverages established Python resource management idioms
- **Backward Compatibility**: Can be adopted incrementally without breaking existing handlers
- **Error Safety**: Cleanup occurs even during exception conditions

### Why Handler Protocol Addition?

- **Type Safety**: Runtime enforcement of handler interface contracts
- **Documentation**: Protocol serves as living documentation of handler requirements
- **IDE Support**: Better autocomplete and static analysis
- **Future-Proofing**: Enables alternative handler implementations

## Consequences

### Positive Outcomes

**Improved Maintainability**

- Clear service boundaries reduce complexity when adding new commands
- Standardized dependency injection patterns reduce cognitive load
- Automated resource management eliminates manual cleanup errors

**Enhanced Testability**  

- Smaller service containers enable focused unit tests
- Constructor injection simplifies mocking specific dependencies
- Protocol enforcement catches interface violations at test time

**Better Reliability**

- Context manager cleanup eliminates resource leak risks
- Consistent error handling patterns across all handlers  
- Type safety improvements reduce runtime errors

**Increased Extensibility**

- Clear extension points for new services and commands
- Layered architecture supports incremental feature addition
- Protocol-based handlers enable alternative implementations

### Negative Outcomes

**Migration Complexity**

- All existing handlers must be updated to new DI patterns
- ServiceContainer refactoring affects the entire CLI module
- Potential for introducing bugs during transition

**Temporary Performance Overhead**

- Additional abstraction layers may introduce minor performance cost
- Context manager protocol adds slight overhead to handler execution
- Multiple container instantiation vs single container

**Code Volume Increase**

- More explicit dependency declarations increase line count
- Protocol definitions add additional interface code
- Factory methods for complex services add boilerplate

**Learning Curve**

- Developers need to understand new service layer architecture
- Context manager patterns require additional Python knowledge
- Dependency injection principles may not be familiar to all contributors

## Alternatives Considered

### Alternative 1: Gradual ServiceContainer Split

**Approach**: Split ServiceContainer into 2-3 containers gradually

- **Pros**: Lower migration risk, incremental improvement
- **Cons**: Still maintains high complexity, doesn't address fundamental architectural issues
- **Rejection Reason**: Doesn't solve the root cause of container complexity

### Alternative 2: Service Locator Pattern

**Approach**: Replace dependency injection with service locator registry

- **Pros**: Simpler handler constructors, dynamic service discovery
- **Cons**: Hidden dependencies, harder to test, anti-pattern in modern DI
- **Rejection Reason**: Reduces testability and makes dependencies implicit

### Alternative 3: Factory Builder Pattern

**Approach**: Use builder pattern to construct service graphs

- **Pros**: Flexible service composition, clear construction steps
- **Cons**: Additional complexity, less standard than DI containers
- **Rejection Reason**: Adds complexity without clear benefits over constructor injection

### Alternative 4: Global Service Registry

**Approach**: Return to global singleton pattern with service registry

- **Pros**: Simple access pattern, no dependency passing required
- **Cons**: Testing difficulties, hidden dependencies, tight coupling
- **Rejection Reason**: Contradicts project's move away from singletons toward explicit DI

## Implementation Plan

### Phase 1: Foundation Setup (Week 1-2)

**Priority: HIGH**

1. **Create Service Layer Architecture**
   - Implement CoreServices, InfrastructureServices, BusinessServices, UtilityServices containers
   - Move existing services from monolithic ServiceContainer to appropriate layers
   - Add factory methods for complex service construction

2. **Implement Context Manager Protocol**
   - Add `__aenter__` and `__aexit__` methods to service containers
   - Implement resource cleanup logic for each service type
   - Create ResourceManager utility for managing service lifecycles

3. **Add Handler Protocol Definition**
   - Define CommandHandler protocol with explicit interface requirements
   - Add runtime validation for protocol compliance
   - Update BaseCommandHandler to implement protocol

### Phase 2: Handler Standardization (Week 3-4)  

**Priority: HIGH**

1. **Refactor UpgradeHandler**
   - Make UpgradeHandler inherit from BaseCommandHandler
   - Move inline dependency creation to constructor injection
   - Update UpgradeHandler tests to use new DI pattern

2. **Standardize Service Creation**
   - Move CatalogHandler service instantiation to appropriate service container
   - Audit all handlers for inline service creation and move to containers
   - Update handler constructors to receive dependencies explicitly

3. **Remove Manual Cleanup Patterns**
   - Replace try/finally blocks with context manager usage
   - Update all handlers to use `async with service_container:` pattern
   - Remove manual cleanup methods from handlers

### Phase 3: Integration and Testing (Week 5-6)

**Priority: MEDIUM**

1. **Update CLIRunner Integration**
   - Refactor CLIRunner to use new layered service containers
   - Implement service container composition in runner initialization
   - Update runner cleanup to use context manager protocol

2. **Comprehensive Testing Updates**
   - Update all handler tests to use new dependency injection patterns
   - Create unit tests for individual service containers
   - Add integration tests for context manager resource cleanup

3. **Performance Validation**
   - Benchmark service container creation vs original ServiceContainer
   - Measure context manager overhead in handler execution
   - Optimize lazy loading for expensive service creation

### Phase 4: Documentation and Refinement (Week 7)

**Priority: LOW**

1. **Update Extension Point Documentation**
   - Document new service container architecture for extensions
   - Update handler creation guide with new DI patterns  
   - Create examples for adding new services to containers

2. **Migration Guide Creation**
   - Document breaking changes for external handler implementations
   - Provide migration steps for custom services
   - Create compatibility shims if needed for gradual adoption

3. **Code Quality Validation**
   - Run full test suite to ensure no regressions
   - Perform static analysis to validate type safety improvements
   - Review code coverage for new service layer architecture

## Timeline

**Total Estimated Effort**: 7 weeks
**Risk Level**: Medium (widespread changes but well-isolated)
**Dependencies**: None (CLI module changes are self-contained)

**Priority Justification**: High priority due to impact on developer productivity and system reliability. Dependency injection inconsistencies affect every new command handler, and manual cleanup patterns create reliability risks.

## Extension Points

### 1. Adding New Service Containers

**Process**: Create domain-specific containers for new service categories

```python
class ExternalIntegrationServices:
    def __init__(self, core_services: CoreServices):
        self.core_services = core_services
        self._webhook_service = None
        self._notification_service = None
    
    @property  
    def webhook_service(self) -> WebhookService:
        if self._webhook_service is None:
            self._webhook_service = WebhookService(self.core_services.http_session)
        return self._webhook_service
```

### 2. Custom Handler Implementations

**Process**: Implement CommandHandler protocol for alternative handler types

```python
class StreamingCommandHandler:
    def __init__(self, services: BusinessServices):
        self.services = services
    
    async def execute(self, args: Namespace) -> None:
        async with self.services:
            # Streaming implementation
            async for result in self.services.streaming_workflow:
                yield result
```

### 3. Service Factory Customization

**Process**: Override default service factories for specialized implementations

```python
class CustomCoreServices(CoreServices):
    def create_config_manager(self) -> ConfigManager:
        return CustomConfigManager(
            encryption_key=self.get_encryption_key()
        )
```

### 4. Resource Management Extensions

**Process**: Add custom cleanup logic to service containers

```python
class DatabaseServices:
    async def __aenter__(self) -> 'DatabaseServices':
        await self.connection_pool.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.connection_pool.close_all()
        await self.cleanup_temporary_tables()
```

### 5. Handler Middleware Support

**Process**: Add middleware pattern for cross-cutting concerns

```python
@middleware(LoggingMiddleware, TimingMiddleware)
class EnhancedCommandHandler(BaseCommandHandler):
    async def execute(self, args: Namespace) -> None:
        # Business logic with automatic logging and timing
        pass
```

### 6. Alternative Dependency Injection Frameworks

**Process**: Support integration with external DI frameworks

```python
class DIFrameworkAdapter:
    def __init__(self, external_container):
        self.container = external_container
    
    def resolve_services(self) -> ServiceContainer:
        return ServiceContainer(
            config_manager=self.container.resolve(ConfigManager),
            auth_manager=self.container.resolve(GitHubAuthManager)
        )
```
