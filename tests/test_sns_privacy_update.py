"""Privacy PATCH accepts partial toggles but rejects null before persistence."""

import unittest

from pydantic import ValidationError

from app.models.user_privacy_settings import PrivacyScope
from app.modules.sns.account.schemas.account_requests import UpdatePrivacyRequest


class PrivacyUpdateTests(unittest.TestCase):
    def test_explicit_null_is_rejected_for_every_privacy_setting(self):
        for field in UpdatePrivacyRequest.model_fields:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as caught:
                    UpdatePrivacyRequest.model_validate({field: None})
                self.assertEqual(caught.exception.errors()[0]["loc"], (field,))

    def test_omitted_settings_are_preserved_by_partial_patch(self):
        self.assertEqual(UpdatePrivacyRequest().model_dump(exclude_unset=True), {})
        payload = UpdatePrivacyRequest(phone_number_visibility="private")
        self.assertEqual(
            payload.model_dump(exclude_unset=True),
            {"phone_number_visibility": PrivacyScope.private},
        )

    def test_hide_profile_and_field_toggles_are_independent(self):
        payload = UpdatePrivacyRequest(
            is_profile_discoverable=False,
            first_name_visibility="private",
            last_name_visibility="private",
            phone_number_visibility="public",
        )
        data = payload.model_dump(exclude_unset=True)
        self.assertIs(data["is_profile_discoverable"], False)
        self.assertIs(data["first_name_visibility"], PrivacyScope.private)
        self.assertIs(data["phone_number_visibility"], PrivacyScope.public)
        self.assertNotIn("profile_picture_visibility", data)


if __name__ == "__main__":
    unittest.main()
