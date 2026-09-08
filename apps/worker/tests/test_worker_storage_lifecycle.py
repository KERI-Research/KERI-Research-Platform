from io import BytesIO
from threading import Event
from time import monotonic
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.schemas import (
    AnalysisConfig,
    JobRequest,
    JobResult,
    JobStatus,
    StoragePresignDownloadRequest,
)
from app.synthetic import generate_synthetic_dataset


def _archive_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("participants.csv", "patient_id,sex,age\nSYN-1,F,60\n")
        archive.writestr(
            "observations.csv",
            "patient_id,variable_code,value,observed_at,unit\nSYN-1,lab_a,1,2024-01-01T00:00:00Z,u/L\n",
        )
        archive.writestr(
            "outcomes.csv",
            "patient_id,outcome_code,outcome_at,label\nSYN-1,synthetic,2025-01-01T00:00:00Z,1\n",
        )
        archive.writestr(
            "encounters.csv",
            "patient_id,encountered_at,encounter_type\nSYN-1,2024-01-02T00:00:00Z,consultation\n",
        )
        archive.writestr(
            "data_dictionary.json", '[{"variable_code":"lab_a","unit":"u/L"}]'
        )
    return buffer.getvalue()


def test_storage_backed_request_loads_the_private_upload(monkeypatch) -> None:
    monkeypatch.setattr(main, "download_bytes", lambda _key: _archive_bytes())
    request = JobRequest(
        job_id="job-storage-input",
        dataset_object_key="uploads/upl-test/synthetic.zip",
        dataset_filename="synthetic.zip",
        analysis_config=AnalysisConfig(analysis_locked=True),
    )

    dataset = main._dataset_for_request(request)

    assert dataset.participants[0].patient_id == "SYN-1"
    assert dataset.observations[0].variable_code == "lab_a"


def test_pipeline_writes_all_job_scoped_report_artifacts(monkeypatch) -> None:
    uploads: dict[str, bytes] = {}
    monkeypatch.setattr(
        main,
        "upload_bytes",
        lambda key, data, _content_type: uploads.__setitem__(key, data),
    )
    request = JobRequest(
        job_id="job-artifacts",
        dataset_id="dataset-artifacts",
        dataset=generate_synthetic_dataset(n_patients=20),
        result_write_prefix="results/job-artifacts",
        analysis_config=AnalysisConfig(horizons=[30], analysis_locked=True),
    )

    result = main._run_pipeline(request)

    assert set(uploads) == {
        "results/job-artifacts/report.json",
        "results/job-artifacts/report.md",
        "results/job-artifacts/report.html",
        "results/job-artifacts/model-card.md",
    }
    assert result.report_references[0] == "storage:results/job-artifacts/report.json"


def test_raw_uploads_cannot_be_signed_for_download(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "generate_presigned_download_url",
        lambda key: f"https://example.invalid/{key}",
    )

    with pytest.raises(HTTPException, match="Only result artifacts"):
        main.presign_download(
            StoragePresignDownloadRequest(object_key="uploads/upl-test/synthetic.zip"),
            None,
        )


def test_run_endpoint_queues_then_exposes_terminal_status(monkeypatch) -> None:
    monkeypatch.setenv("ORAMA_WORKER_SHARED_SECRET", "worker-test-secret")
    main.job_store._jobs.clear()
    completed_result = JobResult(
        feasibility_conclusion="NO_GO",
        decision_reasons=["Synthetic test result."],
        metrics_by_horizon={},
        report_json={},
        report_markdown="report",
    )
    monkeypatch.setattr(main, "_run_pipeline", lambda _request: completed_result)

    client = TestClient(main.app)
    response = client.post(
        "/internal/jobs/run",
        headers={"X-Orama-Worker-Secret": "worker-test-secret"},
        json={
            "job_id": "job-queued-lifecycle",
            "dataset": generate_synthetic_dataset(n_patients=20).model_dump(
                mode="json"
            ),
            "analysis_config": {"analysis_locked": True},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.QUEUED
    assert response.json()["progress"] == {
        "percent": 0,
        "phase": "queued",
        "detail": "Job accepted by worker. It will start when one of the 2 processing slots is available.",
    }
    status_response = client.get(
        "/internal/jobs/job-queued-lifecycle",
        headers={"X-Orama-Worker-Secret": "worker-test-secret"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == JobStatus.SUCCEEDED
    assert status_response.json()["progress"]["percent"] == 100
    assert status_response.json()["progress"]["phase"] == "complete"


def test_private_dashboard_renders_current_job_progress() -> None:
    main.job_store._jobs.clear()
    main.job_store.create_or_reset("job-dashboard", "Queued for a processing slot.")
    main.job_store.update_progress(
        "job-dashboard", 42, "model", "90-day horizon: fitting M2."
    )

    response = TestClient(main.app).get("/")

    assert response.status_code == 200
    assert "Private synthetic research job progress" in response.text
    assert "job-dashboard" in response.text
    assert "42%" in response.text
    assert "90-day horizon: fitting M2." in response.text


def test_third_job_waits_for_a_processing_slot(monkeypatch) -> None:
    monkeypatch.setenv("ORAMA_WORKER_SHARED_SECRET", "worker-test-secret")
    main.job_store._jobs.clear()
    started = Event()
    release = Event()
    started_count = 0

    def blocked_execute(request: JobRequest) -> None:
        nonlocal started_count
        started_count += 1
        if started_count == main.MAX_CONCURRENT_JOBS:
            started.set()
        release.wait(timeout=5)
        main.job_store.transition(
            request.job_id,
            JobStatus.SUCCEEDED,
            message="Synthetic queued job completed.",
        )

    monkeypatch.setattr(main, "_execute_job", blocked_execute)
    client = TestClient(main.app)
    job_payload = {
        "dataset": generate_synthetic_dataset(n_patients=20).model_dump(mode="json"),
        "analysis_config": {"analysis_locked": True},
    }

    for job_id in ("job-slot-1", "job-slot-2", "job-slot-3"):
        response = client.post(
            "/internal/jobs/run",
            headers={"X-Orama-Worker-Secret": "worker-test-secret"},
            json={"job_id": job_id, **job_payload},
        )
        assert response.status_code == 200

    assert started.wait(timeout=2)
    assert main.job_store.get("job-slot-3").status == JobStatus.QUEUED

    release.set()
    deadline = monotonic() + 2
    while main.job_store.get("job-slot-3").status == JobStatus.QUEUED:
        if monotonic() >= deadline:
            pytest.fail("Queued job did not start after a processing slot opened.")
