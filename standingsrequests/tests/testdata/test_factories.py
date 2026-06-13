from app_utils.testing import NoSocketsTestCase

from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    EveCorporationFactory,
)


class TestEveCorporationFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = EveCorporationFactory()
        self.assertTrue(o)


class TestCharacterAffiliationFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = CharacterAffiliationFactory()
        self.assertTrue(o)

    def test_can_create_with_eve_character(self):
        o = CharacterAffiliationFactory(is_eve_character=True)
        self.assertEqual(o.eve_character.character_id, o.character.id)
