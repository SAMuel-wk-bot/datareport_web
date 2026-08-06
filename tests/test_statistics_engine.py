import numpy as np
import pandas as pd
import pytest

from statistics_engine import descriptive, matrix, scalar


def test_descriptive_operations_show_steps():
    result = descriptive("mean", pd.Series([2, 4, 6, 8]))
    assert result["result"] == 5
    assert result["formula"]
    assert len(result["steps"]) >= 3


def test_weighted_mean():
    result = descriptive("weighted_mean", pd.Series([80, 90]), pd.Series([1, 3]))
    assert result["result"] == 87.5


def test_matrix_inverse_and_multiplication():
    inverse = matrix("inverse", "1,2\n3,4")["result"]
    assert np.allclose(inverse, [[-2, 1], [1.5, -0.5]])
    product = matrix("multiply", "1,2\n3,4", "2,0\n1,2")["result"]
    assert product == [[4, 4], [10, 8]]


def test_scalar_validation():
    assert scalar("square", 12)["result"] == 144
    with pytest.raises(ValueError):
        scalar("sqrt", -1)
