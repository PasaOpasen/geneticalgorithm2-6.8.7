
from typing import Optional, Any, Tuple

from pathlib import Path

import random
import numpy as np

from .aliases import array1D, array2D


def fast_min(a, b):
    '''
    1.5 times faster than row min(a, b)
    '''
    return a if a < b else b


def fast_max(a, b):
    return a if a > b else b


def can_be_prob(value: float) -> bool:
    return 0 <= value <= 1


def is_current_gen_number(number: Optional[int]):
    return (number is None) or (type(number) == int and number > 0)


def is_numpy(arg: Any):
    return isinstance(arg, np.ndarray)


def split_matrix(mat: array2D) -> Tuple[array2D, array1D]:
    """
    splits wide pop matrix to variables and scores
    """
    return mat[:, :-1], mat[:, -1]


def union_to_matrix(variables_2D: array2D, scores_1D: array1D) -> array2D:
    """
    union variables and scores to wide pop matrix
    """
    return np.hstack((variables_2D, scores_1D[:, np.newaxis]))


def random_indexes_pair(seq_len: int) -> Tuple[int, int]:
    """works 3 times faster than `random.sample(range(seq_len), 2)`"""
    a = random.randrange(seq_len)
    b = random.randrange(seq_len)
    if a == b:
        while a == b:
            b = random.randrange(seq_len)
    return a, b













