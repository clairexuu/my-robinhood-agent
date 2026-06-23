from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib import error, parse, request


class HttpJsonClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_headers = dict(default_headers or {})

    def get_json(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = self._url(path, params or {})
        data = self.get_json_any_absolute(url)
        if not isinstance(data, dict):
            raise ValueError("HTTP JSON response must be an object")
        return data

    def get_json_or_list(self, path: str, params: Optional[Dict[str, str]] = None) -> Any:
        url = self._url(path, params or {})
        data = self.get_json_any_absolute(url)
        if not isinstance(data, (dict, list)):
            raise ValueError("HTTP JSON response must be an object or array")
        return data

    def get_json_absolute(self, url: str) -> Dict[str, Any]:
        data = self.get_json_any_absolute(url)
        if not isinstance(data, dict):
            raise ValueError("HTTP JSON response must be an object")
        return data

    def get_json_any_absolute(self, url: str) -> Any:
        http_request = request.Request(url, headers=self.default_headers, method="GET")
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"HTTP request failed: {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise ValueError(f"HTTP request failed: {exc.reason}") from exc
        return data

    def _url(self, path: str, params: Dict[str, str]) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        query = parse.urlencode(params)
        if query:
            return f"{self.base_url}{normalized_path}?{query}"
        return f"{self.base_url}{normalized_path}"
