from pathlib import Path

from dotenv import dotenv_values

from tests.test_search_route import root_app  # noqa: F401


def test_write_config_values_round_trips_values_starting_with_a_quote(root_app):  # noqa: F811
    module, _client = root_app
    module._load_config_module = lambda: None
    Path(".env").write_text("DB_HOST=localhost\nDB_PASSWORD=old\nDB_NAME=old\n", encoding="utf-8")

    updates = {
        "DB_PASSWORD": "'s3cret",
        "DB_NAME": "'bettafish'",
        "DB_USER": '"admin',
        "QUERY_ENGINE_API_KEY": "\t'key",
    }
    module.write_config_values(updates)

    values = dotenv_values(".env")
    for key, value in updates.items():
        assert values[key] == value
    assert values["DB_HOST"] == "localhost"
