from trillion.tools import memory as memory_module


def test_remember_list_update_forget_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))

    add_result = memory_module.remember_fact({"text": "User's name is Alex"})
    assert "User's name is Alex" in add_result
    fact_id = add_result.split("[")[1].split("]")[0]

    listing = memory_module.list_facts_tool({})
    assert "User's name is Alex" in listing

    update_result = memory_module.update_fact({"id": fact_id, "text": "User's name is Alexandra"})
    assert "Alexandra" in update_result
    assert "Alexandra" in memory_module.list_facts_tool({})
    assert "User's name is Alex\n" not in memory_module.list_facts_tool({})

    forget_result = memory_module.forget_fact({"id": fact_id})
    assert "Forgot" in forget_result
    assert memory_module.list_facts_tool({}) == "No facts remembered yet."


def test_remember_fact_requires_text(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert memory_module.remember_fact({"text": "   "}).startswith("error:")


def test_update_and_forget_report_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    assert memory_module.update_fact({"id": "deadbeef", "text": "x"}).startswith("error:")
    assert memory_module.forget_fact({"id": "deadbeef"}).startswith("error:")


def test_facts_persist_across_separate_loads_like_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    memory_module.remember_fact({"text": "Prefers morning meetings"})

    # a fresh load_facts() call, as a new process/session would do on
    # startup, sees what was written by the previous one
    facts = memory_module.load_facts()
    assert facts == [{"id": facts[0]["id"], "text": "Prefers morning meetings"}]


def test_store_is_plain_text_and_hand_editable(tmp_path, monkeypatch):
    monkeypatch.setenv("TRILLION_DATA_DIR", str(tmp_path))
    memory_module.remember_fact({"text": "Likes plain text"})

    raw = memory_module._store_path().read_text()
    assert "Likes plain text" in raw
    assert raw.startswith("#")  # a human-readable header, not a JSON blob

    # a human hand-editing the file (fixing a typo) is respected on next load
    fixed = raw.replace("Likes plain text", "Likes plain, editable text")
    memory_module._store_path().write_text(fixed)
    facts = memory_module.load_facts()
    assert facts[0]["text"] == "Likes plain, editable text"
