

from typing import List, Tuple, Dict, Sequence, Optional, Any, Callable, Union, TypeVar, Literal
from typing_extensions import TypeAlias

import os


Number: TypeAlias = Union[int, float]

import numpy as np

array1D: TypeAlias = np.ndarray
array2D: TypeAlias = np.ndarray

PathLike: TypeAlias = Union[str, os.PathLike]

