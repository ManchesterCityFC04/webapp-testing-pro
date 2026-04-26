"""Shared data models for route discovery."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class RouteType(Enum):
    PAGE = "page"
    API = "api"
    STATIC = "static"
    REDIRECT = "redirect"


class RouteMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class Priority(Enum):
    CRITICAL = 1
    STANDARD = 2
    EDGE = 3


@dataclass
class FormField:
    name: str
    field_type: str
    id_attr: str = ""
    required: bool = False
    tag: str = "input"


@dataclass
class Form:
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class DiscoveredRoute:
    url: str
    route_type: RouteType = RouteType.PAGE
    method: RouteMethod = RouteMethod.GET
    discovered_via: str = ""
    forms: list[Form] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    params: list[str] = field(default_factory=list)
    auth_required: bool = False
    priority: Priority = Priority.STANDARD
    status_code: int = 200
    error: str | None = None
    labels: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    depth: int = 0

    @property
    def is_page(self) -> bool:
        return self.route_type == RouteType.PAGE

    @property
    def has_forms(self) -> bool:
        return len(self.forms) > 0


@dataclass
class SiteMap:
    base_url: str
    routes: list[DiscoveredRoute] = field(default_factory=list)
    crawl_depth: int = 3
    discovery_strategies_used: list[str] = field(default_factory=list)

    @property
    def pages(self) -> list[DiscoveredRoute]:
        return [r for r in self.routes if r.route_type == RouteType.PAGE]

    @property
    def apis(self) -> list[DiscoveredRoute]:
        return [r for r in self.routes if r.route_type == RouteType.API]

    @property
    def coverage_stats(self) -> dict:
        total = len(self.routes)
        tested = sum(1 for r in self.routes if r.labels)
        return {
            "total": total,
            "pages": len(self.pages),
            "apis": len(self.apis),
            "coverage_pct": round(tested / total * 100, 1) if total else 0,
        }

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "crawl_depth": self.crawl_depth,
            "discovery_strategies_used": self.discovery_strategies_used,
            "routes": [
                {
                    "url": r.url,
                    "route_type": r.route_type.value,
                    "method": r.method.value,
                    "discovered_via": r.discovered_via,
                    "forms": [
                        {
                            "action": f.action,
                            "method": f.method,
                            "fields": [
                                {"name": ff.name, "type": ff.field_type, "required": ff.required}
                                for ff in f.fields
                            ],
                        }
                        for f in r.forms
                    ],
                    "params": r.params,
                    "auth_required": r.auth_required,
                    "priority": r.priority.value,
                }
                for r in self.routes
            ],
            "coverage_stats": self.coverage_stats,
        }
