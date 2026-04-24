from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase


class ProfilePrivacyTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner", password="x", callsign="owner", rating_current=555
        )
        self.viewer = get_user_model().objects.create_user(
            username="viewer", password="x", callsign="viewer", role="agent"
        )

    def test_public_profile_hides_exact_rating_for_other_agent(self):
        self.client.force_authenticate(self.viewer)
        url = reverse("profile-public", kwargs={"username": self.user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data.get("rating_current"))

