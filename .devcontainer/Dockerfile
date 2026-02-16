# Use the latest Ubuntu 24.04 LTS base image (noble)
FROM --platform=linux/amd64 ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

# Core tooling & utilities
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        bash-completion \
        build-essential \
        ca-certificates \
        curl \
        dnsutils \
        git \
        gnupg \
        iputils-ping \
        jq \
        less \
        lsb-release \
        lsof \
        net-tools \
        netcat-openbsd \
        ondir \
        procps \
        ssh \
        sudo \
        tar \
        tree \
        zip \
        unzip \
        vim \
        wget \
        htop \
        python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2 and boto3
RUN pip3 install --break-system-packages boto3 \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS
RUN set -eux; \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 images ship with a default 'ubuntu' user (UID/GID 1000). Reuse it
RUN usermod -aG sudo ubuntu \
    && echo "ubuntu ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu \
    && mkdir -p /home/ubuntu \
    && chown ubuntu:ubuntu /home/ubuntu

# Add aliases and quality-of-life tweaks for the ubuntu user
RUN echo "\
alias c='clear'\n\
alias ll='ls -alF'\n\
alias la='ls -A'\n\
alias l='ls -CF'\n\
alias df='df -h'\n\
alias gs='git status --long'\n\
alias gb='git branch'\n\
alias gp='git pull origin main'\n\
alias count='find . -type f | wc -l'\n\
alias cpv='rsync -ah --info=progress2'\n\
alias whatsup='service --status-all'\n\
alias mkdir='mkdir -pv'\n\
alias grep='grep --color=auto'\n\
" >> /home/ubuntu/.bashrc \
    && chown ubuntu:ubuntu /home/ubuntu/.bashrc

# Install Starship prompt for ubuntu user
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes \
    && echo 'eval "$(starship init bash)"' >> /home/ubuntu/.bashrc \
    && chown ubuntu:ubuntu /home/ubuntu/.bashrc

# Install Terraform & Terragrunt (placed last for better layer caching)
ARG TFVer=1.14.0
ARG TGVer=0.93.11
RUN set -eux; \
    # Terraform
    curl -sSL -o terraform.zip "https://releases.hashicorp.com/terraform/${TFVer}/terraform_${TFVer}_linux_amd64.zip" \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/terraform \
    && rm terraform.zip \
    # Terragrunt
    && curl -sSL -o terragrunt "https://github.com/gruntwork-io/terragrunt/releases/download/v${TGVer}/terragrunt_linux_amd64" \
    && chmod +x terragrunt \
    && mv terragrunt /usr/local/bin/terragrunt

# Default to non-root user
USER ubuntu
WORKDIR /home/ubuntu
ENV DEBIAN_FRONTEND=dialog

# Configure git user
RUN git config --global user.email "ricardo@scoven.co.uk" \
    && git config --global user.name "Ricardo Alvarado"

CMD ["bash"]