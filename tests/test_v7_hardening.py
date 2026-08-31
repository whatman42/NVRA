from pathlib import Path
from god.idx.market_rules import validate_idx_order
from god.accounting.transaction_costs import estimate_cost
from god.execution.recovery.order_journal import OrderJournal, OrderRecord
from god.execution.recovery.reconcile import reconcile

def test_idx_rules():
    assert validate_idx_order(199,100).ok
    assert not validate_idx_order(199,50).ok

def test_costs_are_config_driven():
    c=estimate_cost(1_000_000, commission_bps=10, sell_tax_bps=10, is_sell=True)
    assert c.total == 2000

def test_journal_idempotency_and_replay(tmp_path):
    p=tmp_path/'orders.jsonl'; j=OrderJournal(p)
    k=j.idempotency_key('BBCA','BUY','sig-1','s1')
    j.append(OrderRecord(k,'BBCA','BUY',100,9000))
    assert len(j.records())==1
    assert j.records()[0].intent_id==k

def test_reconciliation_fails_closed():
    r=reconcile({'BBCA':100},{'BBCA':200})
    assert not r.healthy and r.safe_mode
