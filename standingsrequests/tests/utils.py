import json
from typing import Set

from django.core.cache import cache
from django.db.models import QuerySet
from django.http import JsonResponse
from django.test import TestCase

from app_utils.testing import response_text


class TestCaseWithClearCache(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache.clear()


def extract(qs: QuerySet, field: str) -> Set[int]:
    """Return the extracted fields from the items of a query set."""
    return set(qs.values_list(field, flat=True))


def _json_response_to_python_2(response: JsonResponse, data_key="data") -> object:
    """Convert JSON response into Python object."""
    data = json.loads(response_text(response))
    return data[data_key]


def json_response_to_dict_2(response: JsonResponse, key="id", data_key="data") -> dict:
    """Convert JSON response into dict by given key."""
    return {x[key]: x for x in _json_response_to_python_2(response, data_key)}
