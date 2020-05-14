from io import BytesIO
from pathlib import Path
from typing import List

from diff_match_patch import diff_match_patch
from PIL import Image
from pixelmatch.contrib.PIL import pixelmatch


def compare_images(actual: bytes, expected: bytes):
    expected = Image.open(BytesIO(expected))
    actual = Image.open(BytesIO(actual))
    output = Image.new('RGBA', expected.size)
    res = {}
    if expected.size != actual.size:
        res['error'] = f'Sizes differ: expected {"x".join(map(str, expected.size))}, got {"x".join(map(str, actual.size))}'
        return res
    mismatch = pixelmatch(expected, actual, expected, threshold=0.1)
    if mismatch > 0:
        res['diff'] = output.tobytes()

    return res


def compare_text(actual: str, expected: str):
    res = {}
    if not isinstance(actual, str):
        res['error'] = 'Actual result should be a string'

    if expected == actual:
        return

    diff = diff_match_path()
    res = diff.diff_main(expected, actual)
    diff.diff_cleanupSemantic(res)
    html = diff.diff_prettyHTML(res)
    html = f'<link rel="stylesheet" href="{(Path(__file__).parent / "diffstyle.css").as_uri()}">{html}'
    res['diff'] = html
    res['diffExtension'] = '.html'


golden_comparators = {
    'image/png': compare_images,
    'image/jpeg': compare_images,
    'text/plain': compare_text,
}
