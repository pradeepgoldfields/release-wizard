"""UI E2E: Authentication flows — login, logout, bad credentials, token persistence."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import DEFAULT_TIMEOUT, login, logout, navigate_to

pytestmark = pytest.mark.ui


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_form_visible_on_load(page: Page, base_url: str) -> None:
    """The login form must be shown when the app first loads."""
    page.goto(base_url, wait_until="domcontentloaded")
    expect(page.locator("#li-user")).to_be_visible(timeout=DEFAULT_TIMEOUT)
    expect(page.locator("#li-pass")).to_be_visible(timeout=DEFAULT_TIMEOUT)
    expect(page.locator("button:has-text('Sign In')")).to_be_visible(timeout=DEFAULT_TIMEOUT)


def test_invalid_credentials_show_error(page: Page, base_url: str) -> None:
    """Bad credentials must show an inline error message."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#li-user", timeout=DEFAULT_TIMEOUT)
    page.fill("#li-user", "admin")
    page.fill("#li-pass", "wrong-password-xyz")
    page.click("button:has-text('Sign In')")
    # Error message is rendered inside .alert-danger
    expect(page.locator(".alert-danger, .alert.alert-danger")).to_be_visible(
        timeout=DEFAULT_TIMEOUT
    )


def test_empty_credentials_show_error(page: Page, base_url: str) -> None:
    """Submitting with empty username should not navigate away from login."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#li-user", timeout=DEFAULT_TIMEOUT)
    # Leave fields blank and submit
    page.click("button:has-text('Sign In')")
    # Login form must still be visible
    expect(page.locator("#li-user")).to_be_visible(timeout=DEFAULT_TIMEOUT)


def test_successful_login_shows_sidebar(page: Page, base_url: str) -> None:
    """Successful login must show the navigation sidebar."""
    login(page, base_url)
    expect(page.locator("#sidebar")).to_be_visible(timeout=DEFAULT_TIMEOUT)


def test_successful_login_shows_user_name_in_topbar(page: Page, base_url: str) -> None:
    """After login the topbar must display the logged-in user's name."""
    login(page, base_url)
    topbar_user = page.locator("#topbar-user")
    expect(topbar_user).to_be_visible(timeout=DEFAULT_TIMEOUT)
    # The user widget contains the display name or username
    expect(topbar_user.locator(".user-name")).to_contain_text("admin", timeout=DEFAULT_TIMEOUT)


def test_login_hides_login_page(page: Page, base_url: str) -> None:
    """After login the #login-page element must be hidden."""
    login(page, base_url)
    login_page = page.locator("#login-page")
    # Either absent from DOM or hidden
    if login_page.count() > 0:
        expect(login_page).to_be_hidden(timeout=DEFAULT_TIMEOUT)


def test_enter_key_submits_login(page: Page, base_url: str) -> None:
    """Pressing Enter in the password field must submit the login form."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#li-user", timeout=DEFAULT_TIMEOUT)
    page.fill("#li-user", "admin")
    page.fill("#li-pass", "admin")
    page.press("#li-pass", "Enter")
    expect(page.locator("#topbar-user")).to_be_visible(timeout=DEFAULT_TIMEOUT)


# ── Logout ────────────────────────────────────────────────────────────────────


def test_logout_returns_to_login_form(page: Page, base_url: str) -> None:
    """Clicking Sign Out must return the user to the login form."""
    login(page, base_url)
    logout(page)
    expect(page.locator("#li-user")).to_be_visible(timeout=DEFAULT_TIMEOUT)


def test_user_menu_opens_on_click(page: Page, base_url: str) -> None:
    """Clicking the topbar user button must open the dropdown."""
    login(page, base_url)
    page.click("#topbar-user button.user-menu-btn")
    expect(page.locator("#user-dropdown")).to_be_visible(timeout=5_000)


def test_user_menu_contains_sign_out(page: Page, base_url: str) -> None:
    """The user dropdown must contain a Sign Out action."""
    login(page, base_url)
    page.click("#topbar-user button.user-menu-btn")
    expect(page.locator("button:has-text('Sign Out')")).to_be_visible(timeout=5_000)


def test_user_menu_contains_change_password(page: Page, base_url: str) -> None:
    """The user dropdown must contain a Change Password action."""
    login(page, base_url)
    page.click("#topbar-user button.user-menu-btn")
    expect(page.locator("button:has-text('Change Password')")).to_be_visible(timeout=5_000)
