from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
)

from app_utils.testing import NoSocketsTestCase

from standingsrequests.models import StandingRequest, StandingRevocation
from standingsrequests.tests.testdata.factories import (
    StandingRequestCharacterFactory,
    StandingRevocationCharacterFactory,
    UserMainApproverFactory,
)
from standingsrequests.tests.utils_2 import TestCaseWithClearCache
from standingsrequests.views import manage_requests

MODULE_PATH = "standingsrequests.views.manage_requests"


class TestEffectiveRequestsData2(TestCaseWithClearCache):
    @patch(MODULE_PATH + ".compose_standing_requests_data")
    def test_manage_requests_list(self, mock_compose_standing_requests_data):
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
        response = self.client.get(reverse("standingsrequests:manage_requests_list"))

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.context["requests"]), 1)
        obj_2 = response.context["requests"].pop()
        self.assertDictEqual(obj_1, obj_2)

    @patch(MODULE_PATH + ".compose_standing_requests_data")
    def test_manage_revocations_list(self, mock_compose_standing_requests_data):
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
        response = self.client.get(reverse("standingsrequests:manage_revocations_list"))

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.context["revocations"]), 1)
        obj_2 = response.context["revocations"].pop()
        self.assertDictEqual(obj_1, obj_2)


@patch(MODULE_PATH + ".notify")
@patch(MODULE_PATH + ".RequestLogEntry.objects.create_from_standing_request")
class TestManageRequestsWrite(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_mark_as_actioned_when_sr_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRequestCharacterFactory()
        user = UserMainApproverFactory()
        request = self.factory.put(
            reverse(
                "standingsrequests:manage_requests_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        response = manage_requests.manage_requests_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        sr.refresh_from_db()
        self.assertEqual(sr.action_by, user)
        self.assertTrue(sr.action_date)
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_return_not_found_when_sr_not_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        user = UserMainApproverFactory()
        contact_id = 666
        request = self.factory.put(
            reverse(
                "standingsrequests:manage_requests_write",
                kwargs={"contact_id": contact_id},
            )
        )
        request.user = user

        # when
        response = manage_requests.manage_requests_write(request, contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertFalse(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_delete_sr_when_found_and_not_notify_requestor(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRequestCharacterFactory()

        user = UserMainApproverFactory()
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_requests_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        with patch(MODULE_PATH + ".SR_NOTIFICATIONS_ENABLED", False):
            response = manage_requests.manage_requests_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(
            StandingRequest.objects.filter(contact_id=sr.contact_id).exists()
        )
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_delete_sr_when_found_and_notify_requestor(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRequestCharacterFactory()
        EveEntityCharacterFactory(id=sr.contact_id)
        user = UserMainApproverFactory()
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_requests_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        with patch(MODULE_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            response = manage_requests.manage_requests_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(
            StandingRequest.objects.filter(contact_id=sr.contact_id).exists()
        )
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertTrue(mock_notify.called)

    def test_should_return_not_found_when_sr_for_delete_not_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        user = UserMainApproverFactory()
        contact_id = 666
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_requests_write",
                kwargs={"contact_id": contact_id},
            )
        )
        request.user = user

        # when
        with self.assertRaises(Http404):
            manage_requests.manage_requests_write(request, contact_id)

        # then
        self.assertFalse(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)


@patch(MODULE_PATH + ".notify")
@patch(MODULE_PATH + ".RequestLogEntry.objects.create_from_standing_request")
class TestManageRevocationsWrite(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_should_mark_as_actioned_when_sr_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRevocationCharacterFactory()
        user = UserMainApproverFactory()
        request = self.factory.put(
            reverse(
                "standingsrequests:manage_revocations_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        response = manage_requests.manage_revocations_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        sr.refresh_from_db()
        self.assertEqual(sr.action_by, user)
        self.assertTrue(sr.action_date)
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_return_not_found_when_sr_not_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        user = UserMainApproverFactory()
        contact_id = 666
        request = self.factory.put(
            reverse(
                "standingsrequests:manage_revocations_write",
                kwargs={"contact_id": contact_id},
            )
        )
        request.user = user

        # when
        response = manage_requests.manage_revocations_write(request, contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertFalse(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_delete_sr_when_found_and_not_notify_requestor(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRevocationCharacterFactory()

        user = UserMainApproverFactory()
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_revocations_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        with patch(MODULE_PATH + ".SR_NOTIFICATIONS_ENABLED", False):
            response = manage_requests.manage_revocations_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(
            StandingRevocation.objects.filter(contact_id=sr.contact_id).exists()
        )
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)

    def test_should_delete_sr_when_found_and_notify_requestor(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        sr = StandingRevocationCharacterFactory()
        EveEntityCharacterFactory(id=sr.contact_id)
        user = UserMainApproverFactory()
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_revocations_write",
                kwargs={"contact_id": sr.contact_id},
            )
        )
        request.user = user

        # when
        with patch(MODULE_PATH + ".SR_NOTIFICATIONS_ENABLED", True):
            response = manage_requests.manage_revocations_write(request, sr.contact_id)

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(
            StandingRequest.objects.filter(contact_id=sr.contact_id).exists()
        )
        self.assertTrue(mock_create_from_standing_request.called)
        self.assertTrue(mock_notify.called)

    def test_should_return_not_found_when_sr_for_delete_not_found(
        self, mock_create_from_standing_request: MagicMock, mock_notify: MagicMock
    ):
        # given
        user = UserMainApproverFactory()
        contact_id = 666
        request = self.factory.delete(
            reverse(
                "standingsrequests:manage_revocations_write",
                kwargs={"contact_id": contact_id},
            )
        )
        request.user = user

        # when
        with self.assertRaises(Http404):
            manage_requests.manage_revocations_write(request, contact_id)

        # then
        self.assertFalse(mock_create_from_standing_request.called)
        self.assertFalse(mock_notify.called)


@patch(MODULE_PATH + ".app_config.standings_source_entity")
class TestManageStandings(NoSocketsTestCase):
    def test_can_open_page(self, mock_standings_source_entity: MagicMock):
        # given
        organization = EveEntityAllianceFactory()
        mock_standings_source_entity.return_value = organization
        StandingRequestCharacterFactory()
        StandingRequestCharacterFactory()
        StandingRevocationCharacterFactory()
        user = UserMainApproverFactory()
        self.client.force_login(user)

        # when
        response = self.client.get(reverse("standingsrequests:manage"))

        # then
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.context["requests_count"], 2)
        self.assertEqual(response.context["revocations_count"], 1)
        self.assertEqual(response.context["organization"], organization)
