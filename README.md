<div align="center">
  <img src="https://raw.githubusercontent.com/sl4x0/ghmon/main/static/banner.png" alt="ghmon Banner" style="max-width: 100%; height: auto;"/>
</div>

# ghmon: Repository Security Scanner

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> A powerful command-line tool for scanning GitHub and GitLab repositories for leaked secrets using TruffleHog, with intelligent notifications and continuous monitoring capabilities.

ghmon streamlines secret detection for DevOps and security teams. It automatically discovers repositories, runs TruffleHog scans, and sends alerts through Discord or Telegram. Use it for one-off scans or continuous monitoring to keep your code free of leaked credentials.

---

## 🚀 What is ghmon?

**ghmon** is a comprehensive security scanning tool that helps you:

- **🔍 Discover** repositories from organizations on GitHub and GitLab
- **🔐 Scan** repository history for leaked secrets using TruffleHog
- **🎯 Filter** findings to focus on verified, high-confidence results
- **📢 Notify** about new discoveries via Discord and Telegram
- **⏰ Monitor** continuously with automated background scanning
- **🔄 Manage** API tokens with smart rotation and rate limiting

**Key Features:**

- Zero-configuration secret detection with TruffleHog integration
- Multi-platform notifications (Discord, Telegram)
- Intelligent token rotation and rate limit handling
- Continuous monitoring with configurable intervals
- Comprehensive logging and result tracking
- Support for both GitHub and GitLab platforms

---

## 📦 Prerequisites

Ensure your system has the following requirements:

### Required Dependencies

