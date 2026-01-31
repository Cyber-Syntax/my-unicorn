"""Test framework utilities package.

This package provides pure, reusable utility functions to eliminate
code duplication across the test framework.

Modules:
    file_ops: File system operations
    hash_ops: SHA hash calculation
    json_ops: JSON read/write operations
    path_ops: Path manipulation
    cli_utils: CLI execution utilities

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from .cli_utils import (
    get_my_unicorn_version,
    is_command_available,
    kill_my_unicorn_processes,
    run_my_unicorn,
)
from .file_ops import (
    ensure_directory,
    file_exists,
    get_file_mtime,
    get_file_size,
    is_executable,
    read_file_bytes,
    read_file_text,
    remove_file,
    write_file_bytes,
    write_file_text,
)
from .hash_ops import (
    calculate_sha256,
    calculate_sha512,
    hash_string,
    verify_hash,
)
from .json_ops import (
    get_json_value,
    is_valid_json,
    load_json,
    merge_json,
    save_json,
)
from .path_ops import (
    get_app_config_path,
    get_apps_dir,
    get_backup_dir,
    get_benchmark_dir,
    get_cache_dir,
    get_cache_file_path,
    get_catalog_dir,
    get_config_dir,
    get_desktop_entry_path,
    get_global_config_path,
    get_log_dir,
)

__all__ = [
    # hash_ops
    "calculate_sha256",
    "calculate_sha512",
    "ensure_directory",
    # file_ops
    "file_exists",
    "get_app_config_path",
    "get_apps_dir",
    "get_backup_dir",
    "get_benchmark_dir",
    "get_cache_dir",
    "get_cache_file_path",
    "get_catalog_dir",
    # path_ops
    "get_config_dir",
    "get_desktop_entry_path",
    "get_file_mtime",
    "get_file_size",
    "get_global_config_path",
    "get_json_value",
    "get_log_dir",
    "get_my_unicorn_version",
    "hash_string",
    "is_command_available",
    "is_executable",
    "is_valid_json",
    "kill_my_unicorn_processes",
    # json_ops
    "load_json",
    "merge_json",
    "read_file_bytes",
    "read_file_text",
    "remove_file",
    # cli_utils
    "run_my_unicorn",
    "save_json",
    "verify_hash",
    "write_file_bytes",
    "write_file_text",
]
