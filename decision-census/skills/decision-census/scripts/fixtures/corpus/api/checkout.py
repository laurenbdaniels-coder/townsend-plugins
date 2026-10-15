def grand(items, order):
    grandtotal = sum(item.rate * item.qty for item in items)
    if order.totalprice > 100:
        return grandtotal
    return unitprice * order.qty
