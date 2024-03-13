
from typing import Dict, Any, List, Optional, Union, Callable, Tuple, Literal


from dataclasses import dataclass
import warnings

import numpy as np

from .aliases import array1D, array2D, TypeAlias, PathLike
from .files import mkdir_of_file

from .crossovers import Crossover, CrossoverFunc
from .mutations import Mutations, MutationIntFunc, MutationFloatFunc
from .selections import Selection, SelectionFunc

from .utils import can_be_prob, union_to_matrix


class DictLikeGetSet:
    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def get(self, item):
        return getattr(self, item)



_algorithm_params_slots = {
    'max_num_iteration',
    'max_iteration_without_improv',
    'population_size',
    'mutation_probability',
    'mutation_discrete_probability',
    'elit_ratio',
    'crossover_probability',
    'parents_portion',
    'crossover_type',
    'mutation_type',
    'mutation_discrete_type',
    'selection_type'
}


@dataclass
class AlgorithmParams(DictLikeGetSet):

    max_num_iteration: Optional[int] = None
    max_iteration_without_improv: Optional[int] = None

    population_size: int = 100

    mutation_probability: float = 0.1
    mutation_discrete_probability: Optional[float] = None

    #  deprecated
    crossover_probability: Optional[float] = None

    elit_ratio: float = 0.04
    parents_portion: float = 0.3

    crossover_type: Union[str, CrossoverFunc] = 'uniform'
    mutation_type: Union[str, MutationFloatFunc] = 'uniform_by_center'
    mutation_discrete_type: Union[str, MutationIntFunc] = 'uniform_discrete'
    selection_type: Union[str, SelectionFunc] = 'roulette'

    __annotations__ = {
        'max_num_iteration': Optional[int],
        'max_iteration_without_improv': Optional[int],
        'population_size': int,
        'mutation_probability': float,
        'mutation_discrete_probability': Optional[float],
        'crossover_probability': Optional[float],
        'elit_ratio': float,
        'parents_portion': float,
        'crossover_type': Union[str, CrossoverFunc],
        'mutation_type': Union[str, MutationFloatFunc],
        'mutation_discrete_type': Union[str, MutationIntFunc],
        'selection_type': Union[str, SelectionFunc]
    }

    def check_if_valid(self) -> None:

        assert int(self.population_size) > 0, f"population size must be integer and >0, not {self.population_size}"
        assert (can_be_prob(self.parents_portion)), "parents_portion must be in range [0,1]"
        assert (can_be_prob(self.mutation_probability)), "mutation_probability must be in range [0,1]"
        assert (can_be_prob(self.elit_ratio)), "elit_ratio must be in range [0,1]"

        if self.max_iteration_without_improv is not None and self.max_iteration_without_improv < 1:
            warnings.warn(
                f"max_iteration_without_improv is {self.max_iteration_without_improv} but must be None or int > 0"
            )
            self.max_iteration_without_improv = None

    def get_CMS_funcs(self) -> Tuple[
        CrossoverFunc,
        MutationFloatFunc,
        MutationIntFunc,
        SelectionFunc
    ]:
        """
        returns gotten crossover, mutation, discrete mutation, selection
        as necessary functions
        """

        result: List[Callable] = []
        for name, value, dct in (
            ('crossover', self.crossover_type, Crossover.crossovers_dict()),
            ('mutation', self.mutation_type, Mutations.mutations_dict()),
            ('mutation_discrete', self.mutation_discrete_type, Mutations.mutations_discrete_dict()),
            ('selection', self.selection_type, Selection.selections_dict())
        ):
            if isinstance(value, str):
                if value not in dct:
                    raise ValueError(
                        f"unknown name of {name}: '{value}', must be from {tuple(dct.keys())} or a custom function"
                    )
                result.append(dct[value])
            else:
                assert callable(value), f"{name} must be string or callable"
                result.append(value)

        return tuple(result)

    @staticmethod
    def from_dict(dct: Dict[str, Any]):

        result = AlgorithmParams()

        for name, value in dct.items():
            if name not in _algorithm_params_slots:
                raise AttributeError(f"name '{name}' does not exists in AlgorithmParams fields")

            setattr(result, name, value)
        return result


GenerationConvertible: TypeAlias = Union[
    'Generation',
    str,
    Dict[Literal['population', 'scores'], Union[array2D, array1D]],
    array2D,
    Tuple[
        Optional[array2D],
        Optional[array1D]
    ]
]


