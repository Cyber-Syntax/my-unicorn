# ADR-002: Core Module Technical Debt Resolution

## Status

Proposed

## Context

The Core module of the my-unicorn project has accumulated critical technical debt that significantly impacts maintainability, testability, and future development velocity. Analysis has identified multiple violations of the project's 500 LOC file size limit and emerging anti-patterns that require immediate attention.

### Critical Issues Identified

#### 1. Large File Violations (500+ LOC)

Five core files severely exceed the established 500 LOC limit:

- **verification/service.py**: 1,376 LOC (2.8x over limit) - handles dual verification methods with extensive error handling
- **workflows/update.py**: 1,042 LOC (2.1x over limit) - manages update checking, version comparison, and backup orchestration
- **backup.py**: 937 LOC (1.9x over limit) - handles backup creation, restoration, and metadata management
- **desktop_entry.py**: 667 LOC (1.3x over limit) - manages desktop file generation and template rendering
- **workflows/install.py**: 625 LOC (1.2x over limit) - orchestrates installation with dual source handling

#### 2. Emerging Anti-Patterns

- **God Objects**: VerificationService exhibits characteristics of a god object with 1,376 LOC handling multiple responsibilities including hash verification, signature checking, and error recovery
- **Long Methods**: Critical methods requiring decomposition:
    - `VerificationService.verify_appimage()`: ~200 LOC - requires extraction into verification steps using Command pattern
    - `UpdateManager.perform_update()`: ~150 LOC - needs separation of backup coordination, download, and validation steps
    - `BackupService.create_backup()`: ~120 LOC - should be split into metadata collection, file operations, and validation phases
- **Feature Envy**: PostDownloadProcessor exhibits Feature Envy pattern by directly accessing multiple config dict fields:
    - `context.config["icon"]["install"]` - should use typed IconConfig object
    - `context.config["desktop"]["create_entry"]` - should use typed DesktopConfig object
    - `context.config["verification"]["skip"]` - should use typed VerificationConfig object
    - Solution: Create typed configuration objects to reduce dict access and improve encapsulation

### Impact Assessment

- **Maintainability**: Large files make code navigation, understanding, and modification difficult
- **Testability**: Monolithic classes require extensive mock setup and have multiple failure points
- **Code Review**: Large files create cognitive overhead and increase review time
- **Parallel Development**: Large files increase merge conflict likelihood
- **Bug Surface**: More responsibilities per class increase potential failure modes

## Decision

Implement a comprehensive refactoring strategy using the **Service Layer + Strategy Pattern** approach to decompose large files and eliminate god objects while maintaining backward compatibility.

### Core Architectural Changes

#### 1. Verification Service Decomposition (verification/service.py)

- **Split by responsibility** (following source file structure recommendations):
    - `service.py` (300 LOC): Coordinator and method selection
    - `digest_verifier.py` (250 LOC): Digest verification method
    - `checksum_verifier.py` (350 LOC): Checksum file verification method
    - `result_builder.py` (200 LOC): Result handling and reporting
    - `config.py` (150 LOC): VerificationConfig dataclass
    - Existing files maintained: `verifier.py` (400 LOC) and `checksum_parser.py` (551 LOC)

- **Apply Strategy Pattern**:
    - `VerificationStrategy` interface for different verification methods
    - `DigestVerificationStrategy` and `ChecksumFileVerificationStrategy`
    - Runtime strategy selection based on available verification data

- **Long Method Decomposition Strategy**:
    - Extract `verify_appimage()` 200 LOC method into Command pattern:
        - `VerificationCommand` interface
        - `DigestVerificationCommand` for digest-based verification
        - `ChecksumFileVerificationCommand` for checksum file verification
        - Command executor for orchestration

#### 2. Update Workflow Decomposition (workflows/update.py)

- **Separate concerns**:
    - `UpdateChecker`: Version comparison and update detection
    - `BackupCoordinator`: Backup orchestration before updates
    - `UpdateExecutor`: Execute the actual update process
    - `UpdateWorkflow`: High-level workflow coordination

- **Extract reusable components**:
    - `VersionComparator`: Centralize version comparison logic
    - `ReleaseAnalyzer`: Analyze GitHub release data for updates

#### 3. Backup Service Decomposition (backup.py)

- **Split by operation**:
    - `BackupCreator`: Handle backup creation operations
    - `BackupRestorer`: Handle restoration operations  
    - `BackupMetadataManager`: Manage backup metadata and indexing
    - `BackupValidator`: Validate backup integrity

- **Apply Command Pattern**:
    - `BackupCommand` interface for backup operations
    - Concrete commands for create, restore, validate operations
    - Command queuing for batch operations

#### 4. Desktop Entry Service Decomposition (desktop_entry.py)

- **Separate template concerns**:
    - `DesktopEntryGenerator`: Core generation logic
    - `TemplateRenderer`: Handle template rendering and substitution
    - `IconPathResolver`: Resolve and validate icon paths
    - `CategoryMapper`: Map application categories to desktop categories

#### 5. Install Workflow Decomposition (workflows/install.py)

