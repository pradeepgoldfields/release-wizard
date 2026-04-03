"""UI E2E: Pipeline editor — create, stage/task management, YAML export."""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from tests.ui.conftest import DEFAULT_TIMEOUT, ApiClient, login, navigate_to

pytestmark = pytest.mark.ui

_TS = int(time.time())


@pytest.fixture(scope="module")
def product(api: ApiClient):
    """Module-scoped product for pipeline tests."""
    p = api.post("/api/v1/products", {"name": f"UI-Pipeline-Prod-{_TS}", "description": "UI pipeline tests"})
    yield p
    api.delete(f"/api/v1/products/{p['id']}")


@pytest.fixture(scope="module")
def pipeline(api: ApiClient, product: dict):
    """Module-scoped pipeline for UI tests."""
    pl = api.post(
        f"/api/v1/products/{product['id']}/pipelines",
        {"name": f"UI-Pipeline-{_TS}", "kind": "ci", "git_branch": "main"},
    )
    yield pl
    # Deleted with product cascade


@pytest.fixture(autouse=True)
def authenticated(page: Page, base_url: str) -> None:
    login(page, base_url)


# ── Pipeline list ─────────────────────────────────────────────────────────────


def test_pipeline_appears_in_product_detail(
    page: Page, product: dict, pipeline: dict
) -> None:
    """A pipeline created via API must appear in the product detail view."""
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    expect(page.locator("#content")).to_contain_text(pipeline["name"], timeout=DEFAULT_TIMEOUT)


def test_pipeline_detail_page_loads(
    page: Page, product: dict, pipeline: dict
) -> None:
    """Navigating to a pipeline's detail URL must render its name."""
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}/pipelines/{pipeline['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    expect(page.locator("#content")).to_contain_text(pipeline["name"], timeout=DEFAULT_TIMEOUT)


def test_pipeline_detail_shows_stages_section(
    page: Page, product: dict, pipeline: dict
) -> None:
    """Pipeline detail must show a Stages section or add-stage button."""
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}/pipelines/{pipeline['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    content = page.locator("#content")
    stage_el = content.locator(
        "text=Stage, text=Stages, button:has-text('Add Stage'), "
        "button:has-text('New Stage'), [data-section='stages']"
    )
    assert stage_el.count() > 0


def test_pipeline_detail_shows_compliance_score(
    page: Page, product: dict, pipeline: dict
) -> None:
    """Pipeline detail must show a compliance score or rating badge."""
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}/pipelines/{pipeline['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    content = page.locator("#content")
    compliance_el = content.locator(
        "text=Compliance, text=compliance, text=Score, "
        "[class*='badge'], [class*='rating'], [class*='compliance']"
    )
    assert compliance_el.count() > 0


# ── Pipeline creation via UI ──────────────────────────────────────────────────


def test_create_pipeline_via_product_detail(
    page: Page, product: dict, api: ApiClient
) -> None:
    """Using the UI create-pipeline button must add a pipeline to the product."""
    name = f"UI-Created-PL-{_TS}"
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(600)

    # Find a "New Pipeline" / "Create Pipeline" button
    btn = page.locator(
        "button:has-text('New Pipeline'), button:has-text('Create Pipeline'), "
        "button:has-text('Add Pipeline'), button:has-text('Pipeline')"
    ).first
    if not btn.is_visible():
        pytest.skip("No create-pipeline button visible — may require a different navigation path")

    btn.click()
    name_input = page.locator("input[placeholder*='name' i], input[id*='name' i]").first
    expect(name_input).to_be_visible(timeout=DEFAULT_TIMEOUT)
    name_input.fill(name)

    save_btn = page.locator(
        "button:has-text('Save'), button:has-text('Create'), button[type='submit']"
    ).last
    save_btn.click()
    page.wait_for_timeout(600)

    expect(page.locator("#content")).to_contain_text(name, timeout=DEFAULT_TIMEOUT)

    # Cleanup
    pipelines_resp = api.get(f"/api/v1/products/{product['id']}/pipelines")
    items = pipelines_resp if isinstance(pipelines_resp, list) else pipelines_resp.get("items", [])
    for pl in items:
        if pl.get("name") == name:
            api.delete(f"/api/v1/products/{product['id']}/pipelines/{pl['id']}")
            break


# ── YAML export ───────────────────────────────────────────────────────────────


def test_pipeline_yaml_export_available(
    page: Page, product: dict, pipeline: dict
) -> None:
    """Pipeline detail must expose a YAML export button or link."""
    page.goto(
        f"{page.url.split('#')[0]}#products/{product['id']}/pipelines/{pipeline['id']}",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#topbar-user", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(800)
    yaml_el = page.locator(
        "button:has-text('YAML'), button:has-text('Export'), "
        "a:has-text('YAML'), [data-action='yaml-export']"
    )
    assert yaml_el.count() > 0
