import pytest
from app.modules.schedule.service import allocate

SOURCE = (
    '档口预测单,修订号,提交时间,目标日型,分位百分比,保底样本,售罄加成百分比,每锅份数,营业记录,原始备注\n'
    'A1,1,2026-11-18T09:30:00+08:00,工作日,100,1,0,10,2026-10-12:工作日:50:正常,大档口\n'
    'A2,1,2026-11-18T09:30:00+08:00,工作日,100,1,0,10,2026-10-12:工作日:20:正常,小档口\n'
)
BOOK = '档口预测单,外部记录值(份)\nA1,30\nA2,10\n'


def row(key, pots, size=10):
    return {'key': key, 'line': 1, 'revision': 1, 'amount': str(pots * size), 'unit': '份',
            'raw': [], 'proof': [], 'pots': pots, 'pot_size': size}


def pots_of(planned):
    return {item['key']: item['scheduled_pots'] for item in planned}


@pytest.fixture
def batch(client):
    return client.post('/api/runs', json={'data': SOURCE, 'book': BOOK, 'pot_limit': 4}).json()


def test_unlimited_schedules_full_demand():
    planned, summary = allocate([row('a', 3), row('b', 4)], None)
    assert pots_of(planned) == {'a': 3, 'b': 4}
    assert summary['slack_pots'] == 0 and summary['gap'] == '0'


def test_guarantees_one_pot_then_splits_by_gap():
    planned, summary = allocate([row('a', 1), row('b', 1), row('c', 5)], 5)
    assert pots_of(planned) == {'a': 1, 'b': 1, 'c': 3}
    assert summary['scheduled_pots'] == 5 and summary['starved'] == 0


def test_hot_stall_gets_more_than_even_share():
    planned, _ = allocate([row('a', 2), row('b', 8)], 5)
    assert pots_of(planned) == {'a': 1, 'b': 4}


def test_zero_demand_stall_not_counted():
    planned, summary = allocate([row('a', 0), row('b', 3)], 1)
    assert pots_of(planned) == {'a': 0, 'b': 1}
    assert summary['starved'] == 0


def test_cap_below_stall_count_is_deterministic():
    planned, summary = allocate([row('a', 2), row('b', 2), row('c', 2)], 2)
    assert pots_of(planned) == {'a': 1, 'b': 1, 'c': 0}
    assert summary['starved'] == 1


def test_slack_when_cap_exceeds_demand():
    _, summary = allocate([row('a', 1), row('b', 2)], 10)
    assert summary['slack_pots'] == 7 and summary['gap_pots'] == 0


def test_batch_shows_demand_scheduled_and_gap(batch):
    rows = {item['key']: item for item in batch['accepted']}
    assert (rows['A1']['demand'], rows['A1']['amount'], rows['A1']['gap']) == ('50', '30', '20')
    assert (rows['A2']['demand'], rows['A2']['amount'], rows['A2']['gap']) == ('20', '10', '10')
    assert batch['schedule'] == {'pot_limit': 4, 'demand_pots': 7, 'scheduled_pots': 4,
                                 'gap_pots': 3, 'gap': '30', 'starved': 0, 'slack_pots': 0}
    metrics = {item['metric']: item['value'] for item in rows['A1']['proof']}
    assert metrics['排产锅次'] == '3' and metrics['缺口'] == '20'


def test_reconcile_uses_scheduled_amounts(batch):
    assert batch['book']['matched'] == 2 and batch['book']['mismatched'] == 0
    assert batch['book']['actual'] == '40'


def test_rerun_same_batch_adds_no_schedule(client, batch):
    again = client.post('/api/runs', json={'data': SOURCE, 'book': BOOK, 'pot_limit': 4}).json()
    assert again == batch
    assert len(client.get('/api/runs').json()) == 1


def test_different_caps_are_separate_batches(client, batch):
    other = client.post('/api/runs', json={'data': SOURCE, 'book': BOOK, 'pot_limit': 5}).json()
    assert other['manifest']['run_id'] != batch['manifest']['run_id']
    history = {item['id']: item['pot_limit'] for item in client.get('/api/runs').json()}
    assert history == {batch['manifest']['run_id']: 4, other['manifest']['run_id']: 5}
    restored = client.get(f"/api/runs/{other['manifest']['run_id']}").json()
    assert restored['schedule']['pot_limit'] == 5 and restored['schedule']['scheduled_pots'] == 5


def test_replay_keeps_pot_limit(client, batch):
    run_id = batch['manifest']['run_id']
    assert client.post(f'/api/runs/{run_id}/replay').json() == batch
    assert len(client.get('/api/runs').json()) == 1


def test_export_carries_schedule(client, batch):
    proof = client.get(f"/api/export/{batch['manifest']['run_id']}").json()
    assert proof['schedule']['pot_limit'] == 4
    assert proof['results'][0]['scheduled_pots'] == 3


def test_default_batch_has_no_gap(client):
    report = client.post('/api/runs', json={'data': SOURCE, 'book': BOOK}).json()
    assert report['schedule']['pot_limit'] is None
    assert all(item['amount'] == item['demand'] and item['gap'] == '0' for item in report['accepted'])


def test_pot_limit_validation(client):
    assert client.post('/api/runs', json={'pot_limit': -1}).status_code == 422
    assert client.post('/api/runs', json={'pot_limit': 2.5}).status_code == 422


def test_schedule_endpoint(client):
    plan = client.post('/api/schedule', json={'data': SOURCE, 'pot_limit': 4}).json()
    assert plan['summary']['scheduled_pots'] == 4
    assert {row['key'] for row in plan['rows']} == {'A1', 'A2'}
