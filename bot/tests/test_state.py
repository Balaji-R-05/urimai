import pytest
import state


@pytest.fixture(autouse=True)
def _clean_registries():
    state._states.clear()
    state._locks.clear()
    yield
    state._states.clear()
    state._locks.clear()


# ---------- get / reset ----------

def test_get_creates_and_reuses_the_same_state():
    a = state.get(1)
    b = state.get(1)
    assert a is b


def test_get_is_independent_per_chat():
    assert state.get(1) is not state.get(2)


def test_reset_preserves_language_and_voice_but_clears_everything_else():
    st = state.get(1)
    st.lang, st.lang_chosen, st.voice_on = "ta", True, False
    st.last = {"x": 1}
    st.card_msg_id = 99
    st.feedback_for = "pm_kisan"

    new = state.reset(1)

    assert new is not st
    assert (new.lang, new.lang_chosen, new.voice_on) == ("ta", True, False)
    assert new.last is None
    assert new.card_msg_id is None
    assert new.feedback_for is None
    assert state.get(1) is new


def test_new_state_has_no_pending_feedback():
    assert state.get(1).feedback_for is None


def test_session_id_is_namespaced_by_chat_id():
    assert state.session_id(42) == "tg:42"


# ---------- lock ----------

def test_lock_is_reused_per_chat_and_distinct_across_chats():
    l1 = state.lock(1)
    assert state.lock(1) is l1
    assert state.lock(2) is not l1


# ---------- LRU eviction ----------

def test_eviction_drops_the_least_recently_touched_chat(monkeypatch):
    monkeypatch.setattr(state, "MAX_CHATS", 2)
    state.get(1)
    state.get(2)
    state.get(3)  # over the cap: 1 was least recently touched

    assert set(state._states) == {2, 3}


def test_touching_a_chat_protects_it_from_eviction(monkeypatch):
    monkeypatch.setattr(state, "MAX_CHATS", 2)
    state.get(1)
    state.get(2)
    state.get(1)  # re-touch 1, so 2 becomes the oldest
    state.get(3)

    assert set(state._states) == {1, 3}


def test_eviction_drops_the_lock_too_when_it_is_free(monkeypatch):
    monkeypatch.setattr(state, "MAX_CHATS", 1)
    state.get(1)
    state.lock(1)

    state.get(2)

    assert 1 not in state._states
    assert 1 not in state._locks


def test_eviction_keeps_the_lock_while_it_is_held(monkeypatch):
    monkeypatch.setattr(state, "MAX_CHATS", 1)
    state.get(1)

    class StubLock:
        def locked(self):
            return True

    state._locks[1] = StubLock()
    state.get(2)  # evicts chat 1's state, but its lock is in use

    assert 1 not in state._states
    assert 1 in state._locks
