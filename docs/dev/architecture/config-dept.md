## Technical Debt

### 1. CommentAwareConfigParser Complexity 🔴 **High Priority**

**Location**: `parser.py`, `CommentAwareConfigParser` class

**Issue**: Custom `write()` override relies on fragile string manipulation to preserve comments.

**Impact**:

- **Maintainability**: 100+ LOC for comment handling
- **Fragility**: Breaks if ConfigParser internal format changes
- **Testing burden**: Edge cases (multi-line comments, inline comments)

**Example Fragile Code**:

```python
def write(self, fp: TextIO) -> None:
    # Override ConfigParser.write() to preserve comments
    for section in self._sections:
        fp.write(f"[{section}]\n")
        for key, value in self._sections[section].items():
            # Manually reconstruct INI format
            comment = self._comments.get(section, {}).get(key, "")
            fp.write(f"{key} = {value} {comment}\n")
```

**Proposed Solution**:

- **Option 1**: Use TOML instead of INI (native comment support)
- **Option 2**: Accept comment loss (simpler code, document limitation)
- **Option 3**: Extract to standalone library (shared complexity)

**Effort**: Medium (2-3 days to migrate to TOML)

---

### 2. Schema-TypedDict Synchronization 🟡 **Medium Priority**

**Location**: `schemas/*.schema.json` + `types.py`

**Issue**: JSON schemas and TypedDict definitions must be manually kept in sync.

**Impact**:

- **Maintenance burden**: Every schema change requires 2 edits
- **Error risk**: Easy to forget updating TypedDict
- **No compile-time check**: Mismatches found at runtime

**Example Duplication**:

**Schema** (app_state_v2.schema.json):

```json
{
  "properties": {
    "source": {"enum": ["catalog", "url"]},
    "catalog_ref": {"type": ["string", "null"]}
  }
}
```

**TypedDict** (types.py):

```python
class AppStateConfig(TypedDict):
    source: str  # Should be Literal["catalog", "url"]
    catalog_ref: str | None
```

**Proposed Solutions**:

- **Option 1**: Generate TypedDicts from schemas (datamodel-code-generator)
- **Option 2**: Generate schemas from TypedDicts (pydantic)
- **Option 3**: Use pydantic models instead of TypedDict (runtime validation)

**Effort**: Medium (3-4 days to integrate codegen, test migration)

---

### 3. Deferred Logging in Migration 🟡 **Medium Priority**

**Location**: `migration/global_config.py`, `ConfigMigration` class

**Issue**: Migration uses deferred logging to avoid logger initialization during config load.

**Impact**:

- **Complexity**: Custom log buffering adds 50+ LOC
- **Delayed feedback**: Logs not visible until after migration
- **Thread-safety**: Deferred log list not thread-safe

**Current Code**:

```python
class ConfigMigration:
    def __init__(self, config_file: Path):
        self.deferred_logs: list[tuple[str, str]] = []
    
    def _log_deferred(self, level: str, message: str):
        self.deferred_logs.append((level, message))
    
    def migrate(self) -> bool:
        # ... migration logic ...
        self._log_deferred("INFO", "Migration complete")
        
        # Flush logs
        for level, message in self.deferred_logs:
            logger.log(getattr(logging, level.upper()), message)
```

**Proposed Solution**:

- **Option 1**: Refactor logger initialization to allow early setup
- **Option 2**: Pass logger as dependency (DI pattern)
- **Option 3**: Accept limitation, document why deferred logging needed

**Effort**: Low (1 day to refactor logger initialization)

---

### 4. Path Expansion Duplication 🟢 **Low Priority**

**Location**: `paths.py`, `global.py`

**Issue**: Path expansion logic (`expand_path()`) duplicated in multiple places.

**Impact**:

- **DRY violation**: Same logic in Paths.expand_path() and_extract_directory_config()
- **Inconsistency risk**: Different expansion behavior in different contexts

**Current Duplication**:

```python
# In paths.py
@classmethod
def expand_path(cls, path: str | Path) -> Path:
    return Path(path).expanduser().resolve()

# In global.py
def _extract_directory_config(...):
    cleaned_path = strip_comments(value)
    directory_config[key] = Paths.expand_path(cleaned_path)  # Uses Paths version
```

**Proposed Solution**:

- **Consolidate**: Always use `Paths.expand_path()`, remove duplicates
- **Effort**: Low (1 hour to consolidate, test)

---

### 5. No Caching of Configs 🟢 **Low Priority**

**Location**: `ConfigManager`, `AppConfigManager`, `CatalogLoader`

