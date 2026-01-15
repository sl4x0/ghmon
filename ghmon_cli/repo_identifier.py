# ghmon_cli/repo_identifier.py
"""
Repository identifier module for discovering repositories across Git hosting services.

This module provides functionality to identify repositories from GitHub and GitLab
organizations with proper rate limiting, token management, and error handling.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from urllib.parse import quote_plus
import threading
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

# Import custom exceptions
from .exceptions import RepoIdentificationError, RateLimitError

# Conditional imports for type checking and runtime
if TYPE_CHECKING:
    import requests

# Import requests conditionally
try:
    import requests
    from requests import Session, Response
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Create dummy classes for type hinting
    class Session:
        """Dummy session class for when requests is unavailable."""
        pass

    class Response:
        """Dummy response class for when requests is unavailable."""
        pass

    requests = None  # type: ignore

logger = logging.getLogger('ghmon-cli.repo-identifier')

@dataclass
class TokenState:
    """Represents the state of an individual API token."""
    token: str
    available: bool = True
    reset_time: Optional[datetime] = None
    remaining_requests: Optional[int] = None
    limit: Optional[int] = None


class ServiceConfig(BaseModel):
    """Configuration for a Git hosting service instance."""
    name: str
    type: str
    api_url: str
    clone_url_base: str
    tokens: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    rate_limit_header_remaining: Optional[str] = None
    rate_limit_header_limit: Optional[str] = None
    rate_limit_header_reset: Optional[str] = None
    enabled: bool = True

    @model_validator(mode='after')
    def set_default_rate_limit_headers(self) -> 'ServiceConfig':
        """Set default rate limit headers based on service type."""
        if self.type == 'github':
            if self.rate_limit_header_remaining is None:
                self.rate_limit_header_remaining = 'X-RateLimit-Remaining'
            if self.rate_limit_header_limit is None:
                self.rate_limit_header_limit = 'X-RateLimit-Limit'
            if self.rate_limit_header_reset is None:
                self.rate_limit_header_reset = 'X-RateLimit-Reset'
        elif self.type == 'gitlab':
            if self.rate_limit_header_remaining is None:
                self.rate_limit_header_remaining = 'RateLimit-Remaining'
            # GitLab typically doesn't send a limit header in the same way for project/group APIs,
            # it's often per-user across the API. Reset is the most critical.
            if self.rate_limit_header_reset is None:
                self.rate_limit_header_reset = 'RateLimit-Reset'
        return self

class TokenPool:
    """
    Manages a pool of API tokens with rate limit awareness.
    Each token is tracked individually with its own reset time.
    """

    def __init__(self, tokens: List[str]) -> None:
        """
        Initialize the token pool.

        Args:
            tokens: List of API tokens to manage
        """
        self.tokens: List[TokenState] = [
            TokenState(
                token=token,
                reset_time=None,
                available=True,
                remaining_requests=None,
                limit=None
            )
            for token in tokens
        ]
        self._lock = threading.Lock()

    def get_token(self) -> Optional[str]:
        """
        Get an available token from the pool.
        If no tokens are available, wait for the soonest reset time.

        Returns:
            An available token or None if all tokens are permanently unavailable
        """
        while True:
            with self._lock:
                current_time = datetime.now()

                # Treat tokens with reset_time=None as immediately available
                available_tokens = [
                    t for t in self.tokens
                    if t.available and (t.reset_time is None or current_time >= t.reset_time)
                ]

                if available_tokens:
                    # Sort by remaining quota (descending) and last used time (ascending)
                    best_token = max(
                        available_tokens,
                        key=lambda t: (
                            t.remaining_requests if t.remaining_requests is not None else 0,
                            -t.reset_time.timestamp() if t.reset_time else 0  # Negative because we want least recently used
                        )
                    )
                    best_token.reset_time = current_time
                    return best_token.token

                # If no token is immediately available, find the one with the soonest reset time
                future_reset_tokens = [
                    t for t in self.tokens
                    if t.reset_time and t.reset_time > current_time
                ]

                if not future_reset_tokens:
                    # No tokens have future reset times - they might be stuck
                    # Try to recover by resetting available flags for tokens with past reset times
                    recovered = False
                    for token_state in self.tokens:
                        if token_state.reset_time and token_state.reset_time <= current_time:
                            token_state.available = True
                            token_state.reset_time = current_time
                            recovered = True
                            logger.debug(
                                f"Recovered token {token_state.token[:8]}... "
                                f"was rate limited until {token_state.reset_time.strftime('%H:%M:%S')}"
                            )
                    if recovered:
                        logger.info("Recovered tokens with expired reset times")
                        continue

                # Now all remaining tokens are truly future‐limited, so pick the soonest reset
                if future_reset_tokens:
                    soonest_reset = min(t.reset_time.timestamp() for t in future_reset_tokens if t.reset_time)
                    wait_time = soonest_reset - current_time.timestamp()
                    wait_time += 2.0  # 2 second buffer

                    logger.info(f"All tokens rate limited. Waiting {wait_time:.1f}s for next available token")
                else:
                    logger.error("No token became available after waiting")
                    return None

            if not future_reset_tokens:
                return None

            time.sleep(wait_time)

            with self._lock:
                # After waiting, reset any token whose reset_time has passed
                for token_state in self.tokens:
                    if token_state.reset_time and token_state.reset_time <= datetime.now():
                        token_state.available = True
                        token_state.reset_time = datetime.now()
                        return token_state.token
            
    def mark_token_rate_limited(self, token: str, reset_time: datetime, remaining: int = 0, limit: int = 0) -> None:
        """
        Mark a token as rate limited and set its reset time.

        Args:
            token: The token that hit the rate limit
            reset_time: Unix timestamp when the token will be available again
            remaining: Number of requests remaining in the current window
            limit: Total requests allowed in the window
        """
        with self._lock:
            for token_state in self.tokens:
                if token_state.token == token:
                    token_state.available = False
                    token_state.reset_time = reset_time
                    token_state.remaining_requests = remaining
                    token_state.limit = limit
                    logger.debug(
                        f"Token {token[:8]}... rate limited until "
                        f"{reset_time.strftime('%H:%M:%S')}"
                    )
                    break

    def update_token_quota(self, token: str, remaining: int, limit: int) -> None:
        """
        Update a token's quota information.

        Args:
            token: The token to update
            remaining: Number of requests remaining in the current window
            limit: Total requests allowed in the window
        """
        with self._lock:
            for token_state in self.tokens:
                if token_state.token == token:
                    token_state.remaining_requests = remaining
                    token_state.limit = limit
                    # Mark as unavailable if we're close to the limit
                    if remaining < limit * 0.1:  # Less than 10% remaining
                        token_state.available = False
                    else:
                        token_state.available = True
                    break

    def get_token_stats(self) -> List[Dict[str, Any]]:
        """
        Get current statistics for all tokens.

        Returns:
            List of dictionaries containing token statistics
        """
        with self._lock:
            return [
                {
                    'token': t.token[:8] + '...',  # Truncate for logging
                    'available': t.available,
                    'reset_time': t.reset_time.strftime('%H:%M:%S') if t.reset_time else 'N/A',
                    'remaining': t.remaining_requests,
                    'limit': t.limit
                }
                for t in self.tokens
            ]

class ServiceInstance:
    """Represents a configured Git hosting service instance."""

    def __init__(self, config: ServiceConfig) -> None:
        """Initialize service instance with configuration."""
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required for ServiceInstance")

        self.config = config
        self.token_pool = TokenPool(config.tokens)

        # Import requests here to avoid issues when not available
        import requests as real_requests
        self.session = real_requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json' if config.type == 'github' else 'application/json',
            'User-Agent': 'ghmon-cli'
        })

    def get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get headers for API requests, optionally including a token."""
        headers = dict(self.session.headers)
        if token:
            if self.config.type == 'github':
                headers['Authorization'] = f'token {token}'
            else:  # gitlab
                headers['PRIVATE-TOKEN'] = token
        return headers

