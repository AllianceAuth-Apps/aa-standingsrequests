from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase, json_response_to_python

from standingsrequests.tests.factories import UserMainApproverFactory

MODULE_PATH = "standingsrequests.views.effective_requests"


class TestEffectiveRequestsData2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def setUp(self):
        cache.clear()

    @patch(MODULE_PATH + ".compose_standing_requests_data")
    def test_effective_requests_data(self, mock_compose_standing_requests_data):
        # given
        contact_id = 90_000_001
        contact_name = "Bruce Wayne"
        request_date = now()
        obj_1 = {
            "contact_id": contact_id,
            "contact_name": contact_name,
            "contact_icon_url": "",
            "contact_name_html": {
                "display": "",
                "sort": "",
            },
            "corporation_id": 98_000_000,
            "corporation_name": "Wayne Technologies",
            "corporation_ticker": "WYT",
            "alliance_id": 99_000_001,
            "alliance_name": "Wayne Enterprises",
            "organization_html": "",
            "request_date": request_date,
            "action_date": now(),
            "has_scopes": True,
            "state": "Member",
            "reason": "",
            "labels": [],
            "main_character_name": "Bruce Wayne",
            "main_character_ticker": "WYT",
            "main_character_icon_url": "url",
            "main_character_html": "Bruce Wayne",
            "actioned": "",
            "is_effective": True,
            "is_corporation": False,
            "is_character": True,
            "action_by": "",
        }
        mock_compose_standing_requests_data.return_value = [obj_1]
        self.client.force_login(UserMainApproverFactory())

        # when
        response = self.client.get(reverse("standingsrequests:effective_requests_data"))

        # then
        self.assertEqual(response.status_code, 200)
        data = json_response_to_python(response)["data"]
        self.assertEqual(len(data), 1)
        obj_2 = data.pop()
        self.assertEqual(obj_2["contact_name"], contact_name)
        self.assertEqual(obj_2["request_date_str"]["sort"], request_date.isoformat())
