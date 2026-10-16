from decimal import Decimal, ROUND_HALF_UP

PRO_PRICE = Decimal("9.99")


def to_cents(amount):
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
