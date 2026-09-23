import json
import os.path
from datetime import UTC, datetime

__doc__ = "Generates Package Control registry file for builded package"


def read_file(file: str) -> str:
    dirname = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(dirname, file), encoding="utf8") as f:
        return f.read(None)


version = read_file("../VERSION").strip()
now = datetime.now(UTC)

registry = {
    "schema_version": "3.0.0",
    "packages": [
        {
            "name": "Emmet",
            "details": "https://github.com/emmetio/sublime-text-plugin",
            "labels": ["auto-complete", "snippets", "text manipulation"],
            "donate": "https://github.com/sponsors/emmetio",
            "releases": [
                {
                    "version": version,
                    "url": f"https://emmetio.github.io/sublime-text-plugin/{version}/Emmet.sublime-package",
                    "date": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "sublime_text": ">=3000",
                }
            ],
        }
    ],
}

print(json.dumps(registry, indent=True))
