import difflib
import io
from difflib import restore
from difflib import unified_diff


def generate_diff(original: str, updated: str) -> str:
    original_lines = original.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)
    return ''.join(difflib.ndiff(original_lines, updated_lines))  # ✅ COMPATIBLE

def apply_diff(original: str, diff_text: str) -> str:
    diff_lines = diff_text.splitlines(keepends=True)
    return ''.join(difflib.restore(diff_lines, which=1))  # ✅ works with ndiff

