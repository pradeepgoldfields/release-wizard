"""UI E2E: Admin panel — users, RBAC, feature toggles, system settings."""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import DEFAULT_TIMEOUT, ApiClient, login, navigate_to

pytestmark = pytest.mark.ui

_TS = int(time.time())


@pytest.fixture(autouse=True)
def authenticated(page: Page, base_url: str) -> None:
    login(page, base_url)


# ── Users panel ───────────────────────────────────────────────────────────────


def test_admin_users_page_renders(page: Page) -> None:
    navigate_to(page, "admin/users")
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)


def test_admin_users_lists_admin_account(page: Page) -> None:
    """The users panel must show the built-in admin account."""
    navigate_to(page, "admin/users")
    page.wait_for_timeout(600)
    expect(page.locator("#content")).to_contain_text("admin", timeout=DEFAULT_TIMEOUT)


def test_admin_users_create_button_present(page: Page) -> None:
    """Users panel must have a button to create a new user."""
    navigate_to(page, "admin/users")
    page.wait_for_timeout(400)
    create_btn = page.locator(
        "button:has-text('New User'), button:has-text('Create User'), "
        "button:has-text('Add User'), button:has-text('Invite')"
    )
    assert create_btn.count() > 0


def test_create_user_via_ui(page: Page, api: ApiClient) -> None:
    """Creating a user through the UI must add them to the list."""
    username = f"uitestuser{_TS}"
    navigate_to(page, "admin/users")
    page.wait_for_timeout(400)

    new_btn = page.locator(
        "button:has-text('New User'), button:has-text('Create User'), "
        "button:has-text('Add User')"
    ).first
    if not new_btn.is_visible():
        pytest.skip("No create-user button found")

    new_btn.click()

    username_input = page.locator(
        "input[placeholder*='username' i], input[id*='username' i], input[name='username']"
    ).first
    expect(username_input).to_be_visible(timeout=DEFAULT_TIMEOUT)
    username_input.fill(username)

    # Email field
    email_input = page.locator(
        "input[type='email'], input[placeholder*='email' i], input[id*='email' i]"
    ).first
    if email_input.is_visible():
        email_input.fill(f"{username}@test.local")

    # Password field
    password_input = page.locator("input[type='password']").first
    if password_input.is_visible():
        password_input.fill("TestPass123!")

    save_btn = page.locator(
        "button:has-text('Save'), button:has-text('Create'), button[type='submit']"
    ).last
    save_btn.click()
    page.wait_for_timeout(600)

    expect(page.locator("#content")).to_contain_text(username, timeout=DEFAULT_TIMEOUT)

    # Cleanup
    users = api.get("/api/v1/users")
    items = users if isinstance(users, list) else users.get("items", [])
    for u in items:
        if u.get("username") == username:
            api.delete(f"/api/v1/users/{u['id']}")
            break


# ── RBAC panel ────────────────────────────────────────────────────────────────


def test_admin_rbac_page_renders(page: Page) -> None:
    navigate_to(page, "admin/rbac")
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)


def test_rbac_page_shows_roles(page: Page) -> None:
    """RBAC panel must list the built-in roles."""
    navigate_to(page, "admin/rbac")
    page.wait_for_timeout(600)
    content = page.locator("#content")
    role_el = content.locator(
        "text=system-administrator, text=product-admin, "
        "text=Role, text=Roles, [class*='role']"
    )
    assert role_el.count() > 0


# ── Feature toggles ───────────────────────────────────────────────────────────


def test_feature_toggles_page_renders(page: Page) -> None:
    navigate_to(page, "admin/toggles")
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)


def test_feature_toggles_page_shows_toggles(page: Page) -> None:
    """Feature toggles panel must list existing toggles."""
    navigate_to(page, "admin/toggles")
    page.wait_for_timeout(600)
    content = page.locator("#content")
    toggle_el = content.locator(
        "[class*='toggle'], input[type='checkbox'], "
        "text=Toggle, text=Feature, text=Enable, text=enable"
    )
    assert toggle_el.count() > 0


def test_feature_toggle_can_be_flipped(page: Page, api: ApiClient) -> None:
    """Clicking a toggle checkbox in the UI must change its enabled state."""
    navigate_to(page, "admin/toggles")
    page.wait_for_timeout(600)
    # Find the first toggle checkbox
    toggle_checkbox = page.locator(
        "input[type='checkbox'], [class*='toggle-switch'], [role='switch']"
    ).first
    if not toggle_checkbox.is_visible():
        pytest.skip("No toggle checkbox visible")

    initial_checked = toggle_checkbox.is_checked()
    toggle_checkbox.click()
    page.wait_for_timeout(400)
    new_checked = toggle_checkbox.is_checked()
    assert new_checked != initial_checked, "Toggle state did not change after click"
    # Restore
    toggle_checkbox.click()


# ── Global variables ──────────────────────────────────────────────────────────


def test_global_variables_page_renders(page: Page) -> None:
    navigate_to(page, "admin/variables")
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)


# ── System settings ───────────────────────────────────────────────────────────


def test_system_settings_page_renders(page: Page) -> None:
    navigate_to(page, "admin/system")
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)
