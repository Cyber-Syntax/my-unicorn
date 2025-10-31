#!/usr/bin/env bash
# Helper script for managing my-unicorn development containers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
  cat <<EOF
My Unicorn Container Manager

Usage: $0 <command> [distro]

Commands:
  build [distro]    Build container(s) - distro: fedora|arch|debian|all
  start [distro]    Start container(s)
  stop [distro]     Stop container(s)
  restart [distro]  Restart container(s)
  shell [distro]    Open shell in container - distro: fedora|arch|debian
  clean [distro]    Stop and remove container(s) and volumes
  status            Show status of all containers
  logs [distro]     Show logs for container(s)

Examples:
  $0 build all      # Build all containers
  $0 build fedora   # Build only Fedora container
  $0 start arch     # Start Arch container
  $0 shell debian   # Open shell in Debian container
  $0 clean fedora   # Remove Fedora container and its config volume
  $0 status         # Show status of all containers

EOF
}

check_podman() {
  if ! command -v podman-compose &>/dev/null; then
    echo -e "${RED}Error: podman-compose is not installed${NC}"
    echo "Install it with: pip install podman-compose"
    exit 1
  fi
}

get_distros() {
  local distro="${1:-all}"
  case "$distro" in
  fedora | arch | debian)
    echo "$distro"
    ;;
  all)
    echo "fedora arch debian"
    ;;
  *)
    echo -e "${RED}Error: Invalid distro '$distro'${NC}"
    echo "Valid options: fedora, arch, debian, all"
    exit 1
    ;;
  esac
}

cmd_build() {
  local distro="${1:-all}"
  check_podman

  # Get host UID/GID to match container user permissions
  local host_uid=$(id -u)
  local host_gid=$(id -g)

  echo -e "${BLUE}Building container(s): $distro${NC}"
  echo -e "${YELLOW}Using UID=${host_uid} GID=${host_gid} (matching host user)${NC}"

  if [[ "$distro" == "all" ]]; then
    USER_UID=${host_uid} USER_GID=${host_gid} podman-compose up -d --build
  else
    USER_UID=${host_uid} USER_GID=${host_gid} podman-compose up -d --build "$distro"
  fi

  echo -e "${GREEN}✓ Build complete${NC}"
}

cmd_start() {
  local distro="${1:-all}"
  check_podman

  echo -e "${BLUE}Starting container(s): $distro${NC}"

  if [[ "$distro" == "all" ]]; then
    podman-compose start
  else
    podman-compose start "$distro"
  fi

  echo -e "${GREEN}✓ Started${NC}"
}

cmd_stop() {
  local distro="${1:-all}"
  check_podman

  echo -e "${BLUE}Stopping container(s): $distro${NC}"

  if [[ "$distro" == "all" ]]; then
    podman-compose stop
  else
    podman-compose stop "$distro"
  fi

  echo -e "${GREEN}✓ Stopped${NC}"
}

cmd_restart() {
  local distro="${1:-all}"
  cmd_stop "$distro"
  cmd_start "$distro"
}

cmd_shell() {
  local distro="${1:-}"

  if [[ -z "$distro" ]] || [[ "$distro" == "all" ]]; then
    echo -e "${RED}Error: Must specify a distro for shell command${NC}"
    echo "Usage: $0 shell <fedora|arch|debian>"
    exit 1
  fi

  local container_name="my-unicorn-${distro}"

  echo -e "${BLUE}Opening shell in ${distro} container...${NC}"
  echo -e "${YELLOW}Tip: Run 'cp -r /workspace ~/my-unicorn && cd ~/my-unicorn' to get started${NC}"
  echo ""

  podman exec -it "$container_name" bash
}

cmd_clean() {
  local distro="${1:-all}"
  check_podman

  echo -e "${YELLOW}Warning: This will remove container(s) and config volumes${NC}"
  read -p "Are you sure? [y/N] " -n 1 -r
  echo

  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Cancelled${NC}"
    exit 0
  fi

  echo -e "${BLUE}Cleaning container(s): $distro${NC}"

  if [[ "$distro" == "all" ]]; then
    podman-compose down -v
    echo -e "${GREEN}✓ All containers and volumes removed${NC}"
  else
    podman-compose stop "$distro"
    podman-compose rm -f "$distro"
    # Volume names are created/managed by the compose file and use the
    # my-unicorn-<distro>-config naming defined in the compose.
    podman volume rm "my-unicorn-${distro}-config" 2>/dev/null || true
    echo -e "${GREEN}✓ ${distro} container and volume removed${NC}"
  fi
}

cmd_status() {
  check_podman

  echo -e "${BLUE}Container Status:${NC}"
  echo ""

  # Filter containers by the my-unicorn name prefix
  podman ps -a --filter "name=my-unicorn" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

  echo ""
  echo -e "${BLUE}Volumes:${NC}"
  # Filter volumes created for my-unicorn
  podman volume ls --filter "name=my-unicorn" --format "table {{.Name}}\t{{.Driver}}\t{{.Mountpoint}}"
}

cmd_logs() {
  local distro="${1:-all}"
  check_podman

  if [[ "$distro" == "all" ]]; then
    podman-compose logs -f
  else
    podman-compose logs -f "$distro"
  fi
}

# Main command dispatcher
main() {
  if [[ $# -eq 0 ]]; then
    print_usage
    exit 0
  fi

  local command="$1"
  shift

  case "$command" in
  build)
    cmd_build "$@"
    ;;
  start)
    cmd_start "$@"
    ;;
  stop)
    cmd_stop "$@"
    ;;
  restart)
    cmd_restart "$@"
    ;;
  shell)
    cmd_shell "$@"
    ;;
  clean)
    cmd_clean "$@"
    ;;
  status)
    cmd_status
    ;;
  logs)
    cmd_logs "$@"
    ;;
  -h | --help | help)
    print_usage
    ;;
  *)
    echo -e "${RED}Error: Unknown command '$command'${NC}"
    echo ""
    print_usage
    exit 1
    ;;
  esac
}

main "$@"
