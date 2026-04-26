"""Auto-detect project tech stack from file patterns."""
import os
from pathlib import Path
from typing import Literal

TechStack = Literal["nextjs", "rails", "django", "laravel", "plain"] | None

STACK_PATTERNS = {
    "nextjs": {
        "indicator_files": ["next.config.ts", "next.config.js", "package.json"],
        "route_indicator": ["src/app", "app"],
        "config_check": lambda root: (
            Path(root, "src/app").exists() or Path(root, "app").exists()
        ) and (
            Path(root, "package.json").exists()
            and "next" in Path(root, "package.json").read_text(errors="ignore").lower()
        ),
    },
    "rails": {
        "indicator_files": ["config/routes.rb", "Gemfile"],
        "route_indicator": ["config/routes.rb"],
        "config_check": lambda root: Path(root, "config/routes.rb").exists(),
    },
    "django": {
        "indicator_files": ["manage.py", "urls.py"],
        "route_indicator": ["urls.py"],
        "config_check": lambda root: Path(root, "manage.py").exists(),
    },
    "laravel": {
        "indicator_files": ["artisan", "composer.json", "routes/web.php"],
        "route_indicator": ["routes/web.php"],
        "config_check": lambda root: (
            Path(root, "artisan").exists()
            and Path(root, "routes/web.php").exists()
        ),
    },
}


def detect_tech_stack(project_root: str) -> TechStack:
    """Detect the tech stack from project root directory."""
    for name, pattern in STACK_PATTERNS.items():
        if pattern["config_check"](project_root):
            return name  # type: ignore
    return "plain"


def get_route_source_dir(project_root: str, stack: TechStack) -> str | None:
    """Return the directory containing route definitions for the detected stack."""
    if stack == "nextjs":
        if Path(project_root, "src/app").exists():
            return str(Path(project_root, "src/app"))
        if Path(project_root, "app").exists():
            return str(Path(project_root, "app"))
    elif stack == "rails":
        return str(Path(project_root, "config"))
    elif stack == "django":
        return str(Path(project_root))  # urls.py can be anywhere under root
    elif stack == "laravel":
        return str(Path(project_root, "routes"))
    return None
