## Critical Technical Debt

### Files Exceeding 500 LOC Limit

| File | LOC | Limit | Overage | Priority | Reason for Bloat |
|------|-----|-------|---------|----------|------------------|
| [verification/service.py](../../src/my_unicorn/core/verification/service.py) | **1,376** | 500 | **+876 (2.8x)** | 🔴 **CRITICAL** | Dual verification methods, result handling, extensive error handling, logging |
| [workflows/update.py](../../src/my_unicorn/core/workflows/update.py) | **1,042** | 500 | **+542 (2.1x)** | 🔴 **CRITICAL** | Update checking, version comparison, backup orchestration, error handling |
| [backup.py](../../src/my_unicorn/core/backup.py) | **937** | 500 | **+437 (1.9x)** | 🟡 **HIGH** | Backup creation, restoration, metadata management, cleanup |
| [desktop_entry.py](../../src/my_unicorn/core/desktop_entry.py) | **667** | 500 | **+167 (1.3x)** | 🟢 **MEDIUM** | Desktop file generation, template rendering, validation |
| [workflows/install.py](../../src/my_unicorn/core/workflows/install.py) | **625** | 500 | **+125 (1.2x)** | 🟢 **MEDIUM** | Install orchestration, dual source handling, error recovery |

**Total Overage**: 2,147 LOC (4.3× the limit across 5 files)

---

### Refactoring Recommendations

#### 1. VerificationService (Priority: CRITICAL)

**Current State**: Single 1,376 LOC file handling both verification methods

**Recommended Split**:

```
verification/
  service.py (300 LOC)          # Coordinator, method selection
  digest_verifier.py (250 LOC)  # Digest method
  checksum_verifier.py (350 LOC) # Checksum file method
  result_builder.py (200 LOC)   # Result handling
  config.py (150 LOC)           # VerificationConfig dataclass
  verifier.py (400 LOC)         # Keep existing (hash computation)
  checksum_parser.py (551 LOC)  # Keep existing (parsing logic)
```

**Benefits**:

- Single Responsibility Principle per file
- Easier testing (mock one verifier)
- Reduced cognitive load

---

#### 2. UpdateManager (Priority: CRITICAL)

**Current State**: Single 1,042 LOC file handling check + perform update

**Recommended Split**:

```
workflows/
  update.py (400 LOC)           # Coordinator
  update_checker.py (300 LOC)   # Check updates, build UpdateInfo
  update_performer.py (350 LOC) # Perform updates, backup, restore
  update_info.py (150 LOC)      # UpdateInfo dataclass + helpers
```

**Pattern**: Separate read operations (check) from write operations (perform)

---

#### 3. BackupService (Priority: HIGH)

**Current State**: Single 937 LOC file handling all backup operations

**Recommended Split**:

```
core/
  backup.py (300 LOC)           # Coordinator
  backup_creator.py (250 LOC)   # Create backups
  backup_restorer.py (200 LOC)  # Restore backups
  backup_cleaner.py (150 LOC)   # Cleanup old backups
  backup_metadata.py (100 LOC)  # Metadata handling
```

---

#### 4. DesktopEntry (Priority: MEDIUM)

**Current State**: 667 LOC, mostly template rendering

**Recommended Split**:

```
core/
  desktop_entry.py (300 LOC)    # Coordinator
  desktop_template.py (200 LOC) # Template rendering
  desktop_validator.py (150 LOC) # Validation logic
```

---

#### 5. InstallHandler (Priority: MEDIUM)

**Current State**: 625 LOC, orchestrating install workflow

**Recommended Action**:

- Monitor: Currently just over limit (125 LOC)
- Consider Application Service pattern when refactoring
- Split if grows beyond 700 LOC

---

### Emerging Anti-Patterns

#### 1. God Objects

**VerificationService** exhibits god object characteristics:

- 1,376 LOC
- 2 verification methods
- Result building
- Error handling
- Progress reporting
- Configuration parsing

**Solution**: Apply Service Layer + Strategy pattern

---

#### 2. Long Methods

**Examples**:

- `VerificationService.verify_appimage()`: ~200 LOC
- `UpdateManager.perform_update()`: ~150 LOC
- `BackupService.create_backup()`: ~120 LOC

**Solution**: Extract methods, apply Command pattern

---

#### 3. Feature Envy

**PostDownloadProcessor** accesses many config fields:

```python
context.config["icon"]["install"]
context.config["desktop"]["create_entry"]
context.config["verification"]["skip"]
```

**Solution**: Create typed config objects, reduce dict access

---

## Dependencies

### Internal Dependencies (Within Core)

```
protocols/progress.py (base)
    ↑
    ├── download.py
    ├── verification/service.py
    ├── backup.py
    ├── workflows/install.py
    └── workflows/update.py

github/client.py (base)
    ↑
    ├── github/release_fetcher.py
    └── workflows/install.py

cache.py (base)
    ↑
    └── github/release_fetcher.py
```

**Dependency Principle**: Base services (protocols, client, cache) have no dependencies, higher-level services depend on base

---

### External Dependencies (Other Modules)

**Core → Config**:

- `ConfigManager`: Load/save app and global config
- `CatalogLoader`: Load catalog entries

**Core → UI**:

- `ProgressReporter`: Protocol implemented by UI layer
- UI imports Core (not vice versa) ✅ Dependency inversion

**Core → Utils**:

- `appimage_utils`: Asset selection helpers
- `version_utils`: Version comparison
- `download_utils`: URL parsing

**Core → Exceptions**:

- Custom exception classes

---

### Third-Party Dependencies

| Package | Purpose | Usage in Core |
|---------|---------|---------------|
| **aiohttp** | Async HTTP client | GitHub API, downloads |
| **orjson** | Fast JSON parsing | Cache serialization |
| **uvloop** | Fast event loop | Async performance boost |
| **keyring** | OS keyring access | Token storage |
| **hashlib** | Hash computation | SHA256/SHA512 verification |

---

## Extension Points

### 1. New Verification Methods

**Interface**: `VerificationService.verify_appimage()`

**How to Add**:

1. Create new verifier class (e.g., `GPGVerifier`)
2. Implement method in `VerificationService`
3. Add selection logic based on config/availability

**Example**: GPG signature verification

---

### 2. New Progress Implementations

**Interface**: `ProgressReporter` protocol

**How to Add**:

1. Implement protocol methods
2. Inject into services via constructor
3. No changes to core services needed

**Example**: Web-based progress (WebSocket updates)

---

### 3. New Download Strategies

**Interface**: `DownloadService`

**How to Add**:

1. Subclass or replace `DownloadService`
2. Inject via ServiceContainer
3. Maintain same async interface

**Example**: BitTorrent downloads, mirror selection

---

### 4. New Workflow Steps

**Interface**: `PostDownloadProcessor`

**How to Add**:

1. Add new processing step to workflow
2. Update `PostDownloadContext` with new data
3. Implement in processor

**Example**: AppImage sandboxing (Firejail integration)

---

### 5. New Cache Backends

**Interface**: `ReleaseCacheManager`

**How to Add**:

1. Implement cache manager with same interface
2. Support TTL validation
3. Inject via ServiceContainer

**Example**: Redis cache, SQLite cache
