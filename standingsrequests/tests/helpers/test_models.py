from app_utils.testing import NoSocketsTestCase

from standingsrequests.tests.factories import FrozenAuthUserFactory


class TestGatherEntityIds(NoSocketsTestCase):
    def test_should_gather_all_entity_ids(self):
        # given
        alt = FrozenAuthUserFactory(create_faction=True)

        # when
        result = alt.entity_ids()

        # then
        expected = {
            alt.alliance.id,
            alt.character.id,
            alt.corporation.id,
            alt.faction.id,
        }
        self.assertSetEqual(result, expected)

    def test_should_gather_entity_ids_and_ignore_none_values(self):
        # given
        alt = FrozenAuthUserFactory()

        # when
        result = alt.entity_ids()

        # then
        expected = {alt.alliance.id, alt.character.id, alt.corporation.id}
        self.assertSetEqual(result, expected)