class RepositoryIdentifier:
    """
    Identifies repositories across multiple Git hosting services.
    Supports GitHub, GitLab, and their self-hosted instances.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the repository identifier.

        Args:
            config: Configuration dictionary containing service settings
        """
        self.config = config
        self.services: Dict[str, ServiceInstance] = {}
        self._init_services()

    def _init_services(self) -> None:
        """Initialize service instances from configuration."""
        logger.debug("Initializing services in RepositoryIdentifier...")
        self.services = {}  # Reset services

        # Process GitHub configuration from top-level config
        github_config = self.config.get('github', {})
        if github_config.get('enabled', False):
            github_tokens = github_config.get('tokens', [])
            if isinstance(github_tokens, str):
                github_tokens = [github_tokens]
            elif not isinstance(github_tokens, list):
                github_tokens = []

            if github_tokens:
                self.services['github'] = ServiceInstance(
                    config=ServiceConfig(
                        name='github',
                        type='github',
                        api_url=str(github_config.get('api_url', 'https://api.github.com')),
                        clone_url_base='https://github.com',
                        tokens=github_tokens
                    )
                )
                logger.info(f"Initialized GitHub service with {len(github_tokens)} tokens")
            else:
                logger.warning("GitHub service is enabled but no tokens are configured")
        else:
            logger.info("GitHub service is not enabled")

        # Process GitLab configuration from top-level config
        gitlab_config = self.config.get('gitlab', {})
        if gitlab_config.get('enabled', False):
            gitlab_tokens = gitlab_config.get('tokens', [])
            if isinstance(gitlab_tokens, str):
                gitlab_tokens = [gitlab_tokens]
            elif not isinstance(gitlab_tokens, list):
                gitlab_tokens = []

            # Fallback to legacy single token format if no tokens found
            if not gitlab_tokens and 'token' in gitlab_config:
                legacy_token = gitlab_config.get('token', '')
                if legacy_token:
                    gitlab_tokens = [legacy_token]
                    logger.info("Using legacy GitLab token format - consider updating to tokens list")

            if gitlab_tokens:
                self.services['gitlab'] = ServiceInstance(
                    config=ServiceConfig(
                        name='gitlab',
                        type='gitlab',
                        api_url=str(gitlab_config.get('api_url', 'https://gitlab.com/api/v4')),
                        clone_url_base='https://gitlab.com',
                        tokens=gitlab_tokens
                    )
                )
                logger.info(f"Initialized GitLab service with {len(gitlab_tokens)} tokens")
            else:
                logger.warning("GitLab service is enabled but no tokens are configured")
        else:
            logger.info("GitLab service is not enabled")

        if not self.services:
            logger.warning(
                "No Git hosting services (GitHub/GitLab) were initialized. "
                "Repository identification will likely fail for most organizations."
            )
            
    def _get_service_for_org(self, org_name: str) -> Optional[ServiceInstance]:
        """
        Determine which service instance to use for an organization.

        Args:
            org_name: Name of the organization

        Returns:
            ServiceInstance to use, or None if no suitable service found
        """
        # First try to find a service with matching org name in its config
        for service in self.services.values():
            if org_name in service.config.organizations:
                logger.debug(f"Found explicit mapping for {org_name} to service {service.config.name}")
                return service

        # If no explicit mapping, try to parse service:org format
        if ':' in org_name:
            service_name, _ = org_name.split(':', 1)
            for service in self.services.values():
                if service.config.name == service_name:
                    logger.debug(f"Found service mapping from {org_name} to {service.config.name}")
                    return service

        # Fallback to service type based on org name pattern
        if any(org_name.lower().endswith(suffix) for suffix in ['-gitlab', '-gl']):
            service = next((s for s in self.services.values() if s.config.type == 'gitlab'), None)
            if service:
                logger.debug(f"Using GitLab service for {org_name} based on name pattern")
                return service

        # Default to GitHub
        service = next((s for s in self.services.values() if s.config.type == 'github'), None)
        if service:
            logger.debug(f"Using GitHub service for {org_name} as default")
            return service

        logger.warning(f"No suitable service found for organization: {org_name}")
        return None
            
    def _request_with_backoff(
        self,
        service: ServiceInstance,
        method: str,
        url: str,
        **kwargs: Any
    ) -> Response:
        """
        Make an API request with exponential backoff and rate limit handling.

        Args:
            service: ServiceInstance to use
            method: HTTP method
            url: API endpoint URL
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            RateLimitError: If rate limit is hit and cannot be handled
            RepoIdentificationError: For other request failures
        """
        if not REQUESTS_AVAILABLE:
            raise RepoIdentificationError("requests library is required for API calls")

        # Import requests here to avoid issues when not available
        import requests as real_requests

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            token = service.token_pool.get_token()
            if not token:
                raise RateLimitError("No available tokens")

            headers = service.get_headers(token)
            try:
                # Add timeout to prevent hanging
                if 'timeout' not in kwargs:
                    kwargs['timeout'] = 30  # 30 second timeout
                response = service.session.request(method, url, headers=headers, **kwargs)

                # Update token quota from headers using service-specific header names
                remaining = response.headers.get(service.config.rate_limit_header_remaining)
                limit = response.headers.get(service.config.rate_limit_header_limit)
                reset = response.headers.get(service.config.rate_limit_header_reset)

                if all([remaining, limit, reset]):
                    try:
                        service.token_pool.update_token_quota(
                            token,
                            int(remaining),
                            int(limit)
                        )
                    except (ValueError, TypeError):
                        pass

                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    # Rate limit hit
                    reset_ts = float(response.headers.get(service.config.rate_limit_header_reset, time.time() + 60))
                    service.token_pool.mark_token_rate_limited(token, datetime.fromtimestamp(reset_ts))

                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise RateLimitError("Rate limit exceeded after retries")

                response.raise_for_status()
                return response

            except real_requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Request failed: {e}, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise RepoIdentificationError(
                        f"Request failed after {max_retries} retries: {e}. "
                        f"URL: {url}, Method: {method}"
                    )

        raise RepoIdentificationError(
            f"Max retries exceeded for request. "
            f"URL: {url}, Method: {method}"
        )
        
    def identify_by_organization(self, org_name: str) -> List[Dict[str, Any]]:
        """
        Identify repositories for an organization.

        Args:
            org_name: Name of the organization

        Returns:
            List of repository information dictionaries

        Raises:
            RepoIdentificationError: If repository identification fails
        """
        service = self._get_service_for_org(org_name)
        if not service:
            raise RepoIdentificationError(f"No suitable service found for organization: {org_name}")

        try:
            if service.config.type == 'github':
                return self._identify_github_org(service, org_name)
            else:  # gitlab
                return self._identify_gitlab_org(service, org_name)
        except Exception as e:
            raise RepoIdentificationError(f"Failed to identify repositories for {org_name}: {e}") from e

    def identify_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """
        Identify repositories by searching across organizations for a domain.
        This is a placeholder for domain-based discovery.

        Args:
            domain: Domain to search for

        Returns:
            List of repository information dictionaries
        """
        logger.warning(f"Domain-based identification not yet implemented for: {domain}")
        return []

    def identify_from_manual_list(self, repo_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Identify repositories from a manual list of URLs.

        Args:
            repo_urls: List of repository URLs

        Returns:
            List of repository information dictionaries
        """
        repos = []
        for url in repo_urls:
            try:
                # Parse GitHub/GitLab URLs
                if 'github.com' in url:
                    parts = url.rstrip('/').split('/')
                    if len(parts) >= 2:
                        owner, repo_name = parts[-2], parts[-1]
                        repos.append({
                            'name': repo_name,
                            'full_name': f"{owner}/{repo_name}",
                            'clone_url': url if url.endswith('.git') else f"{url}.git",
                            'html_url': url.replace('.git', ''),
                            'platform': 'github',
                            'organization': owner
                        })
                elif 'gitlab.com' in url:
                    parts = url.rstrip('/').split('/')
                    if len(parts) >= 2:
                        owner, repo_name = parts[-2], parts[-1]
                        repos.append({
                            'name': repo_name,
                            'full_name': f"{owner}/{repo_name}",
                            'clone_url': url if url.endswith('.git') else f"{url}.git",
                            'html_url': url.replace('.git', ''),
                            'platform': 'gitlab',
                            'organization': owner
                        })
            except Exception as e:
                logger.warning(f"Failed to parse repository URL {url}: {e}")
                continue
        return repos

    def _identify_github_org(self, service: ServiceInstance, org_name: str) -> List[Dict[str, Any]]:
        """Identify repositories in a GitHub organization with enhanced metadata."""
        repos = []
        page = 1
        per_page = 100
        total_fetched = 0

        # Get repository limit from configuration
        max_repos = self.config.get('operation', {}).get('max_repos_per_org', 1000)
        if max_repos == 0:
            max_repos = float('inf')  # No limit

        logger.info(f"🔍 Discovering repositories for GitHub organization: {org_name}")
        if max_repos != float('inf'):
            logger.info(f"  📊 Repository limit: {max_repos} repositories")

        while True:
            # Ensure no double slashes in URL by stripping trailing slash from api_url
            base_url = str(service.config.api_url).rstrip('/')
            url = f"{base_url}/orgs/{org_name}/repos"
            params = {
                'page': page,
                'per_page': per_page,
                'type': 'all',
                'sort': 'updated',  # Sort by last updated for better prioritization
                'direction': 'desc'
            }

            logger.info(f"  📄 Fetching page {page} (up to {per_page} repos)...")
            response = self._request_with_backoff(service, 'GET', url, params=params)
            page_repos = response.json()

            if not page_repos:
                break

            total_fetched += len(page_repos)
            logger.info(f"  ✅ Page {page}: Found {len(page_repos)} repositories (total: {total_fetched})")

            for repo in page_repos:
                # Enhanced repository metadata for better scanning decisions
                repo_info = {
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'clone_url': repo['clone_url'],
                    'html_url': repo.get('html_url', ''),
                    'platform': 'github',
                    'organization': org_name,
                    # Enhanced metadata for scanning prioritization
                    'private': repo.get('private', False),
                    'archived': repo.get('archived', False),
                    'disabled': repo.get('disabled', False),
                    'fork': repo.get('fork', False),
                    'default_branch': repo.get('default_branch', 'main'),
                    'updated_at': repo.get('updated_at'),
                    'pushed_at': repo.get('pushed_at'),
                    'size': repo.get('size', 0),  # Repository size in KB
                    'language': repo.get('language'),
                    'topics': repo.get('topics', []),
                    'visibility': repo.get('visibility', 'private' if repo.get('private') else 'public')
                }

                # Skip archived, disabled, or empty repositories by default
                if repo_info['archived']:
                    logger.debug(f"⏭️ Skipping archived repository: {repo_info['full_name']}")
                    continue
                if repo_info['disabled']:
                    logger.debug(f"⏭️ Skipping disabled repository: {repo_info['full_name']}")
                    continue
                if repo_info['size'] == 0:
                    logger.debug(f"⏭️ Skipping empty repository: {repo_info['full_name']}")
                    continue

                repos.append(repo_info)

                # Check if we've reached the repository limit
                if len(repos) >= max_repos:
                    logger.info(f"  🛑 Reached repository limit ({max_repos}). Stopping discovery.")
                    break

            # Check if we've reached the repository limit (outside the loop too)
            if len(repos) >= max_repos:
                break

            if len(page_repos) < per_page:
                break

            page += 1

        logger.info(f"✅ Found {len(repos)} active repositories in {org_name}")
        if len(repos) >= max_repos and max_repos != float('inf'):
            logger.info(f"  ⚠️ Note: Discovery was limited to {max_repos} repositories. There may be more.")
        return repos
        
    def _identify_gitlab_org(self, service: ServiceInstance, org_name: str) -> List[Dict[str, Any]]:
        """Identify repositories in a GitLab group."""
        repos = []
        page = 1
        per_page = 100

        while True:
            # Ensure no double slashes in URL by stripping trailing slash from api_url
            base_url = str(service.config.api_url).rstrip('/')
            url = f"{base_url}/groups/{org_name}/projects"
            params = {
                'page': page,
                'per_page': per_page,
                'include_subgroups': 'true'
            }

            response = self._request_with_backoff(service, 'GET', url, params=params)
            page_repos = response.json()

            if not page_repos:
                break

            for repo in page_repos:
                repos.append({
                    'name': repo['name'],
                    'full_name': f"{org_name}/{repo['path']}",
                    'clone_url': repo['http_url_to_repo'],
                    'html_url': repo.get('web_url', ''),
                    'platform': 'gitlab',
                    'organization': org_name,
                    'project_id': repo['id'],  # Store the numeric project ID
                    'path_with_namespace': repo['path_with_namespace']  # Store the full path
                })

            if len(page_repos) < per_page:
                break

            page += 1

        return repos
        
    def get_latest_commit_sha(self, repo_info: Dict[str, Any]) -> Optional[str]:
        """
        Get the latest commit SHA for a repository.
        
        Args:
            repo_info: Repository information dictionary
            
        Returns:
            Latest commit SHA or None if not found
        """
        service = self._get_service_for_org(repo_info.get('organization', ''))
        if not service:
            return None
            
        try:
            if service.config.type == 'github':
                return self._get_github_sha(service, repo_info)
            else:  # gitlab
                return self._get_gitlab_sha(service, repo_info)
        except Exception as e:
            logger.error(f"Failed to get SHA for {repo_info.get('full_name')}: {e}")
            return None
            
    def _get_github_sha(self, service: ServiceInstance, repo_info: Dict[str, Any]) -> Optional[str]:
        """Get latest commit SHA from GitHub."""
        # Ensure no double slashes in URL by stripping trailing slash from api_url
        base_url = str(service.config.api_url).rstrip('/')
        url = f"{base_url}/repos/{repo_info['full_name']}/commits"
        params = {'per_page': 1}
        
        response = self._request_with_backoff(service, 'GET', url, params=params)
        commits = response.json()
        
        if commits and isinstance(commits, list):
            return commits[0]['sha']
        return None
        
    def _get_gitlab_sha(self, service: ServiceInstance, repo_info: Dict[str, Any]) -> Optional[str]:
        """Get latest commit SHA from GitLab."""
        # Prefer project ID if available, fall back to path_with_namespace, then full_name
        project_identifier = (
            repo_info.get('project_id') or
            repo_info.get('path_with_namespace') or
            repo_info['full_name']
        )
        
        # URL encode if using path-based identifier
        if not isinstance(project_identifier, int):
            project_identifier = quote_plus(str(project_identifier))

        # Ensure no double slashes in URL by stripping trailing slash from api_url
        base_url = str(service.config.api_url).rstrip('/')
        url = f"{base_url}/projects/{project_identifier}/repository/commits"
        params = {'per_page': 1}
        
        try:
            response = self._request_with_backoff(service, 'GET', url, params=params)
            commits = response.json()
            
            if commits and isinstance(commits, list):
                return commits[0]['id']
                
            logger.warning(
                f"No commits found for GitLab project {project_identifier} "
                f"(using {'ID' if isinstance(project_identifier, int) else 'path'})"
            )
            return None
            
        except Exception as e:
            logger.error(
                f"Failed to get SHA for GitLab project {project_identifier}: {e}",
                exc_info=True
            )
            return None
