import pandas as pd
import pytest

from ltverify.contracts import DataContractError, validate_columns


def test_validate_columns_names_missing_fields() -> None:
    frame = pd.DataFrame({"timestamp": []})
    with pytest.raises(DataContractError, match="measurements missing columns: transformer_id"):
        validate_columns(frame, {"timestamp", "transformer_id"}, "measurements")
