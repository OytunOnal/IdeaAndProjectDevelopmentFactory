from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


def get_template(category: str, filename: str) -> str:
    """Load a Jinja2 template for a project category."""
    template_path = TEMPLATES_DIR / category / filename
    if template_path.exists():
        return template_path.read_text()
    return ""


def list_categories() -> list[str]:
    """List available project categories."""
    if TEMPLATES_DIR.exists():
        return [d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir()]
    return []
