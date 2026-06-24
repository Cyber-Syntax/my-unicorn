# my-unicorn fish completion script
# ------------------------------------------------
# Install: cp completions/my-unicorn.fish ~/.config/fish/completions/
# ------------------------------------------------

complete -c my-unicorn -f

# -- Global options -----------------------------------------------------------

complete -c my-unicorn -l version -d 'Show my-unicorn version and exit'
complete -c my-unicorn -s h -l help -d 'Show help message and exit'

# -- Subcommands --------------------------------------------------------------

complete -c my-unicorn -n __fish_use_subcommand -a install -d 'Install AppImages from catalog or URLs'
complete -c my-unicorn -n __fish_use_subcommand -a update -d 'Update installed AppImages'
complete -c my-unicorn -n __fish_use_subcommand -a upgrade -d 'Upgrade my-unicorn CLI'
complete -c my-unicorn -n __fish_use_subcommand -a catalog -d 'Browse AppImage catalog'
complete -c my-unicorn -n __fish_use_subcommand -a migrate -d 'Migrate configs to latest version'
complete -c my-unicorn -n __fish_use_subcommand -a remove -d 'Remove installed AppImages'
complete -c my-unicorn -n __fish_use_subcommand -a backup -d 'Manage AppImage backups and restore'
complete -c my-unicorn -n __fish_use_subcommand -a cache -d 'Manage release data cache'
complete -c my-unicorn -n __fish_use_subcommand -a token -d 'Manage GitHub authentication token'
complete -c my-unicorn -n __fish_use_subcommand -a auth -d 'Show GitHub authentication status'
complete -c my-unicorn -n __fish_use_subcommand -a config -d 'Manage configuration'

# -- install ------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from install' -l concurrency -d 'Maximum number of parallel installs' -r
complete -c my-unicorn -n '__fish_seen_subcommand_from install' -l no-icon -d 'Skip downloading application icons'
complete -c my-unicorn -n '__fish_seen_subcommand_from install' -l no-verify -d 'Skip AppImage verification'
complete -c my-unicorn -n '__fish_seen_subcommand_from install' -l no-desktop -d 'Skip desktop entry creation'
complete -c my-unicorn -n '__fish_seen_subcommand_from install' -l verbose -d 'Show detailed logging during installation'
complete -c my-unicorn -n '__fish_seen_subcommand_from install' -s h -l help -d 'Show help message and exit'

# -- update -------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from update' -l check-only -d 'Only check for updates without installing'
complete -c my-unicorn -n '__fish_seen_subcommand_from update' -l refresh-cache -d 'Bypass cache and fetch fresh data from GitHub API'
complete -c my-unicorn -n '__fish_seen_subcommand_from update' -l verbose -d 'Show detailed logging during update'
complete -c my-unicorn -n '__fish_seen_subcommand_from update' -s h -l help -d 'Show help message and exit'

# -- upgrade ------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from upgrade' -l check -d 'Check for available updates without performing the upgrade'
complete -c my-unicorn -n '__fish_seen_subcommand_from upgrade' -s h -l help -d 'Show help message and exit'

# -- catalog ------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from catalog' -l installed -d 'Show installed AppImages (default)'
complete -c my-unicorn -n '__fish_seen_subcommand_from catalog' -l available -d 'Show available applications from catalog with descriptions'
complete -c my-unicorn -n '__fish_seen_subcommand_from catalog' -l info -d 'Show detailed information about a specific app' -r
complete -c my-unicorn -n '__fish_seen_subcommand_from catalog' -s h -l help -d 'Show help message and exit'

# -- migrate ------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from migrate' -l dry-run -d 'Show what would be migrated without making changes'
complete -c my-unicorn -n '__fish_seen_subcommand_from migrate' -l force -d 'Force migration even if versions match'
complete -c my-unicorn -n '__fish_seen_subcommand_from migrate' -s h -l help -d 'Show help message and exit'

# -- remove -------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from remove' -l keep-config -d 'Keep configuration files'
complete -c my-unicorn -n '__fish_seen_subcommand_from remove' -s h -l help -d 'Show help message and exit'

# -- backup -------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -l restore-last -d 'Restore the latest backup version'
complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -l restore-version -d 'Restore a specific version' -r
complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -l list-backups -d 'List available backups for the specified app'
complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -l cleanup -d 'Clean up old backups according to max_backup setting'
complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -l info -d 'Show detailed backup information'
complete -c my-unicorn -n '__fish_seen_subcommand_from backup' -s h -l help -d 'Show help message and exit'

# -- cache --------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from cache' -a clear -d 'Clear cache entries'
complete -c my-unicorn -n '__fish_seen_subcommand_from cache' -a stats -d 'Show cache statistics and storage info'
complete -c my-unicorn -n '__fish_seen_subcommand_from cache' -s h -l help -d 'Show help message and exit'

# -- cache clear subcommand ---------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from cache; and contains -- (commandline -opc); and not contains clear -- (commandline -opc); and not contains stats -- (commandline -opc)' -a clear -d 'Clear cache entries'
complete -c my-unicorn -n '__fish_seen_subcommand_from cache; and string match -q clear -- (commandline -opc)[2]' -l all -d 'Clear all cache entries'
complete -c my-unicorn -n '__fish_seen_subcommand_from cache; and string match -q clear -- (commandline -opc)[2]' -s h -l help -d 'Show help message and exit'

# -- token --------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from token' -l save -d 'Save GitHub authentication token'
complete -c my-unicorn -n '__fish_seen_subcommand_from token' -l remove -d 'Remove GitHub authentication token'
complete -c my-unicorn -n '__fish_seen_subcommand_from token' -s h -l help -d 'Show help message and exit'

# -- auth ---------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from auth' -l status -d 'Show authentication status (default action)'
complete -c my-unicorn -n '__fish_seen_subcommand_from auth' -s h -l help -d 'Show help message and exit'

# -- config -------------------------------------------------------------------

complete -c my-unicorn -n '__fish_seen_subcommand_from config' -l show -d 'Show current configuration'
complete -c my-unicorn -n '__fish_seen_subcommand_from config' -l reset -d 'Reset configuration to defaults'
complete -c my-unicorn -n '__fish_seen_subcommand_from config' -s h -l help -d 'Show help message and exit'
