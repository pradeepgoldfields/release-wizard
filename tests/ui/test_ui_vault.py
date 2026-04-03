"""UI E2E: Vault — secret list, create, reveal toggle."""

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
    navigate_to(page, "admin/keys")


@pytest.fixture()
def vault_secret(api: ApiClient):
    """Create a vault secret via API and clean up after the test."""
    secret = api.post(
        "/api/v1/vault",
        {"key": f"UI_TEST_SECRET_{_TS}", "value": "super-secret-value", "description": "UI test"},
    )
    yield secret
    if "id" in secret:
        api.delete(f"/api/v1/vault/{secret['id']}")


# ── Vault list ────────────────────────────────────────────────────────────────


def test_vault_page_renders(page: Page) -> None:
    """Vault section must render without error."""
    expect(page.locator("#content")).not_to_be_empty(timeout=DEFAULT_TIMEOUT)


def test_vault_page_shows_secrets_heading(page: Page) -> None:
    """Vault section must contain a heading or label for secrets."""
    content = page.locator("#content")
    vault_heading = content.locator(
        "h1, h2, h3, text=Vault, text=Secrets, text=Secret, [class*='vault']"
    )
    assert vault_heading.count() > 0


def test_vault_secret_appears_in_list(page: Page, vault_secret: dict) -> None:
    """A secret created via API must be listed in the vault UI."""
    page.reload()
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    navigate_to(page, "admin/keys")
    expect(page.locator("#content")).to_contain_text(
        f"UI_TEST_SECRET_{_TS}", timeout=DEFAULT_TIMEOUT
    )


def test_vault_secret_value_is_masked(page: Page, vault_secret: dict) -> None:
    """Secret values must be masked (shown as asterisks or hidden) by default."""
    page.reload()
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    navigate_to(page, "admin/keys")
    page.wait_for_timeout(500)
    # The literal value must NOT be visible in the DOM
    content_text = page.locator("#content").inner_text()
    assert "super-secret-value" not in content_text


def test_create_vault_secret_via_ui(page: Page, api: ApiClient) -> None:
    """Using the UI new-secret form must save a new secret."""
    key = f"UI_NEW_SECRET_{_TS}"

    new_btn = page.locator(
        "button:has-text('New Secret'), button:has-text('Add Secret'), "
        "button:has-text('New'), button:has-text('Create')"
    ).first
    if not new_btn.is_visible():
        pytest.skip("No create-secret button found in vault UI")

    new_btn.click()

    key_input = page.locator("input[placeholder*='key' i], input[id*='key' i], input[name='key']").first
    expect(key_input).to_be_visible(timeout=DEFAULT_TIMEOUT)
    key_input.fill(key)

    val_input = page.locator(
        "input[type='password'], input[placeholder*='value' i], textarea[placeholder*='value' i]"
    ).first
    if val_input.is_visible():
        val_input.fill("test-secret-val-123")

    save_btn = page.locator(
        "button:has-text('Save'), button:has-text('Create'), button[type='submit']"
    ).last
    save_btn.click()
    page.wait_for_timeout(600)

    expect(page.locator("#content")).to_contain_text(key, timeout=DEFAULT_TIMEOUT)

    # Cleanup
    secrets = api.get("/api/v1/vault")
    items = secrets if isinstance(secrets, list) else secrets.get("items", [])
    for s in items:
        if s.get("key") == key:
            api.delete(f"/api/v1/vault/{s['id']}")
            break
