"""Playwright UI test fixtures.

All UI tests run against a live server. Start the server and seed data first:

    python wsgi.py &
    python scripts/seed_data.py

Then run:
    pytest tests/ui/ --base-url http://localhost:8080            # headless (CI)
    pytest tests/ui/ --base-url http://localhost:8080 --headed   # visible browser

Credentials:
    admin / admin  — system-administrator (created by seed_data.py)

UI selectors (from app.js / index.html):
    Login form : #li-user, #li-pass, button "Sign In"
    Post-login : #topbar-user (.user-name), #sidebar, #content
    Logout     : button "Sign Out" (inside #user-dropdown)
    Navigate   : anchor[href="#{section}"] in #sidebar
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 15_000  # ms


# ── Login / logout helpers ─────────────────────────────────────────────────────


def login(page: Page, base_url: str, username: str = "admin", password: str = "admin") -> None:
    """Navigate to the app and log in through the login form."""
    page.goto(base_url, wait_until="domcontentloaded")
    # The login page is rendered dynamically — wait for the username input
    page.wait_for_selector("#li-user", timeout=DEFAULT_TIMEOUT)
    page.fill("#li-user", username)
    page.fill("#li-pass", password)
    page.click("button:has-text('Sign In')")
    # After login the topbar user widget is rendered
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)


def logout(page: Page) -> None:
    """Log out via the user menu."""
    page.click("#topbar-user button.user-menu-btn")
    page.wait_for_selector("#user-dropdown", timeout=5_000)
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("#li-user", timeout=DEFAULT_TIMEOUT)


def navigate_to(page: Page, section: str) -> None:
    """Click a sidebar nav link by its href hash."""
    page.click(f'a[href="#{section}"]')
    # Wait for the content area to update
    page.wait_for_timeout(400)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    """Resolved base URL — defaults to http://localhost:8080."""
    url = pytestconfig.getoption("--base-url", default=None)
    return url or "http://localhost:8080"


@pytest.fixture()
def logged_in_page(page: Page, base_url: str) -> Page:
    """A Playwright Page already authenticated as admin."""
    login(page, base_url)
    yield page


@pytest.fixture(scope="session")
def api_token(base_url: str) -> str:
    """Obtain a JWT for API setup calls (no browser needed)."""
    payload = json.dumps({"username": "admin", "password": "admin"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["token"]


@pytest.fixture(scope="session")
def api(base_url: str, api_token: str) -> "ApiClient":
    """Thin REST helper for setting up / tearing down test data."""
    return ApiClient(base_url, api_token)


class ApiClient:
    """Minimal HTTP client for test setup — not a browser fixture."""

    def __init__(self, base: str, token: str) -> None:
        self._base = base.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get(self, path: str) -> dict:
        req = urllib.request.Request(
            f"{self._base}{path}", headers=self._headers, method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, headers=self._headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read())

    def delete(self, path: str) -> int:
        req = urllib.request.Request(
            f"{self._base}{path}", headers=self._headers, method="DELETE"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