@dataclass
class Generation(DictLikeGetSet):
    variables: Optional[array2D] = None
    scores: Optional[array1D] = None

    __annotations__ = {
        'variables': Optional[array2D],
        'scores': Optional[array1D]
    }

    def __check_dims(self) -> None:
        if self.variables is not None:
            assert len(self.variables.shape) == 2, (
                f"'variables' must be matrix with shape (objects, dimensions), not {self.variables.shape}"
            )
            if self.scores is not None:
                assert len(self.scores.shape) == 1, f"'scores' must be 1D-array, not with shape {self.scores.shape}"
                assert self.variables.shape[0] == self.scores.size, (
                    f"count of objects ({self.variables.shape[0]}) "
                    f"must be equal to count of scores ({self.scores.size})"
                )

    @property
    def size(self) -> int:
        return self.scores.size

    @property
    def dim_size(self) -> int:
        return self.variables.shape[1]

    def as_wide_matrix(self) -> array2D:
        # should not be used in main code -- was needed for old versions
        return union_to_matrix(self.variables, self.scores)

    def save(self, path: PathLike):
        mkdir_of_file(path)
        np.savez(path, population=self.variables, scores=self.scores)

    @staticmethod
    def load(path: PathLike):
        try:
            st = np.load(path)
        except Exception as err:
            raise Exception(
                f"if generation object is a string, "
                f"it must be path to npz file with needed content, but raised exception {repr(err)}"
            )

        assert 'population' in st and 'scores' in st, (
            "saved generation object must contain 'population' and 'scores' fields"
        )

        return Generation(variables=st['population'], scores=st['scores'])

    @staticmethod
    def from_object(
        dim: int,
        object: GenerationConvertible
    ):

        obj_type = type(object)

        if obj_type == str:

            generation = Generation.load(object)

        elif obj_type == np.ndarray:

            assert len(object.shape) == 2 and (object.shape[1] == dim or object.shape[1] == dim + 1), (
                f"if start_generation is numpy array, "
                f"it must be with shape (samples, dim) or (samples, dim+1), not {object.shape}"
            )

            generation = Generation(object, None) if object.shape[1] == dim else Generation.from_pop_matrix(object)

        elif obj_type == tuple:

            assert len(object) == 2, (
                f"if start_generation is tuple, "
                f"it must be tuple with 2 components, not {len(object)}"
            )

            variables, scores = object

            assert ( (variables is None or scores is None) or (variables.shape[0] == scores.size)), (
                "start_generation object must contain variables and scores components "
                "which are None or 2D- and 1D-arrays with same shape"
            )

            generation = Generation(variables=variables, scores=scores)

        elif obj_type == dict:
            assert (
                ('variables' in object and 'scores' in object) and
                (object['variables'] is None or object['scores'] is None) or
                (object['variables'].shape[0] == object['scores'].size)
            ), (
                "start_generation object must contain 'variables' and 'scores' keys "
                "which are None or 2D- and 1D-arrays with same shape"
            )

            generation = Generation(variables=object['variables'], scores=object['scores'])

        elif obj_type == Generation:
            generation = Generation(variables=object['variables'], scores=object['scores'])
        else:
            raise TypeError(
                f"invalid type of generation! "
                f"Must be in (Union[str, Dict[str, np.ndarray], Generation, np.ndarray, "
                f"Tuple[Optional[np.ndarray], Optional[np.ndarray]]]), "
                f"not {obj_type}"
            )

        generation.__check_dims()

        if generation.variables is not None:
            assert generation.dim_size == dim, (
                f"generation dimension size {generation.dim_size} does not equal to target size {dim}"
            )

        return generation

    @staticmethod
    def from_pop_matrix(pop: array2D):
        warnings.warn("depricated! pop matrix style will be removed at version 7, use samples and scores separetly")
        return Generation(
            variables=pop[:, :-1],
            scores=pop[:, -1]
        )


@dataclass
class GAResult(DictLikeGetSet):

    last_generation: Generation

    __annotations__ = {
        'last_generation': Generation
    }

    @property
    def variable(self) -> array1D:
        return self.last_generation.variables[0]

    @property
    def score(self) -> float:
        return self.last_generation.scores[0]

    @property
    def function(self):
        warnings.warn(
            f"'function' field is deprecated, will be removed in version 7, use 'score' to get best population score"
        )
        return self.score


@dataclass
class MiddleCallbackData(DictLikeGetSet):
    """
    data object using with middle callbacks
    """

    reason_to_stop: Optional[str]

    last_generation: Generation

    current_generation: int
    report_list: List[float]

    mutation_prob: float
    mutation_discrete_prob: float

    mutation: MutationFloatFunc
    mutation_discrete: MutationIntFunc
    crossover: CrossoverFunc
    selection: SelectionFunc

    current_stagnation: int
    max_stagnation: int

    parents_portion: float
    elit_ratio: float

    set_function: Callable[[array2D], array1D]
    
    __annotations__ = {
        'reason_to_stop': Optional[str],
        'last_generation': Generation,
        'current_generation': int,
        'report_list': List[float],
        'mutation_prob': float,
        'mutation_discrete_prob': float,
        'mutation': MutationFloatFunc,
        'mutation_discrete': MutationIntFunc,
        'crossover': CrossoverFunc,
        'selection': SelectionFunc,
        'current_stagnation': int,
        'max_stagnation': int,
        'parents_portion': float,
        'elit_ratio': float,
        'set_function': Callable[[array2D], array1D]
    }














