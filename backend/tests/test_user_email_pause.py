"""Verify pausing/resuming user delivery without sending mail or touching a DB."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.config import Settings, settings
from app.services import learning_tips, reengagement
from app.utils import email


@pytest.fixture
def resend_send(monkeypatch):
    send = Mock(return_value={"id": "test-email-id"})
    monkeypatch.setattr(email.resend.Emails, "send", send)
    monkeypatch.setattr(email, "RESEND_AVAILABLE", True)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_only")
    return send


def test_pause_defaults_on_and_can_be_explicitly_resumed(monkeypatch):
    monkeypatch.delenv("USER_EMAILS_PAUSED", raising=False)
    assert Settings(_env_file=None).USER_EMAILS_PAUSED is True
    monkeypatch.setenv("USER_EMAILS_PAUSED", "false")
    assert Settings(_env_file=None).USER_EMAILS_PAUSED is False


@pytest.mark.parametrize("paused", [True, False])
@pytest.mark.parametrize("kind", ["recommendations", "learning_tip"])
def test_user_delivery_honors_pause(monkeypatch, resend_send, paused, kind):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", paused)
    if kind == "recommendations":
        result = email.send_recommendations_email(
            "reader@example.test", "Reader", [{"title": "Test Book"}]
        )
    else:
        result = email.send_learning_tip_email(
            "reader@example.test", "Reader", "Test Book", "Author",
            {"insight": "A useful idea", "action": "Try it"},
        )
    if paused:
        assert result["status"] == "paused"
        resend_send.assert_not_called()
    else:
        assert result["status"] == "success"
        resend_send.assert_called_once()


@pytest.mark.parametrize("force", [True, False])
@pytest.mark.parametrize("send_batch", [
    reengagement.send_recommendation_emails,
    learning_tips.send_learning_tip_emails,
])
def test_paused_batches_do_no_work_even_when_forced(monkeypatch, resend_send, force, send_batch):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", True)
    db = Mock()
    recommendations = Mock()
    tips = Mock()
    monkeypatch.setattr(reengagement, "get_recommendations_for_user", recommendations)
    monkeypatch.setattr(learning_tips, "_generate_learning_tip", tips)

    result = send_batch(db, force=force, max_users=1, only_user_id="test-user")

    assert result == {"status": "paused", "eligible": 0, "sent": 0, "skipped": 0, "errors": 0}
    assert db.mock_calls == []
    recommendations.assert_not_called()
    tips.assert_not_called()
    resend_send.assert_not_called()


@pytest.mark.parametrize("pause_during_generation", [True, False])
@pytest.mark.parametrize("kind", ["recommendations", "learning_tip"])
def test_batch_preserves_history_if_delivery_is_paused(
    monkeypatch, resend_send, pause_during_generation, kind
):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", False)
    previous_send = datetime(2025, 1, 1, tzinfo=timezone.utc)
    user = SimpleNamespace(
        id="test-user", email="reader@example.test",
        last_recommendations_email_at=previous_send,
        last_learning_tip_email_at=previous_send,
    )
    profile = SimpleNamespace(full_name="Reader Example", biggest_challenge="Pricing")
    book = SimpleNamespace(id="test-book", title="Test Book", author_name="Author")

    db = Mock()
    users_query = Mock()
    users_query.join.return_value = users_query
    users_query.filter.return_value = users_query
    users_query.all.return_value = [user]
    profile_query = Mock()
    profile_query.filter.return_value.one_or_none.return_value = profile
    db.query.side_effect = [users_query, profile_query]

    def generate(*args, **kwargs):
        if pause_during_generation:
            monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", True)
        return [book] if kind == "recommendations" else {"insight": "A useful idea"}

    if kind == "recommendations":
        module = reengagement
        send_batch = module.send_recommendation_emails
        stamp = "last_recommendations_email_at"
        monkeypatch.setattr(module, "get_recommendations_for_user", generate)
    else:
        module = learning_tips
        send_batch = module.send_learning_tip_emails
        stamp = "last_learning_tip_email_at"
        monkeypatch.setattr(module, "_current_book_for_user", lambda *args: book)
        monkeypatch.setattr(module, "_generate_learning_tip", generate)
    event = Mock()
    monkeypatch.setattr(module, "log_event_best_effort", event)

    result = send_batch(db, force=True)

    assert result["errors"] == 0
    if pause_during_generation:
        assert result["sent"] == 0
        assert result["skipped"] == 1
        assert getattr(user, stamp) == previous_send
        db.commit.assert_not_called()
        event.assert_not_called()
        resend_send.assert_not_called()
    else:
        assert result["sent"] == 1
        assert getattr(user, stamp) > previous_send
        db.commit.assert_called_once()
        event.assert_called_once()
        resend_send.assert_called_once()


def test_internal_report_remains_available_while_user_emails_are_paused(monkeypatch, resend_send):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", True)
    monkeypatch.setattr(email, "generate_weekly_pending_books_report", lambda db: "<p>Report</p>")
    result = email.send_weekly_pending_books_email(Mock(), recipient="admin@example.test")
    assert result["status"] == "success"
    resend_send.assert_called_once()


@pytest.mark.parametrize("kind", ["recommendations", "learning_tip"])
def test_scheduled_jobs_honor_pause(monkeypatch, resend_send, kind):
    from app import scheduler

    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", True)
    db = Mock()
    monkeypatch.setattr(scheduler, "SessionLocal", lambda: db)
    job = (scheduler.send_recommendation_emails_job if kind == "recommendations"
           else scheduler.send_learning_tip_emails_job)
    job()
    db.query.assert_not_called()
    db.commit.assert_not_called()
    db.close.assert_called_once()
    resend_send.assert_not_called()


@pytest.fixture
def admin_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.auth import require_admin_user
    from app.database import get_db
    from app.routers.admin_analytics import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="test-user")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(id="admin")
    return TestClient(app), db, app


@pytest.mark.parametrize("path", ["send-recommendation-emails", "send-learning-tip-emails"])
@pytest.mark.parametrize("params", [{}, {"force": "true", "only_email": "reader@example.test"}])
def test_admin_send_routes_cannot_bypass_pause(monkeypatch, resend_send, admin_client, path, params):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", True)
    client, db, _ = admin_client
    response = client.post(f"/api/admin/{path}", params=params)
    assert response.status_code == 200
    assert response.json() == {"status": "paused", "eligible": 0, "sent": 0, "skipped": 0, "errors": 0}
    db.commit.assert_not_called()
    resend_send.assert_not_called()


@pytest.mark.parametrize("paused", [True, False])
def test_admin_can_inspect_pause_without_sending(monkeypatch, resend_send, admin_client, paused):
    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", paused)
    client, db, _ = admin_client
    response = client.get("/api/admin/email-status")
    assert response.status_code == 200
    assert response.json() == {"user_emails_paused": paused}
    assert db.mock_calls == []
    resend_send.assert_not_called()


def test_email_status_requires_authentication(admin_client):
    from app.core.auth import require_admin_user

    client, _, app = admin_client
    del app.dependency_overrides[require_admin_user]
    response = client.get("/api/admin/email-status")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("paused", [True, False])
def test_scheduler_reports_runtime_pause_without_sending(monkeypatch, resend_send, caplog, paused):
    from app import scheduler

    monkeypatch.setattr(settings, "USER_EMAILS_PAUSED", paused)
    monkeypatch.setattr(scheduler, "scheduler", None)
    fake_scheduler = Mock()
    monkeypatch.setattr(scheduler, "BackgroundScheduler", lambda: fake_scheduler)
    with caplog.at_level("INFO", logger="app.scheduler"):
        scheduler.start_scheduler()
    assert f"User email delivery paused={paused}" in caplog.text
    assert fake_scheduler.add_job.call_count == 3
    fake_scheduler.start.assert_called_once()
    resend_send.assert_not_called()
