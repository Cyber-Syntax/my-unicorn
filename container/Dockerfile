FROM docker.io/library/archlinux:latest

# Update and install development dependencies
RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm \
    # Basic utilities
    git \
    vim \
    wget \
    bash-completion \
    # Required for script
    jq \
    # Sudo for privilege escalation
    sudo \
    # Build dependencies
    python3 \
    && pacman -Scc --noconfirm

ARG USER_UID=1000
ARG USER_GID=1000

# Create user with matching UID/GID
RUN groupadd -g ${USER_GID} devuser && \
    useradd -m -u ${USER_UID} -g ${USER_GID} -G wheel devuser && \
    echo "devuser:test123" | chpasswd && \
    echo "devuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/devuser && \
    chmod 0440 /etc/sudoers.d/devuser

# Keep non-root user and temporary working dir for any user-level steps
USER devuser
WORKDIR /tmp

# Create .config directory with proper permissions
RUN mkdir -p /home/devuser/.config

#TESTING: source code volume mount
# Creating directory for source code volume mount
RUN mkdir -p /home/devuser/my-unicorn
# Make the directory writable by the user
RUN chmod -R 755 /home/devuser/my-unicorn
# run on the host (adjust path & uid/gid if different)
RUN chown -R 1000:1000 /home/devuser/my-unicorn

# Set working directory to the project
WORKDIR /home/devuser/my-unicorn

# Keep container running
CMD ["sleep", "infinity"]
