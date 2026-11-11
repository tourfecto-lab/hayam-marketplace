from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any, cast
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from django.test import Client

from store.models import Order, Variant
from store.services import CheckoutError, checkout

from .conftest import VariantFactory


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_retry", [False, True])
def test_simultaneous_checkout(same_retry: bool) -> None:
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock semantics are exercised in CI")
    variant = cast(Variant, VariantFactory(stock=1))
    sessions = [Client().session.session_key, Client().session.session_key]
    keys = [uuid4(), uuid4()]
    if same_retry:
        sessions[1], keys[1] = sessions[0], keys[0]
    gate = Barrier(2)

    def buy(index: int) -> Any:
        close_old_connections()
        try:
            gate.wait(timeout=10)
            return checkout(
                cart={str(variant.pk): 1},
                session_key=sessions[index] or "",
                key=keys[index],
                details={"name": "منى", "phone": "+201012345678", "address": "القاهرة"},
            ).pk
        except CheckoutError:
            return None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(buy, [0, 1]))
    variant.refresh_from_db()
    assert variant.stock == 0
    assert Order.objects.count() == 1
    if same_retry:
        assert results[0] == results[1] is not None
    else:
        assert sum(result is not None for result in results) == 1
