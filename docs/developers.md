# Developers wiki for my-unicorn 🦄

> [!NOTE]
> This document provides an overview of the architecture and key components of the My Unicorn project for developers.

## Architecture Overview

Architecture:

- Binary location: `~/.local/bin/my-unicorn`
- Source Code stored in `~/.local/share/my-unicorn/`
- Configuration stored in `~/.config/my-unicorn/`
    - settings.conf - Configuration file for my-unicorn cli
    - cache/ - Cache files, filtered for AppImage/checksums only (Windows, mac removed)
        - `AppFlowy-IO_AppFlowy.json` - AppFlowy cache config
        - `zen-browser_desktop.json` - Zen Browser cache config
    - logs/ - Log files for my-unicorn
    - apps/ - AppImages state data folder (Keeps track of versions, checksum statuses)
        - `appflowy.json` - AppFlowy app config
        - `zen-browser.json` - Zen Browser app config

Project Structure:

- `my_unicorn/` - Main application directory (e.g. src)
    - `catalog/` - AppImage catalog data (owner, repo, verification logic etc.)
        - `appflowy.json` - AppFlowy catalog config
        - `zen-browser.json` - Zen Browser catalog config
    - `cli/` - CLI interface (parser, runner)
    - `commands/` - Command handlers
        - `auth.py` - Auth command handler
        - `backup.py` - Backup command handler
        - `base.py` - Base command handler
        - `cache.py` - Cache command handler
        - `config.py` - Config command handler
        - `install.py` - Install command handler
        - `list.py` - List command handler
        - `remove.py` - Remove command handler
        - `update.py` - Update command handler
        - `upgrade.py` - Upgrade command handler
    - `utils/` - Utility functions
    - `verification/` - Checksum verification logic
    - auth.py: Authentication handler module for github token management
    - backup.py: Backup configuration module
    - cache.py: Cache management module
    - config.py: Configuration management module
    - config_migration.py: Configuration migration module
    - constants.py: Constants module
    - desktop_entry.py: Desktop entry creation module
    - download.py: Download module that downloads AppImage, checksum files
    - exceptions.py: Exception handling module
    - file_ops.py: File operations module
    - github_client.py: GitHub API client module for requests
    - icon.py: Icon management module
    - install.py: Installation module
    - logger.py: Logging module
    - main.py: Main entry point for the application
    - progress.py: Progress bar module using ASCII backend
    - update.py: Update module that updates AppImages
    - upgrade.py: Upgrade module that upgrades my-unicorn
- `scripts/`: Scripts for various tasks
- `tests/`: Test files written in Python using pytest
- setup.sh: Setup script for installation my-unicorn
- run.py: my-unicorn development entry point

## API

> Currently, the app is use only github api but it will be extended to support other platforms in the future.

### Example of the api usage for the latest release api for zen-browser

<https://api.github.com/repos/zen-browser/desktop/releases/latest>

### Example of the beta api usage for FreeTube

<https://api.github.com/repos/FreeTubeApp/FreeTube/releases>

### What we fetch from the API?

#### Information that we use for downloads

> [!NOTE]
> There is also same name, digest, browser_download_url for checksum_files which we use them if the asset does not provide a digest.

##### Example of asset metadata for AppImage

```json
"tag_name": "v0.23.5-beta",
"prerelease": true,
"assets": [
  {
    "name": "freetube-0.23.5-amd64.AppImage",
    "content_type": "application/vnd.appimage",
    "digest": null,
    "size": 99711480,
    "browser_download_url": "https://github.com/FreeTubeApp/FreeTube/releases/download/v0.23.5-beta/freetube-0.23.5-amd64.AppImage"
  }
```

##### Example of aset metadata for Checksumfile

```json
{
      "url": "https://api.github.com/repos/pbek/QOwnNotes/releases/assets/289339017",
      "id": 289339017,
      "node_id": "RA_kwDOAaKly84RPvaJ",
      "name": "QOwnNotes-x86_64-Qt6-experimental.AppImage.sha256sum",
      "label": "",
      "content_type": "text/plain",
      "state": "uploaded",
      "size": 109,
      "digest": "sha256:076c2cb3731dac2d18c561def67423c01ec1843d6ed3dc815bd6b8c55d972694",
      "download_count": 2,
      "created_at": "2025-09-03T20:47:02Z",
      "updated_at": "2025-09-03T20:47:02Z",
      "browser_download_url": "https://github.com/pbek/QOwnNotes/releases/download/v25.9.1/QOwnNotes-x86_64-Qt6-experimental.AppImage.sha256sum"
    },
```

### Example of raw data from github API for zen-browser

