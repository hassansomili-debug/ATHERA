"""AT-S0-10 — لا أسرار في المستودع (§36.1)."""
import pathlib
import re
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\."),
]

SKIP_FILES = {"athera.txt"}
BINARY_SUFFIXES = {".png", ".jpg", ".pdf", ".docx", ".ico", ".woff2"}


def _tracked_files() -> list[pathlib.Path]:
    """الملفات المتعقَّبة في git وحدها.

    الاختبار اسمه «committed»، فيجب أن يعني ذلك. المسح على نظام الملفات كان
    يلتقط ملفات محلية غير متعقَّبة ومُتجاهَلة — `apps/web/.env.local` مثلًا —
    فيفشل عند كل مطوّر لديه بيئة محلية، بينما المستودع نظيف تمامًا.

    وإنذار كاذب متكرر أسوأ من فحص غائب: يُعلِّم المطوّر تجاهل الحارس.

    والاشتقاق من `git ls-files` يحترم `.gitignore` بحكم تعريفه، ولا يضعف
    الكشف: الأنماط نفسها على كل ملف يمكن أن يصل إلى المستودع فعلًا.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, check=True, text=True,
    )
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


def test_no_secret_material_committed():
    offenders = []
    for path in _tracked_files():
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if path.suffix in BINARY_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)} :: {pattern.pattern}")
    assert not offenders, "secret material found in the repository:\n" + "\n".join(offenders)


def test_env_example_contains_no_real_values():
    example = REPO_ROOT / ".env.example"
    text = example.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=\n" in text or "OPENAI_API_KEY=" in text
    assert "sk-" not in text
    # المزود الافتراضي في Sprint 0 هو null — لا استدعاء إنتاجي.
    assert "MODEL_PROVIDER=null" in text


def test_gitignore_blocks_env_files():
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignored and "!.env.example" in ignored
