# Security Best Practices — Dependency Management (uv + Python)

## Current dependencies

We use a controlled set of dependencies managed via `pyproject.toml` and locked with `uv.lock`.

### Runtime dependencies

```toml
requires-python = ">= 3.12,<3.14"
dependencies = [
  "aiohttp>=3.12",
  "aiofiles>=25",
  "uvloop>=0.21; platform_system != 'Windows'",
  "keyring>=25",
  "packaging>=25",
  "jsonschema>=4.23",
  "pyyaml>=5",
  "orjson>=3.10",
]
```

### Development dependencies

```toml
[dependency-groups]
dev = [
  "pytest>=9",
  "pytest-cov>=6",
  "pytest-mock>=3",
  "pytest-asyncio>=1",
  "mypy>=1",
  "pip-audit>=2",
  "aioresponses>=0.6.4",
  "requests>=2",
]
lint = ["ruff>=0.15"]
```

### Tooling configuration

```toml
[tool.uv]
exclude-newer = "7 days"
```

## What covers?

1. Excluding 7 days of newer versions to avoid supply chain attacks.
2. Excluding python 3.14 to avoid compatibility issues.

## Limitations

- Malicious dependencies may still exist even after 7 days if community/developers don't detect it.
- CVE vulnerabilities not covered by this, we still need to use `pip-audit` to scan for them.
    - Even pip-audit might not catch all vulnerabilities which every new feature can introduce new ones.
