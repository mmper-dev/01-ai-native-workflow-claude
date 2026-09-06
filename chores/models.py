from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user, swapped in from migration zero so it can grow later.

    Household membership, skills, availability and the stretch-learning opt-in
    are deliberately NOT here -- they belong to a Membership model, because the
    plan scopes them per household rather than per person globally.
    """

    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.username
