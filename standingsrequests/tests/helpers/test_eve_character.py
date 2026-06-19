from app_utils.testing import NoSocketsTestCase

from standingsrequests.helpers.eve_character import EveCharacterHelper
from standingsrequests.tests.factories import CharacterAffiliationFactory


class TestEveCharacterHelper(NoSocketsTestCase):
    def test_should_initialize_from_character_affiliation_with_alliance(self):
        # given
        ca = CharacterAffiliationFactory()

        # when
        character = EveCharacterHelper(character_id=ca.character.id)

        # then
        self.assertEqual(character.character_id, ca.character.id)
        self.assertEqual(character.character_name, ca.character.name)
        self.assertEqual(character.corporation_id, ca.corporation.id)
        self.assertEqual(character.corporation_name, ca.corporation.name)
        self.assertEqual(character.alliance_id, ca.alliance.id)
        self.assertEqual(character.alliance_name, ca.alliance.name)

    def test_should_initialize_from_character_affiliation_without_alliance(self):
        # given
        ca = CharacterAffiliationFactory(alliance=None)

        # when
        character = EveCharacterHelper(character_id=ca.character.id)

        # then
        self.assertEqual(character.character_id, ca.character.id)
        self.assertEqual(character.character_name, ca.character.name)
        self.assertEqual(character.corporation_id, ca.corporation.id)
        self.assertEqual(character.corporation_name, ca.corporation.name)
        self.assertIsNone(character.alliance_id)
        self.assertIsNone(character.alliance_name)

    def test_should_initialize_without_character_affiliation(self):
        # when
        character = EveCharacterHelper(1001)

        # then
        self.assertEqual(character.character_id, 1001)
