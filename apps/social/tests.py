from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class SocialLimitsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u1", password="x", callsign="u1")
        self.opponent = get_user_model().objects.create_user(
            username="u2", password="x", callsign="u2", rating_current=600
        )
        self.client.force_authenticate(self.user)

    def test_duel_rating_diff_limit(self):
        url = reverse("social-duels-create")
        response = self.client.post(url, {"opponent_username": self.opponent.username}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

