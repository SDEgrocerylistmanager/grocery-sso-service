import json
import pathlib

import yaml

from scripts.export_openapi import build_schema


def test_openapi_file_is_up_to_date():
    # Fails if the API changed but openapi.yaml was not regenerated
    path = pathlib.Path(__file__).resolve().parent.parent / "openapi.yaml"
    committed = yaml.safe_load(path.read_text())
    assert json.loads(json.dumps(build_schema())) == committed
