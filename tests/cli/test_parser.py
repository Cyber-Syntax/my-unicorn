from unittest.mock import patch

import pytest

from my_unicorn.cli.parser import CLIParser  # Replace with actual module name


@pytest.fixture
def cli_parser() -> CLIParser:
    """Fixture providing a CLIParser instance with default config."""
    return CLIParser(global_config={"max_concurrent_downloads": 3})


def test_install_command_basic(cli_parser):
    with patch("sys.argv", ["my-unicorn", "install", "app1", "app2"]):
        args = cli_parser.parse_args()
        assert args.command == "install"
        assert args.targets == ["app1", "app2"]
        assert args.concurrency == 3
        assert not args.no_icon
        assert not args.no_verify
        assert not args.no_desktop


def test_install_command_with_options(cli_parser):
    with patch(
        "sys.argv",
        [
            "my-unicorn",
            "install",
            "app1,app2",
            "app3",
            "--concurrency=5",
            "--no-icon",
            "--no-verify",
            "--no-desktop",
            "--verbose",
        ],
    ):
        args = cli_parser.parse_args()
        assert args.targets == ["app1,app2", "app3"]
        assert args.concurrency == 5
        assert args.no_icon
        assert args.no_verify
        assert args.no_desktop
        assert args.verbose


def test_update_command_all(cli_parser):
    with patch("sys.argv", ["my-unicorn", "update"]):
        args = cli_parser.parse_args()
        assert args.command == "update"
        assert args.apps == []
        assert not args.check_only


def test_update_command_specific_apps(cli_parser):
    with patch("sys.argv", ["my-unicorn", "update", "app1", "app2"]):
        args = cli_parser.parse_args()
        assert args.apps == ["app1", "app2"]


def test_update_command_with_check_only(cli_parser):
    with patch("sys.argv", ["my-unicorn", "update", "--check-only"]):
        args = cli_parser.parse_args()
        assert args.check_only


def test_self_update_command(cli_parser):
    with patch("sys.argv", ["my-unicorn", "upgrade"]):
        args = cli_parser.parse_args()
        assert args.command == "upgrade"


def test_list_installed(cli_parser):
    with patch("sys.argv", ["my-unicorn", "list"]):
        args = cli_parser.parse_args()
        assert args.command == "list"
        assert not args.available


def test_list_available(cli_parser):
    with patch("sys.argv", ["my-unicorn", "list", "--available"]):
        args = cli_parser.parse_args()
        assert args.available


def test_remove_command(cli_parser):
    with patch("sys.argv", ["my-unicorn", "remove", "app1", "app2"]):
        args = cli_parser.parse_args()
        assert args.command == "remove"
        assert args.apps == ["app1", "app2"]
        assert not args.keep_config


def test_remove_with_keep_config(cli_parser):
    with patch("sys.argv", ["my-unicorn", "remove", "app1", "--keep-config"]):
        args = cli_parser.parse_args()
        assert args.keep_config


def test_token_save(cli_parser):
    with patch("sys.argv", ["my-unicorn", "token", "--save"]):
        args = cli_parser.parse_args()
        assert args.command == "token"
        assert args.save


def test_token_remove(cli_parser):
    with patch("sys.argv", ["my-unicorn", "token", "--remove"]):
        args = cli_parser.parse_args()
        assert args.remove


def test_auth_status(cli_parser):
    """Test auth command with --status flag."""
    with patch("sys.argv", ["my-unicorn", "auth", "--status"]):
        args = cli_parser.parse_args()
        assert args.command == "auth"
        assert args.status


def test_auth_default(cli_parser):
    """Test auth command without flag (status is default)."""
    with patch("sys.argv", ["my-unicorn", "auth"]):
        args = cli_parser.parse_args()
        assert args.command == "auth"


def test_config_show(cli_parser):
    with patch("sys.argv", ["my-unicorn", "config", "--show"]):
        args = cli_parser.parse_args()
        assert args.command == "config"
        assert args.show


def test_config_reset(cli_parser):
    with patch("sys.argv", ["my-unicorn", "config", "--reset"]):
        args = cli_parser.parse_args()
        assert args.reset


def test_install_default_concurrency(cli_parser):
    with patch("sys.argv", ["my-unicorn", "install", "app"]):
        args = cli_parser.parse_args()
        assert args.concurrency == 3  # From default config
