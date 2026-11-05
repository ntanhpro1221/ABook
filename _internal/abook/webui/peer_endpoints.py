"""Android build endpoints, shared with Gradle and Kotlin from one packaged JSON asset."""
import json
from pathlib import Path

ENDPOINTS = json.loads((Path(__file__).with_name("assets") / "peer_endpoints.json").read_text(encoding="utf-8"))
RELEASE = ENDPOINTS["release"]
DEBUG = ENDPOINTS["debug"]
