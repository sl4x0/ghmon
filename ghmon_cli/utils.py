# utils.py

import os
import logging
from typing import Dict, Any, Optional, Tuple, Union

# Use specific logger for utils
logger = logging.getLogger('ghmon-cli.utils')

# --- Constants ---
MAX_SNIPPET_LEN = 100  # Configurable max length for snippet in Finding ID
MAX_DETECTOR_LEN = 50  # Max length for detector name in ID
_MISSING_SNIPPET = "N/A_Snippet"  # Constant for missing snippet marker

# --- Type Alias for Clarity ---
FindingID = Tuple[str, str, int, str, str]  # repo_full_name, normalized_path, line_num, snippet_part, detector


def create_finding_id(
    repo_full_name: str,
    finding: Dict[str, Any]
) -> Optional[FindingID]:
    """
    Builds a stable, hashable ID tuple from finding components.

    The ID aims to uniquely identify a specific secret occurrence based on
    repository, file path, line number, a snippet of the secret, and the detector.
    Handles variations in finding structure and normalizes paths.

    Args:
        repo_full_name: Full name of the repository (e.g., 'owner/repo')
        finding: Dictionary containing the finding data

    Returns:
        Optional[FindingID]: A tuple representing the ID, or None if essential
                             components are missing.
    """
    if not repo_full_name or not isinstance(finding, dict):
        logger.warning("Invalid input: repo_full_name must be non-empty string and finding must be dict")
        return None

    try:
        # --- Extract Path and Line ---
        metadata = finding.get('SourceMetadata', {})
        data = metadata.get('Data', {})
        filesystem = data.get('Filesystem', {})
        file_path_raw = filesystem.get('file')
        line_str = filesystem.get('line')

        # Fallbacks if standard path/line missing
        if file_path_raw is None:
            file_path_raw = finding.get('file')
            logger.debug(f"Finding ID: Using fallback 'file' key for {repo_full_name}")
        if line_str is None:
            line_str = finding.get('line')
            logger.debug(f"Finding ID: Using fallback 'line' key for {repo_full_name}")

        if file_path_raw is None or line_str is None:
            logger.warning(
                f"Cannot create stable ID for finding in {repo_full_name}: "
                f"Missing Path or Line key. Finding keys: {list(finding.keys())}"
            )
            return None

        # --- Process Line Number ---
        line_num = _parse_line_number(line_str, repo_full_name)
        if line_num < 0:
            logger.warning(
                f"Cannot create stable ID for finding in {repo_full_name}: "
                f"Invalid line number. Path: '{file_path_raw}'"
            )
            return None

        # --- Process Snippet ---
        snippet = _extract_and_truncate_snippet(finding)
        if snippet == _MISSING_SNIPPET:
            logger.warning(
                f"Cannot create stable ID for finding in {repo_full_name}: "
                f"Missing snippet. Path: '{file_path_raw}', Line: {line_num}"
            )
            return None

        # --- Get and Truncate Detector Name ---
        detector = _extract_and_truncate_detector(finding)

        # --- Final Validation and Path Normalization ---
        normalized_file_path = _normalize_file_path(str(file_path_raw), repo_full_name)
        if not normalized_file_path:
            return None

        # Return the tuple ID
        return (
            str(repo_full_name),
            normalized_file_path,
            line_num,
            snippet,
            detector
        )

    except Exception:
        # Use logger.exception to automatically include traceback
        logger.exception(
            f"Error generating finding ID for finding in {repo_full_name}. "
            f"Finding data snippet: {str(finding)[:200]}..."
        )
        return None


def _parse_line_number(line_str: Union[str, int, None], repo_full_name: str) -> int:
    """Parse and validate line number from various input types."""
    if line_str is None:
        return -1

    try:
        line_num = int(line_str)
        if line_num < 0:
            logger.warning(
                f"Invalid negative line number '{line_num}' for finding ID in {repo_full_name}. Using -1."
            )
            return -1
        return line_num
    except (ValueError, TypeError):
        logger.warning(
            f"Could not convert line '{line_str}' to int for finding ID in {repo_full_name}. Using -1."
        )
        return -1


def _extract_and_truncate_snippet(finding: Dict[str, Any]) -> str:
    """Extract and truncate snippet from finding data."""
    snippet_raw = finding.get('Redacted') or finding.get('Raw')
    if snippet_raw is None:
        return _MISSING_SNIPPET

    snippet = str(snippet_raw).strip()
    if not snippet:
        return _MISSING_SNIPPET

    if len(snippet) <= MAX_SNIPPET_LEN:
        return snippet

    # Truncate with ellipsis in the middle
    ellipsis = "..."
    len_ellipsis = len(ellipsis)
    len_keep = MAX_SNIPPET_LEN - len_ellipsis
    len_head = len_keep // 2
    len_tail = len_keep - len_head
    return snippet[:len_head] + ellipsis + snippet[-len_tail:]


def _extract_and_truncate_detector(finding: Dict[str, Any]) -> str:
    """Extract and truncate detector name from finding data."""
    detector = finding.get('DetectorName', 'UnknownDetector')
    detector = str(detector).strip()

    if not detector:
        detector = 'UnknownDetector'

    if len(detector) > MAX_DETECTOR_LEN:
        return detector[:MAX_DETECTOR_LEN - 3] + '...'

    return detector


def _normalize_file_path(file_path_str: str, repo_full_name: str) -> Optional[str]:
    """Normalize file path to use forward slashes and ensure it's relative."""
    if not file_path_str:
        logger.warning(f"Empty file path for finding ID in {repo_full_name}")
        return None

    try:
        # Normalize path separators and resolve any '..' or '.' components
        normalized = os.path.normpath(file_path_str)
        # Convert to forward slashes for consistency (handle Windows-style backslashes too)
        normalized_file_path = normalized.replace('\\', '/').replace(os.sep, '/')

        # Strip leading slash if present to ensure relative path
        normalized_file_path = normalized_file_path.lstrip('/')

        # Ensure we still have a path after stripping
        if not normalized_file_path:
            logger.warning(f"File path became empty after normalization for {repo_full_name}: '{file_path_str}'")
            return None

        return normalized_file_path

    except (TypeError, ValueError) as path_err:
        logger.warning(
            f"Could not normalize path '{file_path_str}' for finding ID in {repo_full_name}: {path_err}. "
            f"Using raw path."
        )
        # Use raw path with fixed separators as fallback
        fallback_path = file_path_str.replace(os.sep, '/').lstrip('/')
        return fallback_path if fallback_path else None