**Issue**: Every config load reads from disk (no in-memory cache).

**Impact**:

- **Performance**: Repeated loads re-parse JSON/INI
- **File I/O overhead**: Disk reads on every access

**Current Behavior**:

```python
# In AppConfigManager
def load_app_config(self, app_name: str) -> dict | None:
    # Always reads from disk
    raw = self.load_raw_app_config(app_name)
    return self._build_effective_config(raw)
```

**Proposed Solution**:

- **Option 1**: Add in-memory cache with TTL (cache invalidation complexity)
- **Option 2**: Accept limitation (configs rarely accessed in tight loops)

**Effort**: Medium (2 days to add cache, handle invalidation)

---

## Extension Points

### 1. Adding New Config Sources

**Use Case**: Support configs from environment variables, remote sources, etc.

**Approach**:

1. Create new manager class (e.g., `EnvConfigManager`)
2. Implement common interface (load/save methods)
3. Add to `ConfigManager` facade

**Example**:

```python
class EnvConfigManager:
    def load_global_config_from_env(self) -> GlobalConfig:
        return {
            "config_version": os.getenv("MY_UNICORN_VERSION", "1.1.0"),
            "log_level": os.getenv("MY_UNICORN_LOG_LEVEL", "INFO"),
            # ...
        }

# In ConfigManager
class ConfigManager:
    def __init__(self, ...):
        self.env_config_manager = EnvConfigManager()
    
    def load_global_config(self) -> GlobalConfig:
        # Try env first, fallback to file
        try:
            return self.env_config_manager.load_global_config_from_env()
        except KeyError:
            return self.global_config_manager.load_global_config()
```

---

### 2. Adding New Migration Paths

**Use Case**: Migrate from v2.0.0 to v3.0.0

**Approach**:

1. Bump `APP_CONFIG_VERSION` constant
2. Create v3 schema (`app_state_v3.schema.json`)
3. Add migration method to `AppConfigMigrator`

**Example**:

```python
# In AppConfigMigrator
def _migrate_v2_to_v3(self, old_config: dict, app_name: str) -> dict:
    # Transform v2 structure to v3
    new_config = {
        "config_version": "3.0.0",
        "source": old_config["source"],
        "catalog_ref": old_config["catalog_ref"],
        "state": old_config["state"],
        "overrides": old_config["overrides"],
        "new_field": "default_value"  # New in v3
    }
    return new_config

# In migrate_app()
if current_version.startswith("1."):
    migrated = self._migrate_v1_to_v2(config, app_name)
elif current_version.startswith("2."):
    migrated = self._migrate_v2_to_v3(config, app_name)  # New path
```

---

### 3. Adding New Validation Rules

**Use Case**: Validate additional security constraints (e.g., max file size)

**Approach**:

1. Add constraint to JSON schema
2. Update TypedDict if needed
3. Test with valid/invalid configs

**Example Schema Addition**:

```json
{
  "properties": {
    "state": {
      "properties": {
        "installed_path": {
          "type": "string",
          "maxLength": 1024  // New constraint
        }
      }
    }
  }
}
```

---

### 4. Supporting New Config Formats

**Use Case**: Support YAML configs alongside JSON

**Approach**:

1. Add YAML parser to dependencies
2. Create `YAMLAppConfigManager` subclass
3. Auto-detect format in `ConfigManager`

**Example**:

```python
class YAMLAppConfigManager(AppConfigManager):
    def load_raw_app_config(self, app_name: str) -> AppStateConfig | None:
        yaml_file = self.apps_dir / f"{app_name}.yaml"
        if yaml_file.exists():
            with yaml_file.open("r") as f:
                return yaml.safe_load(f)
        # Fallback to JSON
        return super().load_raw_app_config(app_name)
```

---

## Responsible AI (RAI) Footer

**RAI Considerations for Configuration Module**:

1. **Data Privacy**:
   - User paths in configs may contain sensitive information (usernames, directory structures)
   - GitHub tokens stored separately (keyring), never in config files
   - No telemetry data collected from config files

2. **Security**:
   - Input validation prevents path traversal attacks
   - GitHub identifiers sanitized to prevent injection
   - Schema validation enforces type safety

3. **Transparency**:
   - All config transformations logged
   - Migration creates backups for auditability
   - No hidden configuration sources

4. **User Control**:
   - Manual migration prevents unexpected changes
   - Comments preserved in global config (user notes)
   - Clear error messages guide user actions

5. **Reliability**:
   - Schema validation ensures data integrity
   - Fail-fast design prevents corrupt state propagation
   - Backup-before-modify pattern prevents data loss
