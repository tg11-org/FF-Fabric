"""
Proxmox REST API client wrapper.

Provides generic GET/POST methods with authentication, error handling,
and JSON parsing for Proxmox Virtual Environment API.
"""

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fabric.exceptions import ProviderError

logger = logging.getLogger(__name__)


class ProxmoxClient:
    """
    Proxmox REST API client with session management and error handling.

    Uses requests.Session for connection pooling and HTTP/HTTPS transport.
    Handles token-based authentication, automatic retries, and response parsing.

    Example:
        client = ProxmoxClient(
            base_url="https://proxmox.example.com:8006",
            api_token="user@pam!tokenid=abcd1234-efgh-5678-ijkl-mnopqrstuv"
        )

        # GET request
        nodes = client.get("/api2/json/nodes")

        # POST request
        result = client.post(
            "/api2/json/nodes/node1/lxc",
            data={
                "vmid": 100,
                "hostname": "container1",
                "memory": 2048,
            }
        )
    """

    # Retry strategy: exponential backoff for transient errors
    DEFAULT_RETRIES = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )

    def __init__(
        self,
        base_url: str,
        api_token: str,
        verify_ssl: bool = True,
        timeout_seconds: int = 30,
        max_retries: Optional[Retry] = None,
    ):
        """
        Initialize Proxmox API client.

        Args:
            base_url: Proxmox API base URL (e.g., https://proxmox.example.com:8006)
            api_token: API token in format "user@realm!tokenid=<token>"
                       e.g., "root@pam!tokenid=12345678-1234-1234-1234-123456789012"
            verify_ssl: Whether to verify SSL certificates (default: True)
            timeout_seconds: Default timeout for requests in seconds (default: 30)
            max_retries: Retry strategy (uses DEFAULT_RETRIES if not provided)

        Raises:
            ValueError: If base_url or api_token is invalid
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if not api_token:
            raise ValueError("api_token cannot be empty")
        if "!" not in api_token:
            raise ValueError(
                "api_token must be in format 'user@realm!tokenid=<token>'"
            )

        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds

        # Create persistent session with retry strategy
        self.session = requests.Session()
        retry_strategy = max_retries or self.DEFAULT_RETRIES
        adapter = HTTPAdapter(max_retries=retry_strategy)

        # Mount adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers with token authentication
        self.session.headers.update(
            {
                "Authorization": f"PVEAPIToken={api_token}",
                "Content-Type": "application/json",
            }
        )

        # Disable SSL warnings if verify_ssl is False
        if not verify_ssl:
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info(f"ProxmoxClient initialized for {base_url}")

    def _build_url(self, path: str) -> str:
        """
        Build full URL from base URL and path.

        Args:
            path: API path (e.g., "/api2/json/nodes")

        Returns:
            Full URL (e.g., "https://proxmox.example.com:8006/api2/json/nodes")
        """
        return urljoin(self.base_url, path.lstrip("/"))

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Perform a GET request to the Proxmox API.

        Args:
            path: API endpoint path (e.g., "/api2/json/nodes")
            params: Query parameters dictionary
            timeout: Request timeout in seconds (uses default if not provided)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ProviderError: If request fails or response indicates an error
        """
        url = self._build_url(path)
        timeout = timeout or self.timeout_seconds

        logger.debug(f"GET {url} params={params}")

        try:
            response = self.session.get(
                url,
                params=params,
                verify=self.verify_ssl,
                timeout=timeout,
            )
            return self._parse_response(response, url, "GET")
        except requests.Timeout:
            raise ProviderError(
                f"GET request to {url} timed out after {timeout} seconds"
            )
        except requests.RequestException as e:
            raise ProviderError(f"GET request to {url} failed: {str(e)}")

    def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Perform a POST request to the Proxmox API.

        Args:
            path: API endpoint path (e.g., "/api2/json/nodes/node1/lxc")
            data: Request body dictionary (will be sent as JSON)
            params: Query parameters dictionary
            timeout: Request timeout in seconds (uses default if not provided)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ProviderError: If request fails or response indicates an error
        """
        url = self._build_url(path)
        timeout = timeout or self.timeout_seconds

        logger.debug(f"POST {url} data={data} params={params}")

        try:
            response = self.session.post(
                url,
                json=data,
                params=params,
                verify=self.verify_ssl,
                timeout=timeout,
            )
            return self._parse_response(response, url, "POST")
        except requests.Timeout:
            raise ProviderError(
                f"POST request to {url} timed out after {timeout} seconds"
            )
        except requests.RequestException as e:
            raise ProviderError(f"POST request to {url} failed: {str(e)}")

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Perform a DELETE request to the Proxmox API.

        Args:
            path: API endpoint path (e.g., "/api2/json/nodes/node1/lxc/100")
            params: Query parameters dictionary
            timeout: Request timeout in seconds (uses default if not provided)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ProviderError: If request fails or response indicates an error
        """
        url = self._build_url(path)
        timeout = timeout or self.timeout_seconds

        logger.debug(f"DELETE {url} params={params}")

        try:
            response = self.session.delete(
                url,
                params=params,
                verify=self.verify_ssl,
                timeout=timeout,
            )
            return self._parse_response(response, url, "DELETE")
        except requests.Timeout:
            raise ProviderError(
                f"DELETE request to {url} timed out after {timeout} seconds"
            )
        except requests.RequestException as e:
            raise ProviderError(f"DELETE request to {url} failed: {str(e)}")

    def _parse_response(
        self, response: requests.Response, url: str, method: str
    ) -> Dict[str, Any]:
        """
        Parse and validate HTTP response.

        Args:
            response: requests.Response object
            url: URL that was requested (for logging)
            method: HTTP method (for logging)

        Returns:
            Parsed JSON response data

        Raises:
            ProviderError: If response indicates an error or cannot be parsed
        """
        # Log response status
        logger.debug(f"{method} {url} -> {response.status_code}")

        # Check for HTTP errors
        if response.status_code == 401:
            raise ProviderError(
                "Proxmox API authentication failed",
                provider_code="401",
                provider_detail="Invalid or expired API token",
            )

        if response.status_code == 403:
            raise ProviderError(
                "Proxmox API permission denied",
                provider_code="403",
                provider_detail="Insufficient permissions for this operation",
            )

        if response.status_code == 404:
            raise ProviderError(
                f"Proxmox API resource not found: {url}",
                provider_code="404",
                provider_detail="The requested resource does not exist",
            )

        if response.status_code >= 400:
            error_msg = self._extract_error_message(response)
            raise ProviderError(
                f"Proxmox API error: {error_msg}",
                provider_code=str(response.status_code),
                provider_detail=response.text[:200],
            )

        # Parse JSON response
        try:
            data = response.json()
            logger.debug(f"Response: {data}")
            return data
        except ValueError as e:
            raise ProviderError(
                f"Failed to parse Proxmox API response as JSON",
                provider_code=str(response.status_code),
                provider_detail=str(e),
            )

    def _extract_error_message(self, response: requests.Response) -> str:
        """
        Extract human-readable error message from Proxmox error response.

        Proxmox API returns errors in format:
        {
            "data": null,
            "errors": "error message here"
        }

        Args:
            response: requests.Response object

        Returns:
            Error message string
        """
        try:
            data = response.json()
            if isinstance(data, dict):
                if "errors" in data:
                    return str(data["errors"])
                if "message" in data:
                    return str(data["message"])
            return response.text[:200]
        except (ValueError, KeyError):
            return response.text[:200]

    def close(self) -> None:
        """
        Close the session and clean up resources.

        Should be called when client is no longer needed.
        """
        if self.session:
            self.session.close()
            logger.info("ProxmoxClient session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures session is closed."""
        self.close()
