from app_utils.testing import NoSocketsTestCase

from standingsrequests.tests.testdata.factories import (
    CharacterAffiliationFactory,
    ContactCharacterFactory,
    ContactSetFactory,
    EveCorporationHelperFactory,
    FrozenAuthUserFactory,
)


class TestCharacterAffiliationFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = CharacterAffiliationFactory()
        self.assertTrue(o)

    def test_can_create_with_eve_character(self):
        o = CharacterAffiliationFactory(is_eve_character=True)
        self.assertEqual(o.eve_character.character_id, o.character.id)


class TestContactCharacterFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = ContactCharacterFactory()
        self.assertTrue(o.eve_entity.is_character)

    def test_can_create_eve_entity_from_contact_id(self):
        contact_id = 1001
        o = ContactCharacterFactory(contact_id=contact_id)
        self.assertEqual(o.eve_entity.id, contact_id)
        self.assertTrue(o.eve_entity.is_character)


class TestFrozenAuthUserFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = FrozenAuthUserFactory()
        self.assertTrue(o)


class TestEveCorporationFactory(NoSocketsTestCase):
    def test_can_create_with_defaults(self):
        o = EveCorporationHelperFactory()
        self.assertTrue(o)


class TestContactSetFactory(NoSocketsTestCase):
    def test_can_create_empty(self):
        x = ContactSetFactory()
        self.assertEqual(x.contacts.count(), 0)

    def test_can_create_with_contacts(self):
        x = ContactSetFactory(contacts=3)
        self.assertEqual(x.contacts.count(), 3)
