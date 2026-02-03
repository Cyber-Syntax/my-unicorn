"""Integration tests for my-unicorn cross-component functionality.

This package contains integration tests that verify end-to-end workflows,
cross-component communication, and real-world usage scenarios. Tests in
this package use the @pytest.mark.integration marker and may require more
setup time than unit tests.

Tests verify:
- Protocol integration across module boundaries
- Exception propagation through workflow layers
- Async file I/O functionality
- Logger rotation with large files
- Self-upgrade functionality
"""
