from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils.timezone import now

from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import add_character_to_user

from standingsrequests.models import StandingRequest
from standingsrequests.tests.factories import (
    ContactCharacterFactory,
    ContactSetFactory,
    UserMainRequestorFactory,
)

PACKAGE_PATH = "standingsrequests.management.commands"
TEST_REQUIRED_SCOPE = "mind_reading.v1"
STANDINGS_ALLIANCE_ID = 99_000_123


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
@patch(
    "standingsrequests.core.app_config.STR_ALLIANCE_IDS",
    [str(STANDINGS_ALLIANCE_ID)],
)
@patch(
    "standingsrequests.models.SR_REQUIRED_SCOPES",
    {"Member": [TEST_REQUIRED_SCOPE], "Blue": [], "": []},
)
@patch(PACKAGE_PATH + ".standingsrequests_sync_blue_alts.get_input")
class TestSyncRequests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        EveCharacterFactory(alliance_id=STANDINGS_ALLIANCE_ID)
        cls.main_character = EveCharacterFactory(alliance_id=STANDINGS_ALLIANCE_ID)

    def test_abort_if_input_is_not_y(self, mock_get_input):
        mock_get_input.return_value = "N"

        # when
        call_command("standingsrequests_sync_blue_alts", stdout=StringIO())

        # then
        self.assertEqual(StandingRequest.objects.count(), 0)

    def test_creates_new_request_for_blue_alt(self, mock_get_input):
        # given
        mock_get_input.return_value = "Y"
        user = UserMainRequestorFactory(main_character__character=self.main_character)
        alt = EveCharacterFactory()
        add_character_to_user(user, alt, scopes=["dummy"])
        cs = ContactSetFactory()
        ContactCharacterFactory(contact_set=cs, contact_id=alt.character_id, standing=5)

        # when
        call_command("standingsrequests_sync_blue_alts", stdout=StringIO())

        # then
        self.assertEqual(StandingRequest.objects.count(), 1)
        request = StandingRequest.objects.first()
        self.assertEqual(request.user, user)
        self.assertEqual(request.contact_id, alt.character_id)
        self.assertEqual(request.is_effective, True)
        self.assertAlmostEqual((now() - request.request_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.action_date).seconds, 0, delta=30)
        self.assertAlmostEqual((now() - request.effective_date).seconds, 0, delta=30)