- **Split by source type**:
    - `GitHubInstaller`: Handle GitHub-based installations
    - `LocalInstaller`: Handle local AppImage installations
    - `InstallationValidator`: Validate installation success
    - `InstallWorkflowCoordinator`: Orchestrate installation process

### Service Integration Strategy

#### 1. Dependency Injection Compatibility

- All new services will be compatible with existing ServiceContainer
- Use constructor injection for dependencies
- Maintain interface contracts for backward compatibility

#### 2. Progressive Migration

- Implement new services alongside existing ones
- Use adapter pattern to maintain existing API surface
- Phase out old implementations once new ones are validated

## Rationale

### Why Service Layer + Strategy Pattern

1. **Single Responsibility Principle**: Each service handles one specific concern
2. **Open/Closed Principle**: New verification methods or backup strategies can be added without modifying existing code
3. **Dependency Inversion**: Services depend on abstractions, not concrete implementations
4. **Testability**: Smaller, focused services are easier to unit test
5. **Maintainability**: Smaller files are easier to understand and modify

### Why Progressive Migration

1. **Risk Mitigation**: Gradual migration reduces the chance of introducing breaking changes
2. **Continuous Integration**: Changes can be validated incrementally
3. **Team Velocity**: Development can continue on other features during refactoring
4. **Rollback Capability**: Individual services can be reverted if issues arise

## Consequences

### Positive Outcomes

1. **Improved Maintainability**: Smaller, focused files will be easier to navigate and understand
2. **Enhanced Testability**: Individual services can be tested in isolation with minimal setup
3. **Better Separation of Concerns**: Each service has a single, well-defined responsibility
4. **Increased Extensibility**: New verification methods, backup strategies, or installation sources can be added easily
5. **Reduced Bug Surface**: Smaller classes with fewer responsibilities have fewer potential failure modes
6. **Parallel Development**: Multiple developers can work on different services without conflicts

### Negative Outcomes

1. **Increased File Count**: More files to manage and navigate
2. **Initial Complexity**: Additional abstraction layers may seem over-engineered initially
3. **Migration Effort**: Significant development time required for refactoring
4. **Temporary Code Duplication**: Some duplication may exist during transition period
5. **Testing Overhead**: More services require more comprehensive test coverage

### Risk Mitigation

1. **Comprehensive Testing**: Implement thorough integration tests to ensure refactored services work correctly together
2. **Backward Compatibility**: Maintain existing APIs during migration to avoid breaking changes
3. **Documentation**: Update architectural documentation to reflect new service boundaries
4. **Code Review**: Mandatory review process for all refactoring changes

## Alternatives Considered

### Alternative 1: Extract Methods Only

**Description**: Simply extract long methods into smaller methods within existing classes

**Pros**:

- Minimal structural change
- Lower migration effort
- Maintains existing class boundaries

**Cons**:

- Doesn't address root cause of large files
- Still violates single responsibility principle  
- Limited improvement in testability

**Why Rejected**: Doesn't solve the fundamental architectural issues

### Alternative 2: Complete Rewrite

**Description**: Rewrite the entire core module from scratch with new architecture

**Pros**:

- Clean slate design
- No legacy constraints
- Optimal architecture from start

**Cons**:

- Extremely high risk
- Massive development effort
- High probability of introducing regressions
- Extended development timeline

**Why Rejected**: Risk-to-benefit ratio is too high for the project

### Alternative 3: Microservice Architecture

**Description**: Split core functionality into separate processes/services

**Pros**:

- Ultimate separation of concerns
- Independent scaling and deployment
- Technology diversity

**Cons**:

- Massive complexity increase
- Network communication overhead
- Deployment complexity
- Overkill for CLI application

**Why Rejected**: Inappropriate for a desktop CLI tool

## Implementation Plan

### Phase 1: Verification Service Decomposition (Week 1-3)

**Priority: CRITICAL** - 2.8x over limit, blocks other workflows

1. Create new verification service interfaces and implementations following 5-file structure
2. Implement strategy pattern for digest and checksum file methods
3. Apply Command pattern to decompose 200 LOC verify_appimage() method
4. Create adapter to maintain existing VerificationService API
5. Add comprehensive unit tests for new services
6. Integration testing with existing workflows

### Phase 2: Update Workflow Decomposition (Week 4-5)

**Priority: CRITICAL** - 2.1x over limit, core functionality

1. Extract update checking logic into dedicated UpdateChecker service
2. Separate backup coordination from update logic into UpdatePerformer
3. Decompose 150 LOC perform_update() method using Command pattern
4. Create version comparison utilities (VersionComparator)
5. Integration testing with GitHub API client
6. End-to-end update workflow validation

### Phase 3: Backup Service Decomposition (Week 6-7)

**Priority: HIGH** - 1.9x over limit, affects update reliability

1. Split backup.py into BackupCreator, BackupRestorer, and BackupMetadataManager
2. Decompose 120 LOC create_backup() method using Command pattern
3. Implement BackupCommand interface for different backup operations
4. Create backward-compatible facade for existing backup API
5. Comprehensive testing of backup and restoration workflows
6. Performance validation to ensure no degradation

