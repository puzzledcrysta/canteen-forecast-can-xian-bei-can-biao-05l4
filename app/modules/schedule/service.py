from app.settings import UNIT


def spread(gaps, remaining):
    """按未满足锅次比例分摊，最大余数法取整，同余数按业务键序。"""
    total = sum(gaps.values())
    shares = {key: min(remaining * gap // total, gap) for key, gap in gaps.items()}
    left = remaining - sum(shares.values())
    order = sorted(gaps, key=lambda key: (-(remaining * gaps[key] % total), key))
    for key in order:
        if not left:
            break
        if shares[key] < gaps[key]:
            shares[key] += 1
            left -= 1
    return shares, left


def allocate(rows, cap):
    """在共用灶台锅次上限内排产：先保每个档口一锅开餐，再按缺口比例分锅。"""
    demands = {row['key']: row['pots'] for row in rows}
    scheduled = {key: 0 for key in demands}
    if cap is None:
        scheduled.update(demands)
    elif cap:
        active = {key: pots for key, pots in demands.items() if pots}
        if len(active) <= cap:
            for key in active:
                scheduled[key] = 1
        remaining = cap - sum(scheduled.values())
        while remaining:
            gaps = {key: demands[key] - scheduled[key] for key in active if scheduled[key] < demands[key]}
            if not gaps:
                break
            shares, remaining = spread(gaps, remaining)
            for key, extra in shares.items():
                scheduled[key] += extra
    planned = []
    for row in rows:
        pots, size = scheduled[row['key']], row['pot_size']
        gap = (row['pots'] - pots) * size
        proof = [*row['proof'],
                 {'metric': '排产锅次', 'value': str(pots), 'unit': '锅'},
                 {'metric': '缺口', 'value': str(gap), 'unit': UNIT}]
        planned.append({**row, 'demand': row['amount'], 'amount': str(pots * size),
                        'scheduled_pots': pots, 'gap': str(gap), 'proof': proof})
    summary = {'pot_limit': cap, 'demand_pots': sum(demands.values()),
               'scheduled_pots': sum(scheduled.values()),
               'gap_pots': sum(demands.values()) - sum(scheduled.values()),
               'gap': str(sum((demands[row['key']] - scheduled[row['key']]) * row['pot_size'] for row in rows)),
               'starved': sum(1 for key in demands if demands[key] and not scheduled[key])}
    summary['slack_pots'] = cap - summary['scheduled_pots'] if cap is not None else 0
    return planned, summary
