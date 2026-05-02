## Problem

<!-- Describe the problem that these changes solve (links to issues are welcome). -->

## Solution

<!-- Describe your changes in detail. -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Refactoring
- [ ] Documentation
- [ ] Other (please describe)

## Checklist

- If you changed python module:
    - [ ] Run all fast tests: `uv run pytest -m 'not slow'`
    - [ ] Run e2e tests: `uv run pytest tests/e2e/` (WARNING: This tests would use real api connection, make sure you setup your token. Also, this would take time according to your internet speed.)
- [ ] Add your test (if you can)
- [ ] Add/update docs
