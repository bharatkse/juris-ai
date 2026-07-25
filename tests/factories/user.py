"""
User factory.
"""

from __future__ import annotations

import factory
from faker import Faker

from src.core.enums import Gender
from src.db.mixins import generate_prefixed_uuid_pk
from src.db.models.user import User
from tests.factories.base import BaseFactory

fake = Faker()


class UserFactory(BaseFactory):
    """
    Factory for User ORM model.
    """

    class Meta:
        model = User

    class Params:
        """
        Reusable factory traits.
        """

        inactive = factory.Trait(
            is_active=False,
        )

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("user"),
    )

    email = factory.LazyAttribute(
        lambda _: fake.unique.email(),
    )

    hashed_password = factory.LazyFunction(
        lambda: fake.sha256(raw_output=False),
    )

    first_name = factory.LazyFunction(
        fake.first_name,
    )

    last_name = factory.LazyFunction(
        fake.last_name,
    )

    gender = factory.Iterator(
        list(Gender),
    )

    date_of_birth = factory.LazyFunction(
        fake.date_of_birth,
    )

    phone_number = factory.LazyFunction(
        fake.phone_number,
    )

    is_active = True
