"""Discover: route discovery for webapp-autotest."""
from .models import DiscoveredRoute, Form, FormField, SiteMap, Priority, RouteType, RouteMethod
from .tech_stack_detector import detect_tech_stack, get_route_source_dir, TechStack
from .static_analyzer import (
    analyze_nextjs_pages,
    analyze_nextjs_api,
    analyze_django_urls,
    analyze_rails_routes,
)
from .sitemap_parser import parse_sitemap
from .crawler import crawl_site

__all__ = [
    "DiscoveredRoute",
    "Form",
    "FormField",
    "SiteMap",
    "Priority",
    "RouteType",
    "RouteMethod",
    "TechStack",
    "detect_tech_stack",
    "get_route_source_dir",
    "analyze_nextjs_pages",
    "analyze_nextjs_api",
    "analyze_django_urls",
    "analyze_rails_routes",
    "parse_sitemap",
    "crawl_site",
]
