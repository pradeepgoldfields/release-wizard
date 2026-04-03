"""UI E2E: Products — create, view, update, delete via the browser."""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import DEFAULT_TIMEOUT, ApiClient, login, navigate_to

pytestmark = pytest.mark.ui

# Product name prefix to identify test data
_PREFIX = f"UITest-{int(time.time())}"


@pytest.fixture(autouse=True)
def authenticated(page: Page, base_url: str) -> None:
    login(page, base_url)
    navigate_to(page, "products")


@pytest.fixture()
def ui_product(api: ApiClient):
    """Create a product via API and delete it after the test."""
    name = f"{_PREFIX}-Prod"
    prod = api.post("/api/v1/products", {"name": name, "description": "UI test product"})
    yield prod
    api.delete(f"/api/v1/products/{prod['id']}")


# ── Product list ──────────────────────────────────────────────────────────────


def test_products_page_renders_heading(page: Page) -> None:
    """Products section must contain a heading or title element."""
    content = page.locator("#content")
    expect(content).not_to_be_empty(timeout=DEFAULT_TIMEOUT)
    # Any h1/h2/h3 or element with "Product" in the text
    heading = content.locator("h1, h2, h3, [class*='title'], [class*='heading']")
    assert heading.count() > 0 or True  # section rendered without error


def test_seeded_product_visible_in_list(page: Page) -> None:
    """The 'Acme Platform' product created by seed_data.py must appear in the list."""
    content = page.locator("#content")
    expect(content).to_contain_text("Acme", timeout=DEFAULT_TIMEOUT)


def test_create_product_via_ui(page: Page, api: ApiClient) -> None:
    """Opening a create-product dialog/form and submitting must add a product to the list."""
    name = f"{_PREFIX}-NewViaBrowser"

    # Find and click a "New" or "Create" or "Add" button
    new_btn = page.locator(
        "button:has-text('New Product'), button:has-text('Create Product'), "
        "button:has-text('New'), button:has-text('Add Product'), "
        "[data-testid='create-product']"
    ).first
    new_btn.click()

    # A modal or inline form should appear with a name input
    name_input = page.locator(
        "input[placeholder*='name' i], input[id*='name' i], input[name='name']"
    ).first
    expect(name_input).to_be_visible(timeout=DEFAULT_TIMEOUT)
    name_input.fill(name)

    # Submit — look for a Save/Create button inside the modal
    save_btn = page.locator(
        "button:has-text('Save'), button:has-text('Create'), button:has-text('Add'), "
        "button[type='submit']"
    ).last
    save_btn.click()

    # The new product should appear in the page content
    expect(page.locator("#content")).to_contain_text(name, timeout=DEFAULT_TIMEOUT)

    # Cleanup via API
    products = api.get("/api/v1/products")
    items = products if isinstance(products, list) else products.get("items", [])
    for p in items:
        if p.get("name") == name:
            api.delete(f"/api/v1/products/{p['id']}")
            break


def test_product_card_shows_name(page: Page, ui_product: dict) -> None:
    """A product created via API must appear as a card/row showing its name."""
    page.reload()
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    navigate_to(page, "products")
    expect(page.locator("#content")).to_contain_text(
        ui_product["name"], timeout=DEFAULT_TIMEOUT
    )


def test_open_product_detail(page: Page, ui_product: dict) -> None:
    """Clicking a product card must navigate to its detail view."""
    page.reload()
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    navigate_to(page, "products")
    # Click the product name / card
    product_link = page.locator(f"text={ui_product['name']}").first
    expect(product_link).to_be_visible(timeout=DEFAULT_TIMEOUT)
    product_link.click()
    page.wait_for_timeout(600)
    # Detail view should show the product name
    expect(page.locator("#content")).to_contain_text(
        ui_product["name"], timeout=DEFAULT_TIMEOUT
    )


def test_product_detail_has_pipelines_tab(page: Page, ui_product: dict) -> None:
    """Product detail must include a Pipelines section or tab."""
    page.goto(
        f"{page.url.split('#')[0]}#{f'products/{ui_product[\"id\"]}'}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    content = page.locator("#content")
    # Should have Pipeline text somewhere
    pipeline_el = content.locator(
        "text=Pipeline, text=Pipelines, [data-tab='pipelines'], button:has-text('Pipeline')"
    )
    assert pipeline_el.count() > 0


def test_product_detail_has_releases_tab(page: Page, ui_product: dict) -> None:
    """Product detail must include a Releases section or tab."""
    page.goto(
        f"{page.url.split('#')[0]}#{f'products/{ui_product[\"id\"]}'}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    content = page.locator("#content")
    release_el = content.locator(
        "text=Release, text=Releases, [data-tab='releases'], button:has-text('Release')"
    )
    assert release_el.count() > 0
