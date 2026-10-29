"""Шефство с согласием подшефного и перерывом между новыми подшефными.

На запуске один студент набрал 495 баллов, по кругу беря и отпуская
подшефных: за каждого нового сразу давали 15 баллов.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.social.models import Mentorship, MentorshipStatus

User = get_user_model()


def agent(name: str) -> User:
    return User.objects.create_user(username=name, password="x", callsign=name, role=Role.AGENT)


class MentorshipConsentTests(APITestCase):
    def setUp(self):
        self.mentor = agent("mentor")
        self.mentees = [agent(f"mentee{i}") for i in range(3)]

    def offer(self, mentee, as_user=None):
        self.client.force_authenticate(as_user or self.mentor)
        return self.client.post(
            reverse("social-mentorships-create"), {"mentee_username": mentee.username}, format="json"
        )

    def answer(self, mentee, mentorship_id: int, action: str = "accept"):
        self.client.force_authenticate(mentee)
        return self.client.post(reverse(f"social-mentorships-{action}", args=[mentorship_id]))

    def rating(self) -> int:
        self.mentor.refresh_from_db()
        return int(self.mentor.rating_current)

    def test_take_end_take_again_cycle_gives_no_extra_points(self):
        base = self.rating()
        first = self.offer(self.mentees[0]).data["id"]
        self.answer(self.mentees[0], first)
        self.client.force_authenticate(self.mentor)
        self.client.post(reverse("social-mentorships-end", args=[first]))

        response = self.offer(self.mentees[1])

        self.assertEqual(response.status_code, 400, "новый подшефный — не раньше чем через 7 дней")
        self.assertEqual(self.rating(), base, "за сам факт шефства баллов нет")

    def test_new_mentee_allowed_after_cooldown(self):
        first = self.offer(self.mentees[0]).data["id"]
        self.answer(self.mentees[0], first)
        Mentorship.objects.filter(pk=first).update(accepted_at=timezone.now() - timedelta(days=8))

        self.assertEqual(self.offer(self.mentees[1]).status_code, 201)

    def test_only_one_open_offer(self):
        self.assertEqual(self.offer(self.mentees[0]).status_code, 201)
        self.assertEqual(self.offer(self.mentees[1]).status_code, 400)

    def test_declined_offer_gives_nothing_and_can_be_repeated(self):
        base = self.rating()
        offer = self.offer(self.mentees[0]).data["id"]
        self.assertEqual(self.answer(self.mentees[0], offer, "decline").status_code, 200)
        self.assertEqual(self.rating(), base)
        self.assertEqual(self.offer(self.mentees[0]).status_code, 201)

    def test_mutual_mentorship_is_refused(self):
        offer = self.offer(self.mentees[0]).data["id"]
        self.answer(self.mentees[0], offer)
        self.assertEqual(self.offer(self.mentor, as_user=self.mentees[0]).status_code, 400)

    def test_only_the_mentee_can_accept(self):
        offer = self.offer(self.mentees[0]).data["id"]
        self.assertEqual(self.answer(self.mentor, offer).status_code, 400)
        self.assertEqual(Mentorship.objects.get(pk=offer).status, MentorshipStatus.PENDING)

    def test_mentee_can_end_active_mentorship(self):
        offer = self.offer(self.mentees[0]).data["id"]
        self.answer(self.mentees[0], offer)
        response = self.client.post(reverse("social-mentorships-end", args=[offer]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Mentorship.objects.get(pk=offer).status, MentorshipStatus.ENDED)