> This example also shows app hashes information on the release description.
>
> This example of latest release but beta is similar to this one. Only changes beta provide all the assets and we use the asset 0 for latest version informations, latest release provide directly to that asset 0.

```json
{
    "url": "https://api.github.com/repos/zen-browser/desktop/releases/245148673",
    "assets_url": "https://api.github.com/repos/zen-browser/desktop/releases/245148673/assets",
    "upload_url": "https://uploads.github.com/repos/zen-browser/desktop/releases/245148673/assets{?name,label}",
    "html_url": "https://github.com/zen-browser/desktop/releases/tag/1.15.4b",
    "id": 245148673,
    "author": {
        "login": "mr-cheffy",
        "id": 91018726,
        "node_id": "U_kgDOBWzV5g",
        "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/mr-cheffy",
        "html_url": "https://github.com/mr-cheffy",
        "followers_url": "https://api.github.com/users/mr-cheffy/followers",
        "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
        "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
        "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
        "repos_url": "https://api.github.com/users/mr-cheffy/repos",
        "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
        "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
        "type": "User",
        "user_view_type": "public",
        "site_admin": false
    },
    "node_id": "RE_kwDOLmfWBM4OnKwB",
    "tag_name": "1.15.4b",
    "target_commitish": "dev",
    "name": "Release build - 1.15.4b (2025-09-05)",
    "draft": false,
    "immutable": false,
    "prerelease": false,
    "created_at": "2025-09-05T10:20:22Z",
    "updated_at": "2025-09-06T15:56:44Z",
    "published_at": "2025-09-05T18:18:39Z",
    "assets": [
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361069",
            "id": 290361069,
            "node_id": "RA_kwDOLmfWBM4RTo7t",
            "name": "linux-aarch64.mar",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 70578930,
            "digest": "sha256:a3d0dc8f1e5352e4ae41f315737cebf96c3f5071ffec76d0ed137ba8cb36a4f0",
            "download_count": 14,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:17Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/linux-aarch64.mar"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361071",
            "id": 290361071,
            "node_id": "RA_kwDOLmfWBM4RTo7v",
            "name": "linux.mar",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 84368327,
            "digest": "sha256:c356d12623fc19e0fe4a6ee08e2bc7a431300fa33cedb786396b6ec532cf52b7",
            "download_count": 1228,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:18Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/linux.mar"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361077",
            "id": 290361077,
            "node_id": "RA_kwDOLmfWBM4RTo71",
            "name": "macos.mar",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 129689434,
            "digest": "sha256:b2d5af628659981d5651769121d9d5da72dfd0b4206e69e086383a76739d6fdf",
            "download_count": 8138,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:20Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/macos.mar"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361075",
            "id": 290361075,
            "node_id": "RA_kwDOLmfWBM4RTo7z",
            "name": "windows-arm64.mar",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 81330256,
            "digest": "sha256:ac38945fb1f62e397766372d5ece9e5633760420fe8962b38ddf6cca0f7bc150",
            "download_count": 117,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:18Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/windows-arm64.mar"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361068",
            "id": 290361068,
            "node_id": "RA_kwDOLmfWBM4RTo7s",
            "name": "windows.mar",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 95159564,
            "digest": "sha256:2806341e0bd1a75f77c4f524d3b95351410f8f23c76d2a893bfcfc10a166af94",
            "download_count": 19230,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:19Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/windows.mar"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361079",
            "id": 290361079,
            "node_id": "RA_kwDOLmfWBM4RTo73",
            "name": "zen-aarch64.AppImage",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 96790928,
            "digest": "sha256:55d38dc92100a4d3a43d0e1f73be9f670027972fec454361f911e68d27cf4f50",
            "download_count": 14,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:19Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen-aarch64.AppImage"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361073",
            "id": 290361073,
            "node_id": "RA_kwDOLmfWBM4RTo7x",
            "name": "zen-aarch64.AppImage.zsync",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 331045,
            "digest": "sha256:cffeb93a0ec0801c0cd4e2bf3b898fa99d50f5adf904707fe7f5a4faca0bb712",
            "download_count": 1,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:14Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen-aarch64.AppImage.zsync"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361078",
            "id": 290361078,
            "node_id": "RA_kwDOLmfWBM4RTo72",
            "name": "zen-x86_64.AppImage",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 109834640,
            "digest": "sha256:d6aeb9479b741ef5eb26ec46f0dd01a13d03f0cdf3c05045f7e2b243af84bd99",
            "download_count": 118,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:19Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen-x86_64.AppImage"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361081",
            "id": 290361081,
            "node_id": "RA_kwDOLmfWBM4RTo75",
            "name": "zen-x86_64.AppImage.zsync",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 187922,
            "digest": "sha256:c7dc981d689e4f46e726a065991614416e0cf67fe29fa26809f2c533bfcee2ba",
            "download_count": 78,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:14Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen-x86_64.AppImage.zsync"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361072",
            "id": 290361072,
            "node_id": "RA_kwDOLmfWBM4RTo7w",
            "name": "zen.installer-arm64.exe",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 80973016,
            "digest": "sha256:697d86cfc720a6455272e1656e05b83fbbaaad90459388b55465cea32c6b13ad",
            "download_count": 28,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:18Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.installer-arm64.exe"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361074",
            "id": 290361074,
            "node_id": "RA_kwDOLmfWBM4RTo7y",
            "name": "zen.installer.exe",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 86836576,
            "digest": "sha256:f64d4be2e590c1baabd610fc8c7ac4a8c9a8f92f67ca9050fef8400091e4a35b",
            "download_count": 3413,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:18Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.installer.exe"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361070",
            "id": 290361070,
            "node_id": "RA_kwDOLmfWBM4RTo7u",
            "name": "zen.linux-aarch64.tar.xz",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/x-xz",
            "state": "uploaded",
            "size": 68624672,
            "digest": "sha256:0e1308ac713c44d3eca34b13d68f9d34d8d541a4b5b62496cc6c09e1646cdc56",
            "download_count": 30,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:17Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.linux-aarch64.tar.xz"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361080",
            "id": 290361080,
            "node_id": "RA_kwDOLmfWBM4RTo74",
            "name": "zen.linux-x86_64.tar.xz",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/x-xz",
            "state": "uploaded",
            "size": 82016760,
            "digest": "sha256:8d8f5e4bf9df9ce10e5c3f57369c54c9fe8ea070017139d8edec0334699a081e",
            "download_count": 2517,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:18Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.linux-x86_64.tar.xz"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361076",
            "id": 290361076,
            "node_id": "RA_kwDOLmfWBM4RTo70",
            "name": "zen.macos-universal.dmg",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 187145526,
            "digest": "sha256:8161155cbddbfecd23f51d302ea31612decada5170ee580134894898765ec00b",
            "download_count": 2831,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:22Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.macos-universal.dmg"
        },
        {
            "url": "https://api.github.com/repos/zen-browser/desktop/releases/assets/290361067",
            "id": 290361067,
            "node_id": "RA_kwDOLmfWBM4RTo7r",
            "name": "zen.source.tar.zst",
            "label": "",
            "uploader": {
                "login": "mr-cheffy",
                "id": 91018726,
                "node_id": "U_kgDOBWzV5g",
                "avatar_url": "https://avatars.githubusercontent.com/u/91018726?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/mr-cheffy",
                "html_url": "https://github.com/mr-cheffy",
                "followers_url": "https://api.github.com/users/mr-cheffy/followers",
                "following_url": "https://api.github.com/users/mr-cheffy/following{/other_user}",
                "gists_url": "https://api.github.com/users/mr-cheffy/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/mr-cheffy/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/mr-cheffy/subscriptions",
                "organizations_url": "https://api.github.com/users/mr-cheffy/orgs",
                "repos_url": "https://api.github.com/users/mr-cheffy/repos",
                "events_url": "https://api.github.com/users/mr-cheffy/events{/privacy}",
                "received_events_url": "https://api.github.com/users/mr-cheffy/received_events",
                "type": "User",
                "user_view_type": "public",
                "site_admin": false
            },
            "content_type": "application/octet-stream",
            "state": "uploaded",
            "size": 867547565,
            "digest": "sha256:1263ff33ad73896cb1ee8bbe36bf340ab7fe1667331da6ae107be33960d6ab57",
            "download_count": 3,
            "created_at": "2025-09-06T15:56:14Z",
            "updated_at": "2025-09-06T15:56:44Z",
            "browser_download_url": "https://github.com/zen-browser/desktop/releases/download/1.15.4b/zen.source.tar.zst"
        }
    ],
    "tarball_url": "https://api.github.com/repos/zen-browser/desktop/tarball/1.15.4b",
    "zipball_url": "https://api.github.com/repos/zen-browser/desktop/zipball/1.15.4b",
    "body": "# Zen Stable Release\n\n\n## Fixes\n- Fixed potential crashes on flatpak and updated flatpak dependencies.\n- Fixed double clicking on the empty space of the sidebar not making a new tab.\n",
    "reactions": {
        "url": "https://api.github.com/repos/zen-browser/desktop/releases/245148673/reactions",
        "total_count": 49,
        "+1": 15,
        "-1": 0,
        "laugh": 0,
        "hooray": 3,
        "confused": 0,
        "heart": 31,
        "rocket": 0,
        "eyes": 0
    }
}
```
