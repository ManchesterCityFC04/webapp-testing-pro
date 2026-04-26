"""Playwright-based site crawler for route and form discovery."""
from playwright.sync_api import sync_playwright, Page, Response
from urllib.parse import urljoin, urlparse
from typing import Optional

from .models import DiscoveredRoute, Form, FormField, RouteType, SiteMap


def crawl_site(
    base_url: str,
    max_depth: int = 3,
    max_pages: int = 200,
    auth_credentials: Optional[dict] = None,
    login_url: Optional[str] = None,
    storage_state_path: Optional[str] = None,
) -> SiteMap:
    """
    Playwright crawler: starts from base_url, extracts all hrefs/forms,
    recursively visits internal links up to max_depth.
    Returns a SiteMap with all discovered routes + forms.
    """
    visited: set[str] = set()
    pending: list[tuple[str, int]] = [(base_url, 0)]
    routes: list[DiscoveredRoute] = []
    strategies_used: list[str] = ["playwright_crawl"]

    context_options = {
        "java_script_enabled": True,
        "ignore_https_errors": True,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        if storage_state_path:
            try:
                context = browser.new_context(storage_state=storage_state_path)
            except Exception:
                context = browser.new_context(**context_options)
        else:
            context = browser.new_context(**context_options)

        page = context.new_page()

        # Auth flow: navigate to login if credentials provided
        if auth_credentials and login_url:
            _do_login(page, base_url + login_url, auth_credentials)

        page.close()

        # Crawl with authenticated context
        context = browser.new_context(
            storage_state=context.storage_state() if storage_state_path else None,
            **context_options,
        )

        while pending:
            if len(visited) >= max_pages:
                break

            url, depth = pending.pop()
            normalized = _normalize_url(url)
            if normalized in visited or depth > max_depth:
                continue

            visited.add(normalized)
            page = context.new_page()

            try:
                resp = page.goto(url, wait_until="networkidle", timeout=20000)

                if resp and resp.status in (301, 302, 307, 308):
                    redirect_url = resp.headers.get("location", "")
                    routes.append(
                        DiscoveredRoute(
                            url=url,
                            route_type=RouteType.REDIRECT,
                            discovered_via="playwright_crawl",
                            status_code=resp.status,
                        )
                    )
                    if redirect_url:
                        pending.append((urljoin(url, redirect_url), depth + 1))
                    page.close()
                    continue

                forms = _extract_forms(page)
                links = _extract_internal_links(page, base_url)

                content_type = ""
                if resp:
                    content_type = resp.headers.get("content-type", "")

                route_type = RouteType.PAGE if "text/html" in content_type else RouteType.API

                routes.append(
                    DiscoveredRoute(
                        url=url,
                        route_type=route_type,
                        discovered_via="playwright_crawl",
                        status_code=resp.status if resp else 0,
                        forms=forms,
                        links=links,
                        depth=depth,
                    )
                )

                for link in links:
                    normalized_link = _normalize_url(link)
                    if normalized_link not in visited:
                        pending.append((link, depth + 1))

            except Exception as e:
                routes.append(
                    DiscoveredRoute(
                        url=url,
                        route_type=RouteType.PAGE,
                        discovered_via="playwright_crawl",
                        error=str(e),
                    )
                )
            finally:
                page.close()

        browser.close()

    return SiteMap(
        base_url=base_url,
        routes=routes,
        crawl_depth=max_depth,
        discovery_strategies_used=strategies_used,
    )


def _do_login(page: Page, login_url: str, credentials: dict) -> None:
    """Perform login to capture authenticated session state."""
    try:
        page.goto(login_url, wait_until="networkidle", timeout=15000)
        username_sel = credentials.get("username_field", "input[type='text'], input[name='username']")
        password_sel = credentials.get("password_field", "input[type='password']")
        submit_sel = credentials.get("submit_button", "button[type='submit']")

        page.fill(username_sel, credentials.get("username", ""))
        page.fill(password_sel, credentials.get("password", ""))
        page.click(submit_sel)
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # Login may fail for various reasons; continue without auth


def _extract_forms(page: Page) -> list[Form]:
    """Extract all forms with method, action, and field metadata."""
    forms = []
    for form_el in page.query_selector_all("form"):
        fields = []
        for input_el in form_el.query_selector_all("input, select, textarea"):
            fields.append(
                FormField(
                    name=input_el.get_attribute("name") or "",
                    field_type=input_el.get_attribute("type") or "text",
                    id_attr=input_el.get_attribute("id") or "",
                    required=input_el.get_attribute("required") is not None,
                    tag=input_el.evaluate("el => el.tagName"),
                )
            )
        forms.append(
            Form(
                action=form_el.get_attribute("action") or "",
                method=form_el.get_attribute("method") or "get",
                fields=fields,
            )
        )
    return forms


def _extract_internal_links(page: Page, base_url: str) -> list[str]:
    """Extract all same-origin hrefs from a page."""
    links: set[str] = set()
    parsed_base = urlparse(base_url)

    for anchor in page.query_selector_all("a[href]"):
        href = anchor.get_attribute("href") or ""
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc == parsed_base.netloc:
            normalized = _normalize_url(full_url)
            if normalized:
                links.add(normalized)

    return list(links)


def _normalize_url(url: str) -> str:
    """Normalize URL: remove fragment, trailing slash."""
    if not url:
        return ""
    url = url.split("#")[0]
    url = url.rstrip("/")
    return url or "/"
