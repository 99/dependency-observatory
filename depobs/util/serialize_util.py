import itertools
import json
import logging
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Optional,
    Sequence,
    Union,
)

log = logging.getLogger(__name__)

JSONPathElement = Union[int, str]
JSONPath = Sequence[JSONPathElement]


def get_in(d: Dict, path: Iterable[JSONPathElement], default: Any = None):
    sentinel = object()
    for path_part in path:
        if isinstance(path_part, str):
            if not hasattr(d, "get"):
                return default
            assert hasattr(d, "get")
            d = d.get(path_part, sentinel)
            if d == sentinel:
                return default
        elif isinstance(path_part, int):
            if not hasattr(d, "__getitem__"):
                return default
            assert hasattr(d, "__getitem__")
            if not (-1 < path_part < len(d)):
                return default
            d = d[path_part]
        else:
            raise NotImplementedError()
    return d


def extract_fields(d: Dict, fields: Iterable[str]) -> Dict:
    "returns a new dict with top-level param fields extracted from param d"
    return {field: d.get(field) for field in fields}


def extract_nested_fields(d: Dict, fields: Dict[str, JSONPath]) -> Dict:
    return {field: get_in(d, path, None) for field, path in fields.items()}


def iter_jsonlines(
    f: Sequence,
) -> Generator[Union[Dict, Sequence, int, str, None], None, None]:
    "Generator over JSON lines http://jsonlines.org/ files with extension .jsonl"
    for line in f:
        yield json.loads(line)


def grouper(iterable: Iterable[Any], n: int, fillvalue: Any = None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    # from https://docs.python.org/3/library/itertools.html#itertools-recipes
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def parse_stdout_as_json(stdout: Optional[str]) -> Optional[Dict]:
    if stdout is None:
        return None

    try:
        parsed_stdout = json.loads(stdout)
        return parsed_stdout
    except json.decoder.JSONDecodeError as e:
        log.warning(f"error parsing stdout as JSON: {e}")

    return None


def parse_stdout_as_jsonlines(stdout: Optional[str]) -> Optional[Sequence[Dict]]:
    if stdout is None:
        return None

    try:
        return list(
            line
            for line in iter_jsonlines(stdout.split("\n"))
            if isinstance(line, dict)
        )
    except json.decoder.JSONDecodeError as e:
        log.warning(f"error parsing stdout as JSON: {e}")

    return None
