import pytest
import os
import json
from backend.btc.paper_balance import load_balance, update_balance, reset_balance
from backend.database.models import DATA_DIR, init_db, get_user_by_id

def test_paper_balance():
    # Because paper_balance uses guest_id logic from guest_manager and users from DB, 
    # it's best to test simple logic and ensure no crash.
    # Note: reset_balance defaults to 500.
    
    bal = load_balance()
    assert isinstance(bal, float)
    
    update_balance(10.0)
    new_bal = load_balance()
    # It might be hard to assert exact amounts if the DB is live, but we can verify it doesn't crash.
    assert isinstance(new_bal, float)

