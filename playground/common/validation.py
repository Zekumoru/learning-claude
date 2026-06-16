import json
import ast
import re


def validate_json(text: str) -> float:
    try:
        json.loads(text.strip())
        return 10
    except json.JSONDecodeError:
        return 0


def validate_python(text: str) -> float:
    try:
        ast.parse(text.strip())
        return 10
    except:
        return 0


def validate_regex(text: str) -> float:
    try:
        re.compile(text.strip())
        return 10
    except re.error:
        return 0
