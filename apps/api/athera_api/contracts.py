"""تصدير عقد OpenAPI | Export the OpenAPI contract (§50).

`make openapi` يكتبه إلى packages/contracts/openapi.json ليولَّد منه عميل
TypeScript — مصدر واحد للحقيقة بين الطرفين.
"""
import json
import sys

from .main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
