"""Check that protected, read-only endpoints reject requests without credentials."""

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = os.getenv("SANILINK_API_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SECONDS = 10
UNSAFE_GET_PATHS = {"/invite/{registration_id}/revoke"}


def request_status(url: str, method: str) -> tuple[int, str | None]:
    request = Request(url, headers={"Accept": "application/json"}, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.headers.get("WWW-Authenticate")
    except HTTPError as error:
        return error.code, error.headers.get("WWW-Authenticate")


def load_openapi() -> dict:
    try:
        with urlopen(f"{BASE_URL}/openapi.json", timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"OpenAPI konnte nicht geladen werden: {error}") from error


def is_protected(operation: dict, document: dict) -> bool:
    security = operation.get("security", document.get("security", []))
    return bool(security)


def make_path(path: str, parameters: list[dict]) -> str:
    path_parameters = {
        parameter["name"]: parameter
        for parameter in parameters
        if parameter.get("in") == "path"
    }

    def replace_parameter(match: re.Match[str]) -> str:
        parameter = path_parameters.get(match.group(1), {})
        schema = parameter.get("schema", {})
        if schema.get("format") == "uuid":
            value = "00000000-0000-0000-0000-000000000000"
        elif schema.get("type") == "integer":
            value = "0"
        else:
            value = "auth-check-placeholder"
        return quote(value, safe="")

    return re.sub(r"\{([^{}]+)\}", replace_parameter, path)


def main() -> int:
    try:
        document = load_openapi()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 2

    protected_operations: list[tuple[str, str, str]] = []
    for path, path_item in document.get("paths", {}).items():
        for method, operation in path_item.items():
            method = method.upper()
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                if is_protected(operation, document):
                    parameters = path_item.get("parameters", []) + operation.get(
                        "parameters", []
                    )
                    endpoint = make_path(path, parameters)
                    protected_operations.append((method, endpoint, path))

    if not protected_operations:
        print("Keine geschützten API-Endpunkte in OpenAPI gefunden.")
        return 1

    print(f"Prüfe geschützte Endpunkte ohne Anmeldung auf {BASE_URL}")
    failed = False
    checked = 0
    for method, endpoint, path in protected_operations:
        if method not in {"GET", "HEAD"}:
            print(
                f"ÜBERSPRUNGEN {method:7} {endpoint}: "
                "schreibende Requests werden nicht ausgeführt"
            )
            continue
        if method == "GET" and path in UNSAFE_GET_PATHS:
            print(f"ÜBERSPRUNGEN {method:7} {endpoint}: führt eine Aktion aus")
            continue

        try:
            code, challenge = request_status(f"{BASE_URL}{endpoint}", method)
        except (URLError, TimeoutError) as error:
            print(f"FEHLER  {method:7} {endpoint}: Anfrage fehlgeschlagen: {error}")
            failed = True
            continue

        checked += 1
        if code == 401 and challenge and challenge.lower().startswith("bearer"):
            result = "SICHER: Authentifizierung gefordert"
        else:
            result = "NICHT BESTÄTIGT: unerwartete Antwort"
            failed = True
        challenge_info = f", WWW-Authenticate: {challenge}" if challenge else ""
        print(f"{result:40} {method:7} {endpoint}: HTTP {code}{challenge_info}")

    print(f"Unauthentifiziert geprüft: {checked} Endpunkte")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
