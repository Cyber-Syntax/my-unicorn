# Upgrade Module Design Documentation

## Overview

The upgrade module (`cli/upgrade.py`) handles self-updating the my-unicorn package using uv's tool management capabilities. This document explains the key design decisions and rationale.

## Cache Handling for Version Checks

**Decision:** The upgrade command intentionally disables caching for release fetches (`use_cache=False`, `ignore_cache=True`).

**Rationale:**

- CLI tools must use the latest version for security and reliability
- Users expect fresh results when checking for updates
- Cache TTL (24 hours default) could hide critical updates
- Upgrade checks occur infrequently, so GitHub API rate limits are not a concern

## GitHub API Rate Limiting

Rate limiting is acceptable for upgrade operations:

- **Without token:** 60 requests/hour (sufficient for manual checks)
- **With token** (via keyring): 5000 requests/hour
- Users run upgrades infrequently, minimizing API usage
- Accuracy of version information is more important than caching

## Prerelease vs Stable Release Handling

**Current Implementation:** Fetches latest prerelease using `fetch_latest_prerelease()`

**Future Migration:** When my-unicorn publishes stable releases, update `_fetch_latest_prerelease_version()` to use `fetch_latest_release()` instead. This will prioritize stable versions over prereleases.

**Why Not Now:** YAGNI principle - we'll implement stable release logic when it's actually needed. Currently, my-unicorn only publishes prerelease versions.

## Version Normalization

The module converts semantic versioning (semver) style version strings to PEP 440 format for proper Python version comparison:

**Conversions:**

- `1.0.0-alpha` → `1.0.0a0`
- `2.0.0-beta1` → `2.0.0b1`
- `3.0.0-rc2` → `3.0.0rc2`

**Implementation:** The `normalize_version()` function uses a regex pattern to detect and convert prerelease labels.

## Process Replacement with execvp

**Decision:** Use `os.execvp()` to replace the current process during upgrade

**Rationale:**

- Ensures the upgrade command completes properly
- Prevents the Python process from holding file handles that could interfere with the upgrade
- Standard pattern for self-updating CLI tools

**User Impact:** Users must restart their terminal after a successful upgrade to refresh the command cache and use the updated version.

## Development vs Production Detection

The module detects whether my-unicorn is installed as:

- **Development:** Installed from local file path (`file://`)
- **Production:** Installed from git repository (`git+https://`)

**Behavior:**

- Development installations always trigger an upgrade to production version
- This prevents developers from accidentally running outdated local builds

**Detection Method:** Parses output from `uv tool list --show-version-specifiers` to check for `file://` URI scheme.

## Error Handling Philosophy

**Version Parsing Failures:**

- If current version fails to parse but candidate succeeds → upgrade
- If both fail to parse → fall back to string comparison
- If candidate fails to parse but current succeeds → don't upgrade

**Release Fetch Failures:**

- Log warning and proceed with upgrade (fail-open approach)
- Rationale: Better to attempt upgrade than block users from security updates
- GitHub API issues should not prevent critical updates

## Future Improvements

Potential enhancements to consider:

1. **Stable Release Support:** Migrate from prerelease-only to stable release prioritization when my-unicorn begins publishing stable versions
2. **Rollback Capability:** Consider adding ability to revert to previous version if upgrade fails
3. **Change Log Display:** Show release notes before upgrade to inform users of changes
4. **Selective Version Targeting:** Allow users to upgrade to specific version rather than always latest
5. **Offline Mode:** Support upgrade from locally downloaded packages when internet is unavailable

## Testing Considerations

Key test scenarios:

- Version comparison with various semver and PEP 440 formats
- Prerelease version handling (alpha, beta, rc)
- Development vs production installation detection
- GitHub API failures and rate limiting
- Invalid version string parsing