- **Python 3.8+** - Check with `python3 --version`
- **Git** - Check with `git --version`
- **TruffleHog** - Install from [GitHub releases](https://github.com/trufflesecurity/trufflehog/releases)

### System Requirements

- **Linux/macOS/Windows** (WSL recommended for Windows)
- **Bash shell** for installation scripts
- **Internet connection** for API access and notifications

### Optional Tools

- **screen** - For background monitoring (auto-installed by setup script)
  ```bash
  # Manual installation if needed:
  # Ubuntu/Debian: sudo apt-get install screen
  # Fedora: sudo dnf install screen
  # macOS: brew install screen
  ```

---

## ⚙️ Installation

Choose your preferred installation method:

### Option A: Clone from Repository (Recommended)

```bash
# Clone the repository
git clone https://github.com/sl4x0/ghmon.git
cd ghmon

# Make scripts executable
chmod +x install.sh

# Run installation
./install.sh
```

### Option B: Install from Archive

```bash
# Upload archive to your server
scp ghmon-*.tar.gz user@server:~/

# Extract and install
ssh user@server
tar -xzf ghmon-*.tar.gz
cd ghmon
chmod +x install.sh
./install.sh
```

### Option C: Python Package Installation

```bash
# Install from GitHub Releases (Recommended)
wget https://github.com/sl4x0/ghmon/releases/download/v1.0.0/ghmon_cli-1.0.0-py3-none-any.whl
pip install ghmon_cli-1.0.0-py3-none-any.whl

# Or install from source distribution
wget https://github.com/sl4x0/ghmon/releases/download/v1.0.0/ghmon_cli-1.0.0.tar.gz
pip install ghmon_cli-1.0.0.tar.gz

# Or install in development mode
pip install -e .
```

### Option D: Docker Deployment

For containerized environments and CI/CD pipelines:

```bash
# Clone the repository
git clone https://github.com/sl4x0/ghmon.git
cd ghmon

# Copy and configure your settings
cp ghmon_config.yaml.example ghmon_config.yaml
# Edit ghmon_config.yaml with your API tokens and settings

# Build the Docker image
docker build -t ghmon:latest .

# Run one-time scan
docker run --rm \
  -v $(pwd)/ghmon_config.yaml:/app/ghmon_config.yaml:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ghmon:latest \
  python -m ghmon_cli scan -o YOUR_ORG_NAME --config /app/ghmon_config.yaml

# Run continuous monitoring
docker run -d \
  --name ghmon-monitor \
  --restart unless-stopped \
  -v $(pwd)/ghmon_config.yaml:/app/ghmon_config.yaml:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ghmon:latest \
  python -m ghmon_cli monitor --config /app/ghmon_config.yaml
```

#### Docker Compose (Recommended)

For easier management, use the provided `docker-compose.yml`:

```bash
# Start continuous monitoring
docker-compose up -d

# Run one-time scan
ORG_NAME=your-org-name docker-compose --profile scan up ghmon-scan

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Docker Features

- **🔒 Security**: Runs as non-root user
- **📁 Persistent Data**: Volumes for configuration, data, and logs
- **🔄 Auto-restart**: Automatic container restart on failure
- **📊 Health Checks**: Built-in container health monitoring
- **⚡ Resource Limits**: Configurable CPU and memory limits
- **🐳 Multi-stage Build**: Optimized image size

---

## 🛠️ Configuration

ghmon uses a YAML configuration file (`ghmon_config.yaml`) for all settings. Create this file in your project root directory.

### Configuration Template

Start with the example template and update it with real tokens:

```bash
cp ghmon_config.yaml.example ghmon_config.yaml
```

### Quick Start Configuration

```yaml
# Basic configuration template
general:
  log_level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
  output_dir: ./scan_results # Results directory
  api_concurrency: 3 # Parallel API requests (1-20)

# GitHub configuration
github:
  enabled: true
  api_url: https://api.github.com
  tokens:
    - ghp_your_github_token_1 # Replace with your tokens
    - ghp_your_github_token_2 # Multiple tokens for rate limiting

# GitLab configuration (optional)
gitlab:
  enabled: false
  api_url: https://gitlab.com/api/v4
  tokens:
    - glpat_your_gitlab_token # Replace with your token

# Notification settings (optional)
notifications:
  discord:
    enabled: false # Set to true to enable
    webhook_url: "" # Your Discord webhook URL
  telegram:
    enabled: false # Set to true to enable
    bot_token: "" # Your Telegram bot token
    chat_id: "" # Your Telegram chat ID

# Operational settings
operation:
  scan_interval: 21600 # 6 hours between monitor cycles
  max_commits_for_full_extraction: 30000 # Skip deep scan for large repos
  scan_only_on_change: true # Only scan repos with new commits

# TruffleHog scanner settings
trufflehog:
  concurrency: 5 # Parallel scans (1-16)
  shallow_clone_timeout: 300 # Timeout for shallow clones (seconds)
  full_clone_timeout: 1200 # Timeout for full clones (seconds)
  shallow_scan_timeout: 600 # Timeout for shallow scans (seconds)
  full_scan_timeout: 1800 # Timeout for full scans (seconds)
  git_rev_list_timeout: 900 # Git operations timeout (seconds)
  git_show_timeout: 180 # Git show timeout (seconds)
  git_unpack_timeout: 900 # Git unpack timeout (seconds)

# Organizations to scan
organizations:
  - your-organization-1 # Replace with actual organization names
  - your-organization-2
  # Add more organizations as needed

# Specific repositories (optional)
targets: [] # Individual repo URLs if needed
```

For token management best practices, see [Security Considerations](#-security-considerations).

---

## 🔧 Usage

### Basic Commands

#### 1. One-time Scan

Scan all organizations listed in your configuration:

```bash
# Scan all configured organizations
python -m ghmon_cli scan --config ghmon_config.yaml

# Or using the installed command
ghmon scan --config ghmon_config.yaml

# Scan specific organizations
python -m ghmon_cli scan --config ghmon_config.yaml --orgs "org1,org2"
```

#### 2. Continuous Monitoring

Run periodic scans with automatic notifications:

```bash
# Foreground monitoring (stop with Ctrl+C)
python -m ghmon_cli monitor --config ghmon_config.yaml

# Background monitoring with screen
screen -dmS ghmon-monitor python -m ghmon_cli monitor --config ghmon_config.yaml
screen -r ghmon-monitor  # Reattach to session

# Background monitoring with nohup
nohup python -m ghmon_cli monitor --config ghmon_config.yaml > monitor.log 2>&1 &
```

#### 3. Test Notifications

Verify your notification setup:

```bash
# Test all enabled notification channels
python -m ghmon_cli notify --test --config ghmon_config.yaml

# Or using the installed command
ghmon notify --test --config ghmon_config.yaml
```

#### 4. Configuration Validation

Validate your configuration file:

```bash
# Check configuration syntax and connectivity
python -m ghmon_cli validate --config ghmon_config.yaml

# Test API token connectivity
python -m ghmon_cli validate --config ghmon_config.yaml --test-tokens
```

### Advanced Usage

#### Custom Output Directory

```bash
python -m ghmon_cli scan --config ghmon_config.yaml --output-dir /custom/path
```

#### Verbose Logging

```bash
python -m ghmon_cli scan --config ghmon_config.yaml --log-level DEBUG
```

#### Dry Run Mode

```bash
python -m ghmon_cli scan --config ghmon_config.yaml --dry-run
```

---

## 🔧 Configuration Reference (ghmon_config.yaml)

```yaml
general:
  log_level: INFO # Logging verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL
  output_dir: ./scan_results # Where JSON/Markdown results are saved
  api_concurrency: 3 # Number of parallel API requests

operation:
  scan_interval: 21600 # Seconds between monitor cycles (default: 6 hours)
  max_commits_for_full_extraction: 30000 # Skip deep history analysis if repo has more commits
  scan_only_on_change: true # Only scan repositories that have new commits

github:
  enabled: true
  api_url: https://api.github.com
  tokens:
    - YOUR_GITHUB_PAT_1
    - YOUR_GITHUB_PAT_2

gitlab:
  enabled: true
  api_url: https://gitlab.com/api/v4
  tokens:
    - YOUR_GITLAB_PAT

notifications:
  discord:
    enabled: true
    webhook_url: YOUR_DISCORD_WEBHOOK_URL
  telegram:
    enabled: true
    bot_token: YOUR_TELEGRAM_BOT_TOKEN
    chat_id: YOUR_TELEGRAM_CHAT_ID

trufflehog:
  concurrency: 5 # Number of parallel TruffleHog scans
  shallow_clone_timeout: 300
  full_clone_timeout: 1200
  shallow_scan_timeout: 600
  full_scan_timeout: 1800
  git_rev_list_timeout: 900
  git_diff_timeout: 180
  git_show_timeout: 180
  git_unpack_timeout: 900
```

---

## 📂 Output Files

Scan results are organized in the directory specified by `general.output_dir`:

### File Structure

```
scan_results/
├── scan_summary_2024-01-15_14-30-45.md     # Human-readable summary
├── scan_run_2024-01-15_14-30-45.json       # Detailed JSON results
├── findings/                                # Individual finding details
│   ├── org1_repo1_findings.json
│   └── org2_repo2_findings.json
└── logs/                                    # Scan logs
    └── ghmon_2024-01-15.log
```

### File Descriptions

- **`scan_summary_<timestamp>.md`**: Markdown summary with key findings and statistics
- **`scan_run_<timestamp>.json`**: Complete scan metadata, configuration, and results
- **`findings/*.json`**: Detailed findings per repository with full context
- **`logs/*.log`**: Detailed execution logs for debugging

---

## 🔍 Troubleshooting

### Common Issues

#### TruffleHog Not Found

```bash
# Check if TruffleHog is installed
which trufflehog

# Install TruffleHog if missing
# Download from: https://github.com/trufflesecurity/trufflehog/releases
```

#### Notification Issues

```bash
# Test notification connectivity
python -m ghmon_cli notify --test --config ghmon_config.yaml

# Check configuration:
# - Verify webhook URLs are correct
# - Ensure bot tokens are valid
# - Confirm chat IDs are accurate
# - Check that enabled: true is set
```

#### Rate Limiting

- **Multiple Tokens**: Configure multiple API tokens for automatic rotation
- **Reduce Concurrency**: Lower `trufflehog.concurrency` and `api_concurrency`
- **Increase Timeouts**: Adjust timeout values in configuration
- **Monitor Usage**: Check API rate limit status in logs

#### Performance Issues

- **Large Repositories**: Increase timeout values for large repos
- **Memory Usage**: Reduce concurrency for memory-constrained systems
- **Network Issues**: Check internet connectivity and proxy settings

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Run with debug logging
python -m ghmon_cli scan --config ghmon_config.yaml --log-level DEBUG

# Check logs for detailed error information
tail -f scan_results/logs/ghmon_$(date +%Y-%m-%d).log
```

---

## 🔒 Security Considerations

### API Token Management

`ghmon` now features enhanced token management with automatic rotation and rate limit handling:

- **Multiple Token Support**:

  - Configure multiple tokens for both GitHub and GitLab
  - Automatic token rotation when rate limits are hit
  - Smart token selection based on remaining quota
  - Automatic recovery of rate-limited tokens

- **Environment Variables**:
  The most secure way to provide API tokens is through environment variables:

  - **GitHub Tokens**: `GHMON_GITHUB_TOKENS`
  - **GitLab Tokens**: `GHMON_GITLAB_TOKENS`

  You can set these variables in your shell environment:

  ```bash
  export GHMON_GITHUB_TOKENS="token1,token2,token3"
  export GHMON_GITLAB_TOKENS="token1,token2"
  ```

- **Configuration File**:
  You can also specify tokens in `ghmon_config.yaml`:
  ```yaml
  github:
    tokens:
      - token1
      - token2
      - token3
  gitlab:
    tokens:
      - token1
      - token2
  ```

### Protecting `ghmon_config.yaml`

- Set strict file permissions:
  ```bash
  chmod 600 ghmon_config.yaml
  ```
- Environment variables will override configuration file tokens if both are set
- Keep your configuration file secure and never commit it to version control

### Output Files

- Scan results are saved in the directory specified by `general.output_dir`
- Handle output files according to your organization's security policies
- Consider implementing automatic cleanup of old scan results

---

## 📖 Getting Started

### Quick Setup Guide

1. **Install Prerequisites**

   ```bash
   # Install Python 3.8+, Git, and TruffleHog
   python3 --version  # Verify Python installation
   git --version      # Verify Git installation
   ```

2. **Clone and Install**

   ```bash
   git clone https://github.com/sl4x0/ghmon.git
   cd ghmon
   ./install.sh
   ```

3. **Configure**

   ```bash
   cp ghmon_config.yaml.example ghmon_config.yaml
   # Edit ghmon_config.yaml with your settings
   ```

4. **Test Setup**

   ```bash
   python -m ghmon_cli notify --test --config ghmon_config.yaml
   ```

5. **Run Your First Scan**
   ```bash
   python -m ghmon_cli scan -o ORG_NAME --config ghmon_config.yaml
   ```

---

## 🧪 Testing

Run the local test suite with:

```bash
pytest -q
```
