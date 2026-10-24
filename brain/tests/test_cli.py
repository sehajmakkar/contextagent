from typer.testing import CliRunner

from brain.cli import app
from brain.config import get_settings
from brain.db import store
from brain.models import ObservationIn


def test_untrusted_text_is_not_rendered_as_markup(tmp_path, monkeypatch):
    """Regression: '[available times next week]' in a draft was swallowed as a Rich style tag."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    conn = store.connect(get_settings().db_path)
    obs = ObservationIn(captured_at="2026-10-19T10:00:00+05:30", app_name="Mail", bundle_id="x",
                        window_title="[bold]inbox[/bold]", text="Send [available times] please")
    with conn:
        obs_id = store.insert_observation(conn, obs, obs.text)
        store.create_loop(conn, observation_id=obs_id, evidence_quote="Send [available times] please",
                          title="Reply with [available times]", direction="i_owe", counterparty="Maya",
                          deliverable="times", due_date=None, confidence=0.9)

    result = CliRunner().invoke(app, ["show", "1"], env={"COLUMNS": "200"})
    get_settings.cache_clear()

    assert result.exit_code == 0, result.output
    assert "Reply with [available times]" in result.output
    assert "[created]" in result.output and "[bold]inbox[/bold]" in result.output