### Phase 4: Desktop Entry Service Decomposition (Week 8)

**Priority: MEDIUM** - 1.3x over limit, affects user experience

1. Split desktop_entry.py into DesktopEntryGenerator, TemplateRenderer, and IconPathResolver
2. Create desktop template abstraction for rendering
3. Implement desktop category mapping logic
4. Comprehensive cross-platform desktop entry testing
5. Template validation and error handling

### Phase 5: Install Workflow Refinement (Week 9)

**Priority: MEDIUM** - 1.2x over limit, monitor for growth

1. Apply Application Service pattern to install workflow
2. Split by installation source (GitHubInstaller, LocalInstaller)
3. Create InstallationValidator for post-install verification
4. Monitor file size - split further if exceeds 700 LOC
5. Installation workflow validation across different AppImage types

### Phase 6: Feature Envy Resolution & Legacy Cleanup (Week 10)

1. Resolve Feature Envy in PostDownloadProcessor by implementing typed config objects
2. Replace direct dict access with IconConfig, DesktopConfig, VerificationConfig objects
3. Remove old implementations once new services are validated
4. Update documentation and architectural diagrams
5. Final integration testing and performance validation
6. Update developer guidelines and contribution docs

## Timeline

- **Total Effort**: 10 weeks (50 development days)
- **Priority**: Critical - must be completed to prevent further technical debt accumulation
- **Dependencies**: None - can start immediately
- **Risk Level**: Medium - significant refactoring but with backward compatibility safeguards
- **Success Metrics**: All files under 500 LOC, 90%+ test coverage maintained, no performance regressions

## Implementation Notes

### Testing Strategy

- Maintain existing integration tests to ensure no regressions
- Add comprehensive unit tests for each new service
- Use contract testing to validate service interfaces
- Performance benchmarking to ensure no degradation

### Documentation Updates

- Update architectural diagrams to reflect new service boundaries
- Create developer guidelines for adding new services
- Document service interfaces and contracts
- Update troubleshooting guides for new service structure

### Migration Safety

- Implement feature flags for gradual rollout
- Maintain parallel implementations during transition
- Comprehensive logging for troubleshooting migration issues
- Clear rollback procedures for each phase

## Extension Points

The refactored Core module will maintain and enhance extension points for future functionality:

### 1. New Verification Methods

**Interface**: `VerificationStrategy` protocol
**How to Add**:

1. Implement `VerificationStrategy` interface (e.g., `GPGVerificationStrategy`)
2. Register strategy with `VerificationCoordinator`
3. Add selection logic based on config/availability
**Example**: GPG signature verification, code signing validation

### 2. New Progress Implementations

**Interface**: `ProgressReporter` protocol (unchanged)
**How to Add**:

1. Implement protocol methods in new progress class
2. Inject into services via ServiceContainer
3. No changes to core services needed
**Example**: Web-based progress (WebSocket updates), desktop notifications

### 3. New Download Strategies

**Interface**: `DownloadService` protocol
**How to Add**:

1. Implement new download strategy maintaining async interface
2. Inject via ServiceContainer
3. Support existing progress reporting
**Example**: BitTorrent downloads, CDN mirror selection, resume capability

### 4. New Workflow Steps

**Interface**: `PostDownloadProcessor` extension
**How to Add**:

1. Add new processing step to install/update workflows
2. Update `PostDownloadContext` with required data
3. Implement processing logic with typed config objects
**Example**: AppImage sandboxing (Firejail integration), malware scanning

### 5. New Cache Backends

**Interface**: `ReleaseCacheManager` protocol
**How to Add**:

1. Implement cache manager with same TTL validation interface
2. Support atomic operations and concurrent access
3. Inject via ServiceContainer
**Example**: Redis distributed cache, SQLite persistent cache, in-memory cache

### 6. New Backup Strategies

**Interface**: `BackupStrategy` protocol (new)
**How to Add**:

1. Implement backup strategy (compression, encryption, remote storage)
2. Register with `BackupCreator`
3. Support metadata preservation
**Example**: Encrypted backups, cloud storage integration, incremental backups

## Dependency Architecture Principles

The refactored Core module follows these dependency principles:

### Base Services (No Dependencies)

- `protocols/progress.py`: Progress reporting contracts
- `github/client.py`: GitHub API client
- `cache.py`: Release cache management

### Higher-Level Services (Depend on Base)

- Verification services depend on progress protocols
- Workflow services depend on GitHub client and cache
- All services follow dependency inversion principle

### External Module Dependencies

- **Core → Config**: Typed config objects replace direct dict access
- **Core → UI**: UI implements progress protocols (dependency inversion maintained)
- **Core → Utils**: Utility functions for common operations
- **Core → Exceptions**: Custom exception hierarchy

This ADR addresses the most critical technical debt in the Core module and provides a clear path forward for resolving large file violations and architectural anti-patterns while maintaining system stability, backward compatibility, and extensibility.
