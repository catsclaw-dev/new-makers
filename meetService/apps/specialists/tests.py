from django.test import TestCase

from apps.specialists.forms import SpecialistProfileForm
from apps.specialists.models import SpecialistProfile


class SpecialistProfileFormTests(TestCase):
    def test_short_bio_is_invalid(self):
        form = SpecialistProfileForm(
            data={
                "level": SpecialistProfile.Level.JUNIOR,
                "status": SpecialistProfile.AvailabilityStatus.LOOKING,
                "bio": "Слишком кратко",
                "experience_years": 2,
                "github_url": "",
                "gitlab_url": "",
                "portfolio_url": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("bio", form.errors)

    def test_experience_cannot_exceed_business_limit(self):
        form = SpecialistProfileForm(
            data={
                "level": SpecialistProfile.Level.SENIOR,
                "status": SpecialistProfile.AvailabilityStatus.OPEN,
                "bio": "Опытный специалист для командной разработки.",
                "experience_years": 61,
                "github_url": "",
                "gitlab_url": "",
                "portfolio_url": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("experience_years", form.errors)
