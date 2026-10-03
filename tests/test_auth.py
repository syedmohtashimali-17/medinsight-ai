import sys, pathlib, hashlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from utils.auth import verify, _check

def test_plain_and_hashed():
    users = {"a": "pw1", "b": "sha256:" + hashlib.sha256(b"secret").hexdigest()}
    assert verify("a", "pw1", users) and not verify("a", "bad", users)
    assert verify("b", "secret", users) and not verify("b", "pw1", users)

def test_unknown_and_empty():
    assert not verify("zzz", "x", {"a": "pw1"})
    assert not verify("", "", {"a": "pw1"})
    assert not verify(None, None, {"a": "pw1"})

def test_streamlit_flow():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(pathlib.Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30).run()
    assert any("Log in" in x.value for x in at.subheader)      # gate shown
    assert not at.exception
    at.text_input(key="login_user").input("demo")
    at.text_input(key="login_pass").input("wrong")
    at.button[0].click(); at.run()
    assert at.error and "Incorrect" in at.error[0].value       # wrong password rejected
    at.text_input(key="login_pass").input("medinsight123")
    at.button[0].click(); at.run()
    assert at.session_state["auth_user"] == "demo"             # correct password accepted
    assert at.session_state["current_page"] == "welcome"        # real app visible now (P1 UI)
    assert not at.exception
