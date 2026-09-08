import pandas as pd

from app.pipeline.models import _static_feature_manifest


def test_static_feature_manifest_marks_pre_index_static_features() -> None:
    static_features = pd.DataFrame(
        {
            "age": [60.0],
            "sex": ["F"],
            "encounter_count": [3],
            "static__haemoglobin__last_value": [128.0],
            "static__haemoglobin__days_since_last_measurement": [12.0],
        },
        index=["SYN-0001"],
    )

    manifest = {
        entry["feature"]: entry for entry in _static_feature_manifest(static_features)
    }

    assert manifest["age"]["feature_set"] == "static_only"
    assert (
        manifest["static__haemoglobin__last_value"]["source_variable"] == "haemoglobin"
    )
    assert all(entry["pre_index_only"] is True for entry in manifest.values())
