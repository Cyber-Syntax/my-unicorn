# My Unicorn — Development Container (Arch only)

This directory provides a small, single-distro development container for testing the `my-unicorn` CLI.
The environment is intentionally simplified to a single Arch Linux container for fast iteration and predictable behavior.

## Core files

- `Dockerfile` — image build definition for the Arch container
- `podman-compose.yml` — compose file to run the container and define the config volume
- `manage.sh` — convenience wrapper to build, start, stop, open a shell, view logs, and clean the container
- `.dockerignore` — files excluded from image context

## Quick requirements

- `podman` (or a compatible container runtime) available on the host
- `podman-compose` installed and on PATH
- A POSIX shell to run `manage.sh` from the `container/` directory

## Quick start

Make the helper executable (one-time):

```my-unicorn/container/README.md#L1-6
chmod +x manage.sh
```

Build and start the container (the script injects your host UID/GID into the build so `devuser` matches your host):

```my-unicorn/container/README.md#L7-12
./manage.sh build
./manage.sh start
```

Open an interactive shell inside the running container:

```my-unicorn/container/README.md#L13-18
./manage.sh shell
# or, explicitly:
./manage.sh shell arch
```

If you prefer `podman-compose` directly:

```my-unicorn/container/README.md#L19-24
cd container
USER_UID=$(id -u) USER_GID=$(id -g) podman-compose up -d --build arch
podman exec -it my-unicorn-arch bash
```

## About `manage.sh`

`manage.sh` is a small wrapper around `podman-compose` that provides common workflows and convenience features:

- Detects presence of `podman-compose` and warns if missing
- Injects `USER_UID` and `USER_GID` into builds (reduces permission friction for created config files)
- Provides the following commands:

```my-unicorn/container/README.md#L25-40
./manage.sh build [arch|all]    # Build image(s) (default: arch)
./manage.sh start [arch|all]    # Start container(s)
./manage.sh stop [arch|all]     # Stop container(s)
./manage.sh restart [arch|all]  # Restart container(s)
./manage.sh shell [arch]        # Open an interactive shell
./manage.sh logs [arch|all]     # Follow container logs
./manage.sh status              # Show containers and volumes
./manage.sh clean [arch|all]    # Remove container(s) and config volume(s) (prompts)
```

### Examples

Build, start and open shell:

```my-unicorn/container/README.md#L41-50
cd container
./manage.sh build
./manage.sh start
./manage.sh shell
# Inside the container:
# cp -r /workspace ~/my-unicorn && cd ~/my-unicorn
# sudo ./setup.sh -a
```

Stop and remove the container and its config volume:

```my-unicorn/container/README.md#L51-58
cd container
./manage.sh stop
./manage.sh clean
# Answer 'y' when prompted to delete containers/volumes.
```

## Filesystem layout (inside container)

- `/workspace` — the repository mounted read-only from the host (do not expect write access)
- `/home/devuser` — home directory for the non-root `devuser` inside the container
- `~/.config/my-unicorn` — persistent application configuration (backed by a podman volume defined in the compose file)

If you need to run scripts that write files under the repo, copy the workspace into the container user's home first:

```my-unicorn/container/README.md#L59-66
# inside the container
cp -r /workspace ~/my-unicorn
cd ~/my-unicorn
sudo ./setup.sh -h
```

## Notes and tips

- The script maps your host `UID`/`GID` into the build to reduce file-permission issues for files created by the container.
- `devuser` is configured with passwordless `sudo` for convenience in ephemeral development.
- Keep edits on the host — the `/workspace` mount ensures you can edit locally while testing in the container.
- If you prefer working without copying, you can symlink `/workspace` into the home (note: symlink does not change write permissions on the underlying mount).

## Volumes

The compose file creates a named podman volume (for example: `my-unicorn-arch-config`) to persist `~/.config/my-unicorn` between runs.
Podman stores volumes under:

```
~/.local/share/containers/storage/volumes/
```

To inspect or back up the config from the host, either use `podman volume inspect` or tar the files from inside the container and `podman cp` them out.

## Troubleshooting

- Permission denied when running `setup.sh`: remember `/workspace` is read-only — copy the workspace to your home before running scripts that write.
- `sudo` prompts for a password: check `/etc/sudoers.d/devuser` inside the container. The image is intended to include NOPASSWD for `devuser`.
- Missing `podman-compose`: install it on the host and re-run `manage.sh`. The script will detect and inform you if it cannot find it.

To fully reset (stop and remove container and volume):

```my-unicorn/container/README.md#L67-74
./manage.sh clean
# or
podman-compose down -v
podman volume rm container_my-unicorn-arch-config || true
```

## Security

- The container runs as non-root `devuser` by default.
- The repository is mounted read-only to help prevent accidental host modifications.
- Config volumes are isolated — avoid mounting your real host `~/.config` into the container.
