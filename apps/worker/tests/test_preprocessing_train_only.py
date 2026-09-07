import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from app.pipeline.models import build_model_pipeline


def test_preprocessing_statistics_come_from_training_only() -> None:
    X_train = pd.DataFrame(
        {
            "age": [10.0, 12.0, 14.0, np.nan],
            "sex": ["F", "M", "F", "F"],
        },
        index=["p1", "p2", "p3", "p4"],
    )
    y_train = pd.Series([0, 1, 0, 1], index=X_train.index)
    X_test = pd.DataFrame({"age": [1000.0], "sex": ["M"]}, index=["p5"])

    pipeline = build_model_pipeline(LogisticRegression(max_iter=1000), X_train)
    pipeline.fit(X_train, y_train)
    _ = pipeline.predict_proba(X_test)

    numeric_transformer = pipeline.named_steps["preprocessor"].named_transformers_["numeric"]
    imputer = numeric_transformer.named_steps["imputer"]
    scaler = numeric_transformer.named_steps["scaler"]

    assert float(imputer.statistics_[0]) == 12.0
    assert float(scaler.mean_[0]) == 12.0
