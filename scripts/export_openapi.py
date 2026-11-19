"""Regenerate openapi.yaml from the FastAPI app: python scripts/export_openapi.py"""
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def build_schema() -> dict:
    # Dummy settings: the schema does not depend on real values
    settings = Settings("", "", "", "", "", "", "")
    return create_app(settings=settings, validator=object(), http_client=object()).openapi()


if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parent.parent / "openapi.yaml"
    out.write_text(yaml.safe_dump(build_schema(), sort_keys=False, allow_unicode=True))
    print(f"written {out}")
