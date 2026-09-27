import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class ZohoClient:
    """Read-only client for the Zoho People API."""

    def __init__(self):
        self.client_id = os.getenv("ZOHO_CLIENT_ID")
        self.client_secret = os.getenv("ZOHO_CLIENT_SECRET")
        self.refresh_token = os.getenv("ZOHO_REFRESH_TOKEN")

        self.api_domain = os.getenv(
            "ZOHO_API_DOMAIN",
            "https://people.zoho.com",
        )

        if not self.client_id:
            raise RuntimeError("ZOHO_CLIENT_ID is missing from .env")

        if not self.client_secret:
            raise RuntimeError("ZOHO_CLIENT_SECRET is missing from .env")

        if not self.refresh_token:
            raise RuntimeError("ZOHO_REFRESH_TOKEN is missing from .env")

        self.access_token = None
        self.access_token_expires_at = 0

    def _get_access_token(self):
        """Get a valid access token using the Zoho refresh token."""

        # Reuse the current access token if it is still valid.
        if (
            self.access_token
            and time.time() < self.access_token_expires_at - 60
        ):
            return self.access_token

        response = requests.post(
            "https://accounts.zoho.com/oauth/v2/token",
            data={
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        access_token = data.get("access_token")

        if not access_token:
            raise RuntimeError(
                f"Zoho did not return an access token: {data}"
            )

        self.access_token = access_token

        expires_in = data.get("expires_in", 3600)
        self.access_token_expires_at = time.time() + expires_in

        return self.access_token

    def _sanitize_for_logging(self, data):
        """Sanitize response body for safe debugging without leaking employee PII or secrets."""
        if isinstance(data, list):
            sample_keys = list(data[0].keys()) if data and isinstance(data[0], dict) else []
            return f"[{len(data)} record(s) returned. PII redacted. Fields: {sample_keys}]"
        elif isinstance(data, dict):
            # If error response, it contains no PII, safe to display error structure
            if "response" in data and "errors" in data.get("response", {}):
                return data
            if "errors" in data or "error" in data:
                return data
            sanitized = {}
            for k, v in data.items():
                if isinstance(v, list):
                    sanitized[k] = f"[{len(v)} item(s). PII redacted]"
                elif isinstance(v, dict):
                    sanitized[k] = f"{{fields: {list(v.keys())}}}"
                else:
                    sanitized[k] = "<redacted>"
            return sanitized
        return "<redacted>"

    def _request(self, method, endpoint, **kwargs):
        """Make an authenticated request to Zoho People. Strictly read-only."""

        # Enforce read-only constraint
        if method.upper() != "GET":
            raise ValueError(
                f"Write operation '{method}' rejected. ZohoClient is strictly read-only."
            )

        token = self._get_access_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Zoho-oauthtoken {token}"

        url = f"{self.api_domain.rstrip('/')}/{endpoint.lstrip('/')}"

        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=30,
            **kwargs,
        )

        # Safe debugging information:
        # Prints HTTP status and response details without ever exposing tokens or PII.
        print(f"\n[Zoho API] Request: {method.upper()} {endpoint}")
        print(f"[Zoho API] HTTP Status: {response.status_code}")

        if response.status_code != 200:
            # Zoho error responses contain status, error code, and error message (no PII)
            try:
                err_data = response.json()
                print(f"[Zoho API] Response body: {err_data}")
                err_code = (
                    err_data.get("response", {}).get("errors", {}).get("code")
                    or err_data.get("errors", {}).get("code")
                )
                if err_code == 7218:
                    print(
                        "[Zoho API] Note: Error 7218 ('Invalid OAuth Scope') indicates the OAuth token "
                        "lacks the required 'ZOHOPEOPLE.forms.READ' scope. "
                        "Regenerate a grant code at https://api-console.zoho.com/ with scope 'ZOHOPEOPLE.forms.READ'."
                    )
            except Exception:
                print(f"[Zoho API] Response body (text): {response.text[:200]}")
        else:
            try:
                res_data = response.json()
                print(f"[Zoho API] Response body (sanitized): {self._sanitize_for_logging(res_data)}")
            except Exception:
                print(f"[Zoho API] Response received ({len(response.content)} bytes)")

        response.raise_for_status()

        return response.json()

    def get_employee(self, employee_id: str):
        """Get a specific employee from Zoho People.

        Documented endpoints:
        - If employee_id is a numeric Zoho Record ID (>= 15 digits), fetches via
          /api/forms/employee/getDataByID?recordId={record_id}
        - Otherwise filters via the official Forms View:
          /api/forms/P_EmployeeView/records?searchColumn=EMPLOYEEID&searchValue={employee_id}
        """
        str_id = str(employee_id).strip()
        if str_id.isdigit() and len(str_id) >= 15:
            return self.get_employee_by_record_id(str_id)

        return self._request(
            "GET",
            "/api/forms/P_EmployeeView/records",
            params={
                "searchColumn": "EMPLOYEEID",
                "searchValue": str_id,
            },
        )

    def get_employee_by_record_id(self, record_id: str):
        """Get an employee record by Zoho internal Record ID.

        Documented endpoint: GET /api/forms/employee/getDataByID
        Required scope: ZOHOPEOPLE.forms.READ
        """
        return self._request(
            "GET",
            "/api/forms/employee/getDataByID",
            params={"recordId": str(record_id).strip()},
        )

    def get_employees(self, s_index: int = 1, limit: int = 200):
        """Retrieve employee records from Zoho People using the official Forms API.

        Documented endpoint: GET /api/forms/P_EmployeeView/records
        Required scope: ZOHOPEOPLE.forms.READ
        Parameters:
            s_index (int): Starting index for pagination (default: 1).
            limit (int): Number of records to return (10 to 200, default: 200).
        """
        return self._request(
            "GET",
            "/api/forms/P_EmployeeView/records",
            params={
                "sIndex": max(1, s_index),
                "rec_limit": min(200, max(10, limit)),
            },
        )


if __name__ == "__main__":
    client = ZohoClient()

    print("Testing Zoho authentication...")

    client._get_access_token()

    print("Authentication successful!")
    print("Access token received (identity hidden).")

    print("\nFetching employee data via documented endpoint...")

    try:
        employees = client.get_employees()
        print("\nEmployee API request successful!")
        print("Employee data retrieved successfully.")

        if isinstance(employees, dict):
            print("Response top-level keys:", list(employees.keys()))
        elif isinstance(employees, list):
            print(f"Records returned: {len(employees)}")
        else:
            print("Response type:", type(employees).__name__)
    except requests.exceptions.HTTPError as err:
        print(f"\nAPI request returned HTTP error: {err.response.status_code}")