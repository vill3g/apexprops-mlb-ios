import os
import shutil
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Never let the test suite touch the real users.db / user folders.
# Several tests change user settings (trade size, stop loss, model...) on the
# first active users they find; on a real install those are real accounts.
# These variables are read by backend.database.models at import time, and this
# file is imported by pytest before any test module imports the backend.
# ---------------------------------------------------------------------------
_TEST_ROOT = tempfile.mkdtemp(prefix="kalshi_tests_")
os.environ["USERS_DB_PATH"] = os.path.join(_TEST_ROOT, "users.db")
os.environ["USERS_DATA_DIR"] = os.path.join(_TEST_ROOT, "data")
os.makedirs(os.environ["USERS_DATA_DIR"], exist_ok=True)

import backend.database.models as _models  # noqa: E402

assert os.path.abspath(_models.DB_PATH) == os.path.abspath(os.environ["USERS_DB_PATH"]), \
    "Refusing to run tests against the real users.db"
_models.init_db()

# Two ordinary accounts for tests that need "active users" to exist.
for _name in ("seed_trader_one", "seed_trader_two"):
    try:
        _models.create_user(_name, "seed-password-hash")
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def setup_db():
    yield
