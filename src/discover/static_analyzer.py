"""Static analysis of route definitions for known tech stacks."""
import re
from pathlib import Path
from typing import Optional

from .models import DiscoveredRoute, Priority, RouteMethod, RouteType, SiteMap


def analyze_nextjs_pages(app_dir: str, base_url: str = "http://localhost:3000") -> list[DiscoveredRoute]:
    """Recursively read all Next.js App Router page.tsx files → URLs."""
    routes = []
    app_path = Path(app_dir)

    if not app_path.exists():
        return routes

    for page_path in app_path.rglob("page.tsx"):
        rel = page_path.relative_to(app_path)
        parts = list(rel.parts[:-1])  # drop page.tsx

        # Skip layout groups (auth), api routes (separate handler)
        if any(p.startswith("[") for p in parts):
            url_path = "/" + "/".join(parts)
        elif parts == []:
            url_path = "/"
        else:
            # Skip (auth) style groups
            clean_parts = [p for p in parts if not (p.startswith("(") and p.endswith(")"))]
            url_path = "/" + "/".join(clean_parts)

        params = [
            p[1:-1]
            for p in parts
            if p.startswith("[") and p.endswith("]")
        ]

        # Determine priority heuristically from URL segments
        priority = _priority_from_url(url_path)

        routes.append(
            DiscoveredRoute(
                url=f"{base_url}{url_path}",
                route_type=RouteType.PAGE,
                discovered_via="static_nextjs",
                params=params,
                priority=priority,
            )
        )

    return routes


def analyze_nextjs_api(api_dir: str, base_url: str = "http://localhost:3000") -> list[DiscoveredRoute]:
    """Read all Next.js API route handlers (src/app/api/**/route.ts)."""
    routes = []
    api_path = Path(api_dir)

    if not api_path.exists():
        return routes

    for route_path in api_path.rglob("route.ts"):
        rel = route_path.relative_to(api_path)
        parts = list(rel.parts[:-1])  # remove route.ts
        path = "/" + "/".join(parts)

        content = route_path.read_text(errors="ignore")
        methods = []
        for m in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            if f'"{m}"' in content or f"'{m}'" in content or f"RequestMethod.{m}" in content:
                methods.append(m)

        routes.append(
            DiscoveredRoute(
                url=f"{base_url}{path}",
                route_type=RouteType.API,
                method=RouteMethod(methods[0]) if methods else RouteMethod.GET,
                discovered_via="static_api_nextjs",
            )
        )

    return routes


def analyze_django_urls(project_root: str, base_url: str = "http://localhost:8000") -> list[DiscoveredRoute]:
    """Parse Django urls.py files for URL patterns."""
    routes = []
    for urls_py in Path(project_root).rglob("urls.py"):
        content = urls_py.read_text(errors="ignore")
        # Match path('', views.index) and path('admin/', ...)
        for match in re.finditer(r"path\(\s*['\"]([^'\"]*)['\"]", content):
            path = match.group(1)
            routes.append(
                DiscoveredRoute(
                    url=f"{base_url}/{path}",
                    route_type=RouteType.PAGE,
                    discovered_via="static_django",
                    priority=Priority.STANDARD,
                )
            )
    return routes


def analyze_rails_routes(routes_file: str, base_url: str = "http://localhost:3000") -> list[DiscoveredRoute]:
    """Parse Rails routes.rb for route definitions."""
    routes = []
    rb_path = Path(routes_file)

    if not rb_path.exists():
        return routes

    content = rb_path.read_text(errors="ignore")

    # Match resources :posts, resource :account, get 'about'
    for match in re.finditer(
        r"(?:resources|resource|get|post|put|patch|delete)\s+[:'\"](\w+)",
        content,
    ):
        name = match.group(1)
        for action in ["index", "show", "new", "edit", "create", "update", "destroy"]:
            routes.append(
                DiscoveredRoute(
                    url=f"{base_url}/{name}",
                    route_type=RouteType.PAGE,
                    discovered_via="static_rails",
                    priority=_priority_from_url(f"/{name}"),
                )
            )
    return routes


def _priority_from_url(url: str) -> Priority:
    """Heuristic: assign priority based on URL keywords."""
    critical_keywords = ["login", "auth", "dashboard", "statistics", "incidents", "reports", "admin"]
    edge_keywords = ["detail", "[id]", "[pk]", "edit", "setting", "config"]

    url_lower = url.lower()
    if any(kw in url_lower for kw in critical_keywords):
        return Priority.CRITICAL
    if any(kw in url_lower for kw in edge_keywords):
        return Priority.EDGE
    return Priority.STANDARD
