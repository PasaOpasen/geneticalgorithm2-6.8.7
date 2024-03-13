"""
Copyright 2021 Demetry Pascal (forked from Ryan (Mohammad) Solgi)

Permission is hereby granted, free of charge, to any person obtaining a copy of 
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to use, 
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the 
Software, and to permit persons to whom the Software is furnished to do so, 
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
SOFTWARE.
"""


from typing import Callable, List, Tuple, Optional, Dict, Any, Union, Sequence, Set, Literal
from typing_extensions import TypeAlias

import collections
import warnings
import operator


import sys
import time
import random
import math

import numpy as np

#region INTERNAL IMPORTS

from .aliases import array1D, array2D

from .classes import AlgorithmParams, Generation, MiddleCallbackData, GAResult, GenerationConvertible

from .initializer import Population_initializer
from .plotting_tools import plot_pop_scores, plot_several_lines

from .utils import can_be_prob, is_numpy, is_current_gen_number, fast_min, random_indexes_pair

from .callbacks import MiddleCallbackFunc, CallbackFunc

#endregion

#region ALIASES

VARIABLE_TYPE: TypeAlias = Literal['int', 'real', 'bool']

#endregion


class geneticalgorithm2:
    
    """
    Genetic Algorithm (Elitist version) for Python
    
    An implementation of elitist genetic algorithm for solving problems with
    continuous, integers, or mixed variables.
    
    repo path https://github.com/PasaOpasen/geneticalgorithm2
    """
    
    default_params = AlgorithmParams()
    PROGRESS_BAR_LEN = 20

    @property
    def output_dict(self):
        warnings.warn(
            "'output_dict' is deprecated and will be removed at version 7 \n use 'result' instead"
        )
        return self.result

    @property
    def needs_mutation(self) -> bool:
        return self.prob_mut > 0 or self.prob_mut_discrete > 0

    #region INIT

    def __init__(
        self,
        function: Callable[[array1D], float],

        dimension: int,
        variable_type: Union[VARIABLE_TYPE, Sequence[VARIABLE_TYPE]] = 'bool',
        variable_boundaries: Optional[Union[array2D, Sequence[Tuple[float, float]]]] = None,

        variable_type_mixed=None,

        function_timeout: Optional[float] = None,
        algorithm_parameters: Union[AlgorithmParams, Dict[str, Any]] = default_params
    ):
        """
        Args:
            function <Callable[[np.ndarray], float]> - the given objective function to be minimized
            #NOTE: This implementation minimizes the given objective function.
            (For maximization multiply function by a negative sign: the absolute
            value of the output would be the actual objective function)

            dimension <integer> - the number of decision variables

            variable_type <string> - 'bool' if all variables are Boolean;
            'int' if all variables are integer; and 'real' if all variables are
            real value or continuous. For mixed types use sequence of string of type for each variable

            variable_boundaries <Optional[Union[np.ndarray, Sequence[Tuple[float, float]]]]> - Default None; leave it
            None if variable_type is 'bool'; otherwise provide an array of tuples
            of length two as boundaries for each variable;
            the length of the array must be equal dimension. For example,
            np.array([0,100],[0,200]) determines lower boundary 0 and upper boundary 100 for first
            and upper boundary 200 for second variable where dimension is 2.

            variable_type_mixed -- deprecated

            function_timeout <float> - if the given function does not provide
            output before function_timeout (unit is seconds) the algorithm raise error.
            For example, when there is an infinite loop in the given function. `None` means disabling

            algorithm_parameters <Union[AlgorithmParams, Dict[str, Any]]>:
                @ max_num_iteration <int> - stoping criteria of the genetic algorithm (GA)
                @ population_size <int>
                @ mutation_probability <float in [0,1]>
                @ elit_ratio <float in [0,1]>
                @ crossover_probability <float in [0,1]>
                @ parents_portion <float in [0,1]>
                @ crossover_type <string/function> - Default is 'uniform'; 'one_point' or 'two_point' (not only) are other options
                @ mutation_type <string/function> - Default is 'uniform_by_x'; see GitHub to check other options
                @ mutation_discrete_type <string/function> - mutation type for discrete variables
                @ selection_type <string/function> - Default is 'roulette'; see GitHub to check other options
                @ max_iteration_without_improv <int> - maximum number of successive iterations without improvement. If None it is ineffective

        for more details and examples of implementation please visit:
            https://github.com/PasaOpasen/geneticalgorithm2
  
        """

        # all default fields

        self.param: AlgorithmParams = None
        # self.crossover: Callable[[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]] = None
        # self.real_mutation: Callable[[float, float, float], float] = None
        # self.discrete_mutation: Callable[[int, int, int], int] = None
        # self.selection: Callable[[np.ndarray, int], np.ndarray] = None

        self.f: Callable[[array1D], float] = None
        self.funtimeout: float = None
        self.set_function: Callable[[np.ndarray], np.ndarray] = None

        # self.dim: int = None
        self.var_bounds: List[Tuple[Union[int, float], Union[int, float]]] = None
        # self.indexes_int: np.ndarray = None
        # self.indexes_float: np.ndarray = None

        self.checked_reports: List[Tuple[str, Callable[[array1D], None]]] = None

        self.population_size: int = None
        self.progress_stream = None

        # input algorithm's parameters

        assert isinstance(algorithm_parameters, (dict, AlgorithmParams)), (
            "algorithm_parameters must be dict or AlgorithmParams object"
        )
        if not isinstance(algorithm_parameters, AlgorithmParams):
            algorithm_parameters = AlgorithmParams.from_dict(algorithm_parameters)

        algorithm_parameters.check_if_valid()
        self.param = algorithm_parameters
        self.crossover, self.real_mutation, self.discrete_mutation, self.selection = algorithm_parameters.get_CMS_funcs()

        # dimension and area bounds
        self.dim = int(dimension)
        assert self.dim > 0, f"dimension count must be int and >0, gotten {dimension}"

        if variable_type_mixed is not None:
            warnings.warn(
                f"argument variable_type_mixed is deprecated and will be removed at version 7\n "
                f"use variable_type={tuple(variable_type_mixed)} instead"
            )
            variable_type = variable_type_mixed
        self._set_types_indexes(variable_type)  # types indexes
        self._set_var_boundaries(variable_type, variable_boundaries)  # input variables' boundaries

        # fix mutation probs

        assert can_be_prob(self.param.mutation_probability)
        self.prob_mut = self.param.mutation_probability
        assert self.param.mutation_discrete_probability is None or can_be_prob(self.param.mutation_discrete_probability)
        self.prob_mut_discrete = self.param.mutation_discrete_probability or self.prob_mut

        if self.param.crossover_probability is not None:
            warnings.warn(
                f"crossover_probability is deprecated and will be removed in version 7. "
                f"Reason: it's old and has no sense"
            )

        #############################################################
        # input function
        assert (callable(function)), "function must be callable!"
        self.f = function

        if function_timeout is not None and function_timeout > 0:
            try:
                from func_timeout import func_timeout, FunctionTimedOut
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "function_timeout > 0 needs additional package func_timeout\n"
                    "run `python -m pip install func_timeout`\n"
                    "or disable this parameter: function_timeout=None"
                )

        self.funtimeout = None if function_timeout is None else float(function_timeout)

        #############################################################
        
        self.population_size = int(self.param.population_size)
        self._set_parents_count(self.param.parents_portion)
        self._set_elit_count(self.population_size, self.param.elit_ratio)
        assert self.parents_count >= self.elit_count, (
            f"\n number of parents ({self.parents_count}) must be greater than number of elits ({self.elit_count})"
        )

        self._set_max_iterations()

        self._set_report()

        # specify this function to speed up or change default behaviour
        self.fill_children: Optional[Callable[[array2D, int], None]] = None
        """
        custom function which adds children for population POP 
            where POP[:parents_count] are parents lines and next lines are for children
        """

    def _set_types_indexes(self, variable_type: Union[str, Sequence[str]]):

        indexes = np.arange(self.dim)
        self.indexes_int = np.array([])
        self.indexes_float = np.array([])

        assert_message = (
            f"\n variable_type must be 'bool', 'int', 'real' or a sequence with 'int' and 'real', got {variable_type}"
        )

        if isinstance(variable_type, str):
            assert (variable_type in VARIABLE_TYPE.__args__), assert_message
            if variable_type == 'real':
                self.indexes_float = indexes
            else:
                self.indexes_int = indexes

        else:  # sequence case

            assert len(variable_type) == self.dim, (
                f"\n variable_type must have a length equal dimension. "
                f"Should be {self.dim}, got {len(variable_type)}"
            )
            assert 'bool' not in variable_type, (
                "don't use 'bool' if variable_type is a sequence, "
                "for 'boolean' case use 'int' and specify boundary as (0,1)"
            )
            assert all(v in VARIABLE_TYPE.__args__ for v in variable_type), assert_message

            vartypes = np.array(variable_type)
            self.indexes_int = indexes[vartypes == 'int']
            self.indexes_float = indexes[vartypes == 'real']

    def _set_var_boundaries(
        self,
        variable_type: Union[str, Sequence[str]],
        variable_boundaries
    ):
        if isinstance(variable_type, str) and variable_type == 'bool':
            self.var_bounds = [(0, 1)] * self.dim
        else:

            if is_numpy(variable_boundaries):
                assert variable_boundaries.shape == (self.dim, 2), (
                    f"\n if variable_boundaries is numpy array, it must be with shape (dim, 2)"
                )
            else:
                assert len(variable_boundaries) == self.dim and all((len(t) == 2 for t in variable_boundaries)), (
                    "\n if variable_boundaries is sequence, "
                    "it must be with len dim and boundary for each variable must be a tuple of length two"
                )

            for i in variable_boundaries:
                assert i[0] <= i[1], "\n lower_boundaries must be smaller than upper_boundaries [lower,upper]"

            self.var_bounds = [(i[0], i[1]) for i in variable_boundaries]

    def _set_parents_count(self, parents_portion: float):

        self.parents_count = int(parents_portion * self.population_size)
        assert self.population_size >= self.parents_count > 1, (
            f'parents count {self.parents_count} cannot be less than population size {self.population_size}'
        )
        trl = self.population_size - self.parents_count
        if trl % 2 != 0:
            self.parents_count += 1

    def _set_elit_count(self, pop_size: int, elit_ratio: Union[float, int]):

        assert elit_ratio >= 0
        self.elit_count = elit_ratio if isinstance(elit_ratio, str) else math.ceil(pop_size*elit_ratio)

    def _set_max_iterations(self):

        if self.param.max_num_iteration is None:
            iterate = 0
            for i in range(0, self.dim):
                bound_min, bound_max = self.var_bounds[i]
                var_space = bound_max - bound_min
                if i in self.indexes_int:
                    iterate += var_space * self.dim * (100 / self.population_size)
                else:
                    iterate += var_space * 50 * (100 / self.population_size)
            iterate = int(iterate)
            if (iterate * self.population_size) > 10000000:
                iterate = 10000000 / self.population_size

            self.max_iterations = fast_min(iterate, 8000)
        else:
            assert self.param.max_num_iteration > 0
            self.max_iterations = math.ceil(self.param.max_num_iteration)

        max_it = self.param.max_iteration_without_improv
        if max_it is None:
            self.max_stagnations = self.max_iterations + 1
        else:
            self.max_stagnations = math.ceil(max_it)

    #endregion

    #region REPORT

    def _set_report(self):
        """
        creates default report checker
        """
        self.checked_reports = [
            # item 0 cuz scores will be sorted and min item is items[0]
            ('report', operator.itemgetter(0))
        ]

    def _clear_report(self):
        """
        removes all report objects
        """
        fields = [f for f in vars(self).keys() if f.startswith('report')]
        for attr in fields:
            delattr(self, attr)

    def _init_report(self):
        """
        makes empty report fields
        """
        for name, _ in self.checked_reports:
            setattr(self, name, [])

    def _update_report(self, scores: array1D):
        """
        append report value to the end of field
        """
        for name, func in self.checked_reports:
            getattr(self, name).append(
                func(scores)
            )

    #endregion

    #region RUN METHODS

    def _progress(self, count: int, total: int, status: str = ''):

        part = count / total

        filled_len = round(geneticalgorithm2.PROGRESS_BAR_LEN * part)
        percents = round(100.0 * part, 1)
        bar = '|' * filled_len + '_' * (geneticalgorithm2.PROGRESS_BAR_LEN - filled_len)

        self.progress_stream.write('\r%s %s%s %s' % (bar, percents, '%', status))
        self.progress_stream.flush()

    def __str__(self):
        return f"Genetic algorithm object with parameters {self.param}"

    def __repr__(self):
        return self.__str__()

    def _simulate(self, sample: array1D):

        from func_timeout import func_timeout, FunctionTimedOut

        obj = None
        eval_time = time.time()
        try:
            obj = func_timeout(
                self.funtimeout,
                lambda: self.f(sample)
            )
        except FunctionTimedOut:
            print("given function is not applicable")
        eval_time = time.time() - eval_time

        assert obj is not None, (
            f"the given function was running like {eval_time} seconds and does not provide any output"
        )

        tp = type(obj)
        assert (
            tp in (int, float) or np.issubdtype(tp, np.floating) or np.issubdtype(tp, np.integer)
        ), f"Minimized function should return a number, but got '{obj}' object with type {tp}"

        return obj, eval_time

    def _set_mutation_indexes(self, mutation_indexes: Optional[Sequence[int]]):

        if mutation_indexes is None:
            self.indexes_float_mut = self.indexes_float
            self.indexes_int_mut = self.indexes_int
        else:
            tmp_indexes = set(mutation_indexes)
            self.indexes_int_mut = np.array(list(set(self.indexes_int).intersection(tmp_indexes)))
            self.indexes_float_mut = np.array(list(set(self.indexes_float).intersection(tmp_indexes)))

            if self.indexes_float_mut.size == 0 and self.indexes_int_mut.size == 0:
                warnings.warn(f"No mutation dimensions!!! Check ur mutation indexes!!")

    #@profile
    def run(
        self,
        no_plot: bool = False,
        disable_printing: bool = False,
        progress_bar_stream: Optional[str] = 'stdout',

        # deprecated
        disable_progress_bar: bool = False,

        set_function: Optional[Callable[[array2D], array1D]] = None,
        apply_function_to_parents: bool = False,
        start_generation: GenerationConvertible = Generation(),
        studEA: bool = False,
        mutation_indexes: Optional[Union[Sequence[int], Set[int]]] = None,

        init_creator: Optional[Callable[[], array1D]] = None,
        init_oppositors: Optional[Sequence[Callable[[array1D], array1D]]] = None,

        duplicates_oppositor: Optional[Callable[[array1D], array1D]] = None,
        remove_duplicates_generation_step: Optional[int] = None,

        revolution_oppositor: Optional[Callable[[array1D], array1D]] = None,
        revolution_after_stagnation_step: Optional[int] = None,
        revolution_part: float = 0.3,

        population_initializer: Tuple[
            int, Callable[[array2D, array1D], Tuple[array2D, array1D]]
        ] = Population_initializer(select_best_of=1, local_optimization_step='never', local_optimizer=None),

        stop_when_reached: Optional[float] = None,
        callbacks: Optional[Sequence[CallbackFunc]] = None,
        middle_callbacks: Optional[Sequence[MiddleCallbackFunc]] = None,  #+
        time_limit_secs: Optional[float] = None,
        save_last_generation_as: Optional[str] = None,
        seed: Optional[int] = None
    ):
        """
        runs optimization process

        Args:
            no_plot: do not plot results using matplotlib by default

            disable_printing: do not print log info of optimization process

            progress_bar_stream: 'stdout', 'stderr' or None to disable progress bar

            disable_progress_bar:

            set_function : 2D-array -> 1D-array function,
                which applyes to matrix of population (size (samples, dimention))
                    to estimate their values

            apply_function_to_parents: apply function to parents from previous generation (if it's needed)

            start_generation: Generation object or a dictionary with structure
                {'variables':2D-array of samples, 'scores': function values on samples}
                or path to .npz file (str) with saved generation; if 'scores' value is None the scores will be compute

            studEA: using stud EA strategy (crossover with best object always)

            mutation_indexes: indexes of dimensions where mutation can be performed (all dimensions by default)

            init_creator: the function creates population samples.
                By default -- random uniform for real variables and random uniform for int
            init_oppositors: the list of oppositors creates oppositions for base population. No by default
            duplicates_oppositor: oppositor for applying after duplicates removing.
                By default -- using just random initializer from creator
            remove_duplicates_generation_step: step for removing duplicates (have a sense with discrete tasks).
                No by default
            revolution_oppositor: oppositor for revolution time. No by default
            revolution_after_stagnation_step: create revolution after this generations of stagnation. No by default
            revolution_part: float, the part of generation to being oppose. By default is 0.3

            population_initializer: object for actions at population initialization step
                to create better start population. See doc

            stop_when_reached: stop searching after reaching this value (it can be potential minimum or something else)

            callbacks: sequence of callback functions with structure:
                (generation_number, report_list, last_population, last_scores) -> do some action

            middle_callbacks: sequence of functions made MiddleCallbacks class

            time_limit_secs: limit time of working (in seconds)

            save_last_generation_as: path to .npz file for saving last_generation as numpy dictionary like
                {'population': 2D-array, 'scores': 1D-array}, None if doesn't need to save in file

            seed: random seed (None if doesn't matter)
        """

        if disable_progress_bar:
            warnings.warn(
                f"disable_progress_bar is deprecated and will be removed in version 7, "
                f"use probress_bar_stream=None to disable progress bar"
            )
            progress_bar_stream = None

        enable_printing: bool = not disable_printing

        start_generation = Generation.from_object(self.dim, start_generation)

        assert is_current_gen_number(revolution_after_stagnation_step), "must be None or int and >0"
        assert is_current_gen_number(remove_duplicates_generation_step), "must be None or int and >0"
        assert can_be_prob(revolution_part), f"revolution_part must be in [0,1], not {revolution_part}"
        assert stop_when_reached is None or isinstance(stop_when_reached, (int, float))
        assert isinstance(callbacks, collections.abc.Sequence) or callbacks is None, (
            "callbacks should be a list of callbacks functions"
        )
        assert isinstance(middle_callbacks, collections.abc.Sequence) or middle_callbacks is None, (
            "middle_callbacks should be list of MiddleCallbacks functions"
        )
        assert time_limit_secs is None or time_limit_secs > 0, 'time_limit_secs must be None of number > 0'

        self._set_mutation_indexes(mutation_indexes)
        from OppOpPopInit import set_seed
        set_seed(seed)

        # randomstate = np.random.default_rng(random.randint(0, 1000) if seed is None else seed)
        # self.randomstate = randomstate

        # using bool flag is faster than using empty function with generated string arguments
        SHOW_PROGRESS = progress_bar_stream is not None
        if SHOW_PROGRESS:

            show_progress = lambda t, t2, s: self._progress(t, t2, status=s)

            if progress_bar_stream == 'stdout':
                self.progress_stream = sys.stdout
            elif progress_bar_stream == 'stderr':
                self.progress_stream = sys.stderr
            else:
                raise Exception(
                    f"wrong value {progress_bar_stream} of progress_bar_stream, must be 'stdout'/'stderr'/None"
                )
        else:
            show_progress = None

        stop_by_val = (
            (lambda best_f: False)
            if stop_when_reached is None
            else (lambda best_f: best_f <= stop_when_reached)
        )

        t: int = 0
        count_stagnation: int = 0
        pop: array2D = None
        scores: array1D = None

        #
        #
        # callbacks part
        #
        #

        def get_data():
            """
            returns all important data about model
            """
            return MiddleCallbackData(
                last_generation=Generation(pop, scores),
                current_generation=t,
                report_list=self.report,

                mutation_prob=self.prob_mut,
                mutation_discrete_prob=self.prob_mut_discrete,
                mutation=self.real_mutation,
                mutation_discrete=self.discrete_mutation,
                crossover=self.crossover,
                selection=self.selection,

                current_stagnation=count_stagnation,
                max_stagnation=self.max_stagnations,

                parents_portion=self.param.parents_portion,
                elit_ratio=self.param.elit_ratio,

                set_function=self.set_function,

                reason_to_stop=reason_to_stop
            )

        def set_data(data: MiddleCallbackData):
            """
            sets data to model
            """
            nonlocal pop, scores, count_stagnation, reason_to_stop

            pop, scores = data.last_generation.variables, data.last_generation.scores
            self.population_size = pop.shape[0]

            self.param.parents_portion = data.parents_portion
            self._set_parents_count(data.parents_portion)

            self.param.elit_ratio = data.elit_ratio
            self._set_elit_count(self.population_size, data.elit_ratio)

            self.prob_mut = data.mutation_prob
            self.prob_mut_discrete = data.mutation_discrete_prob
            self.real_mutation = data.mutation
            self.discrete_mutation = data.mutation_discrete
            self.crossover = data.crossover
            self.selection = data.selection

            count_stagnation = data.current_stagnation
            reason_to_stop = data.reason_to_stop
            self.max_stagnations = data.max_stagnation

            self.set_function = data.set_function

        if not callbacks:
            total_callback = lambda g, r, lp, ls: None
        else:
            def total_callback(
                generation_number: int,
                report_list: List[float],
                last_population: array2D,
                last_scores: array1D
            ):
                for cb in callbacks:
                    cb(generation_number, report_list, last_population, last_scores)

        if not middle_callbacks:
            total_middle_callback = lambda: None
        else:
            def total_middle_callback():
                """
                applies callbacks and sets new data if there is a sence
                """
                data = get_data()
                flag = False
                for cb in middle_callbacks:
                    data, has_sense = cb(data)
                    if has_sense:
                        flag = True
                if flag:
                    set_data(data)  # update global date if there was real callback step

        ############################################################

        start_time = time.time()
        time_is_done = (
            (lambda: False)
            if time_limit_secs is None
            else (lambda: int(time.time() - start_time) >= time_limit_secs)
        )

        ############################################################# 
        # Initial Population
        self.set_function = set_function or geneticalgorithm2.default_set_function(self.f)

        pop_coef, initializer_func = population_initializer
        
        # population creator by random or with oppositions
        if init_creator is None:

            from OppOpPopInit import SampleInitializers

            # just uniform random
            self.creator = SampleInitializers.Combined(
                minimums=[v[0] for v in self.var_bounds],
                maximums=[v[1] for v in self.var_bounds],
                indexes=(
                    self.indexes_int,
                    self.indexes_float
                ),
                creator_initializers=(
                    SampleInitializers.RandomInteger,
                    SampleInitializers.Uniform
                )
            )
        else:
            assert callable(init_creator)
            self.creator = init_creator

        self.init_oppositors = init_oppositors
        self.dup_oppositor = duplicates_oppositor
        self.revolution_oppositor = revolution_oppositor

        # event for removing duplicates
        if remove_duplicates_generation_step is None:
            def remover(pop: array2D, scores: array1D, gen: int) -> Tuple[
                array2D,
                array1D
            ]:
                return pop, scores
        else:
            
            def without_dup(pop: array2D, scores: array1D):  # returns population without dups
                _, index_of_dups = np.unique(pop, axis=0, return_index=True)
                return pop[index_of_dups], scores[index_of_dups], scores.size - index_of_dups.size
            
            if self.dup_oppositor is None:  # if there is no dup_oppositor, use random creator
                def remover(pop: array2D, scores: array1D, gen: int) -> Tuple[
                    array2D,
                    array1D
                ]:
                    if gen % remove_duplicates_generation_step != 0:
                        return pop, scores

                    pp, sc, count_to_create = without_dup(pop, scores)  # pop without dups
                    
                    if count_to_create == 0:
                        if SHOW_PROGRESS:
                            show_progress(t, self.max_iterations,
                                      f"GA is running...{t} gen from {self.max_iterations}. No dups!")
                        return pop, scores

                    pp2 = SampleInitializers.CreateSamples(self.creator, count_to_create)  # new pop elements
                    pp2_scores = self.set_function(pp2)  # new elements values

                    if SHOW_PROGRESS:
                        show_progress(t, self.max_iterations,
                                      f"GA is running...{t} gen from {self.max_iterations}. Kill dups!")
                    
                    new_pop = np.vstack((pp, pp2))
                    new_scores = np.concatenate((sc, pp2_scores))

                    args_to_sort = new_scores.argsort()
                    return new_pop[args_to_sort], new_scores[args_to_sort]

            else:  # using oppositors
                assert callable(self.dup_oppositor)

                def remover(pop: np.ndarray, scores: np.ndarray, gen: int) -> Tuple[
                    np.ndarray,
                    np.ndarray
                ]:
                    if gen % remove_duplicates_generation_step != 0:
                        return pop, scores

                    pp, sc, count_to_create = without_dup(pop, scores)  # pop without dups

                    if count_to_create == 0:
                        if SHOW_PROGRESS:
                            show_progress(t, self.max_iterations,
                                          f"GA is running...{t} gen from {self.max_iterations}. No dups!")
                        return pop, scores

                    if count_to_create > sc.size:
                        raise Exception(
                            f"Too many duplicates at generation {gen} ({count_to_create} > {sc.size}), cannot oppose"
                        )

                    # oppose count_to_create worse elements
                    pp2 = OppositionOperators.Reflect(pp[-count_to_create:], self.dup_oppositor)  # new pop elements
                    pp2_scores = self.set_function(pp2)  # new elements values

                    if SHOW_PROGRESS:
                        show_progress(t, self.max_iterations,
                                      f"GA is running...{t} gen from {self.max_iterations}. Kill dups!")

                    new_pop = np.vstack((pp, pp2))
                    new_scores = np.concatenate((sc, pp2_scores))

                    args_to_sort = new_scores.argsort()
                    return new_pop[args_to_sort], new_scores[args_to_sort]

        # event for revolution
        if revolution_after_stagnation_step is None:
            def revolution(pop: array2D, scores: array1D, stagnation_count: int) -> Tuple[
                array2D,
                array1D
            ]:
                return pop, scores
        else:
            if revolution_oppositor is None:
                raise Exception(
                    f"How can I make revolution each {revolution_after_stagnation_step} stagnation steps "
                    f"if revolution_oppositor is None (not defined)?"
                )
            assert callable(revolution_oppositor)

            from OppOpPopInit import OppositionOperators
            
            def revolution(pop: array2D, scores: array1D, stagnation_count: int) -> Tuple[
                array2D,
                array1D
            ]:
                if stagnation_count < revolution_after_stagnation_step:
                    return pop, scores
                part = int(pop.shape[0]*revolution_part)
                
                pp2 = OppositionOperators.Reflect(pop[-part:], self.revolution_oppositor)
                pp2_scores = self.set_function(pp2)

                combined = np.vstack((pop, pp2))
                combined_scores = np.concatenate((scores, pp2_scores))
                args = combined_scores.argsort()

                if SHOW_PROGRESS:
                    show_progress(t, self.max_iterations,
                                  f"GA is running...{t} gen from {self.max_iterations}. Revolution!")

                args = args[:scores.size]
                return combined[args], combined_scores[args]

        #
        #
        #  START ALGORITHM LOGIC
        #
        #

        # Report
        self._clear_report()  # clear old report objects
        self._init_report()

        # initialization of pop
        
        if start_generation.variables is None:

            from OppOpPopInit import init_population

            real_pop_size = self.population_size * pop_coef

            # pop = np.empty((real_pop_size, self.dim))
            scores = np.empty(real_pop_size)
            
            pop = init_population(
                samples_count=real_pop_size,
                creator=self.creator,
                oppositors=self.init_oppositors
            )

            if self.funtimeout and self.funtimeout > 0:  # perform simulation
            
                time_counter = 0

                for p in range(0, real_pop_size):
                    # simulation returns exception or func value -- check the time of evaluating
                    value, eval_time = self._simulate(pop[p])
                    scores[p] = value
                    time_counter += eval_time

                if enable_printing:
                    print(
                        f"\nSim: Average time of function evaluating (secs): "
                        f"{time_counter/real_pop_size} (total = {time_counter})\n"
                    )
            else:

                eval_time = time.time()
                scores = self.set_function(pop)
                eval_time = time.time() - eval_time
                if enable_printing:
                    print(
                        f"\nSet: Average time of function evaluating (secs): "
                        f"{eval_time/real_pop_size} (total = {eval_time})\n"
                    )
                
        else:

            self.population_size = start_generation.variables.shape[0]
            self._set_elit_count(self.population_size, self.param.elit_ratio)
            self._set_parents_count(self.param.parents_portion)

            pop = start_generation.variables

            if start_generation.scores is None:

                _time = time.time()
                scores = self.set_function(pop)
                _time = time.time() - _time

                if enable_printing:
                    print(
                        f'\nFirst scores are made from gotten variables '
                        f'(by {_time} secs, about {_time/scores.size} for each creature)\n'
                    )
            else:
                scores = start_generation.scores
                if enable_printing:
                    print(f"\nFirst scores are from gotten population\n")

        # Initialization by select bests and local_descent
        
        pop, scores = initializer_func(pop, scores)

        # first sort
        args_to_sort = scores.argsort()
        pop = pop[args_to_sort]
        scores = scores[args_to_sort]
        self._update_report(scores)

        self.population_size = scores.size
        self.best_function = scores[0]

        if enable_printing:
            print(
                f"Best score before optimization: {self.best_function}"
            )

        t: int = 1
        count_stagnation: int = 0
        """iterations without progress"""
        reason_to_stop: Optional[str] = None

        # gets indexes of 2 parents to crossover
        if studEA:
            get_parents_inds = lambda: (0, random.randrange(1, self.parents_count))
        else:
            get_parents_inds = lambda: random_indexes_pair(self.parents_count)

        #  while no reason to stop
        while True:

            if count_stagnation > self.max_stagnations:
                reason_to_stop = f"limit of fails: {count_stagnation}"
            elif t == self.max_iterations:
                reason_to_stop = f'limit of iterations: {t}'
            elif stop_by_val(self.best_function):
                reason_to_stop = f"stop value reached: {self.best_function} <= {stop_when_reached}"
            elif time_is_done():
                reason_to_stop = f'time is done: {time.time() - start_time} >= {time_limit_secs}'

            if reason_to_stop is not None:
                if SHOW_PROGRESS:
                    show_progress(t, self.max_iterations, f"GA is running... STOP! {reason_to_stop}")
                break

            if scores[0] < self.best_function:  # if there is progress
                count_stagnation = 0
                self.best_function = scores[0]
            else:
                count_stagnation += 1

            if SHOW_PROGRESS:
                show_progress(
                    t,
                    self.max_iterations,
                    f"GA is running...{t} gen from {self.max_iterations}...best value = {self.best_function}"
                )

            # Select parents
            
            par: array2D = np.empty((self.parents_count, self.dim))
            """samples chosen to create new samples"""
            par_scores: array1D = np.empty(self.parents_count)

            elit_slice = slice(None, self.elit_count)
            """elit parents"""

            # copy needs because the generation will be removed after parents selection
            par[elit_slice] = pop[elit_slice].copy()
            par_scores[elit_slice] = scores[elit_slice].copy()

            new_par_inds = (
                self.selection(
                    scores[self.elit_count:],
                    self.parents_count - self.elit_count
                ).astype(np.int16) + self.elit_count
            )
            """non-elit parents indexes"""
            #new_par_inds = self.selection(scores, self.parents_count - self.elit_count).astype(np.int16)
            par_slice = slice(self.elit_count, self.parents_count)
            par[par_slice] = pop[new_par_inds].copy()
            par_scores[par_slice] = scores[new_par_inds].copy()

            pop = np.empty((self.population_size, self.dim))
            """new generation"""
            scores = np.empty(self.population_size)
            """new generation scores"""

            parents_slice = slice(None, self.parents_count)
            pop[parents_slice] = par
            scores[parents_slice] = par_scores

            if self.fill_children is None:  # default fill children behaviour
                DO_MUTATION = self.needs_mutation
                for k in range(self.parents_count, self.population_size, 2):

                    r1, r2 = get_parents_inds()

                    pvar1 = pop[r1]  # equal to par[r1], but better for cache
                    pvar2 = pop[r2]

                    ch1, ch2 = self.crossover(pvar1, pvar2)

                    if DO_MUTATION:
                        ch1 = self.mut(ch1)
                        ch2 = self.mut_middle(ch2, pvar1, pvar2)

                    pop[k] = ch1
                    pop[k+1] = ch2
            else:  # custom behaviour
                self.fill_children(pop, self.parents_count)

            if apply_function_to_parents:
                scores = self.set_function(pop)
            else:
                scores[self.parents_count:] = self.set_function(pop[self.parents_count:])
            
            # remove duplicates
            pop, scores = remover(pop, scores, t)
            # revolution
            pop, scores = revolution(pop, scores, count_stagnation)

            # make population better
            args_to_sort = scores.argsort()
            pop = pop[args_to_sort]
            scores = scores[args_to_sort]
            self._update_report(scores)

            # callback it
            total_callback(t, self.report, pop, scores)
            total_middle_callback()

            t += 1

        self.best_function = fast_min(scores[0], self.best_function)

        last_generation = Generation(pop, scores)
        self.result = GAResult(last_generation)

        if save_last_generation_as is not None:
            last_generation.save(save_last_generation_as)

        if enable_printing:
            show = ' ' * 200
            sys.stdout.write(
                f'\r{show}\n'
                f'\r The best found solution:\n {pop[0]}'
                f'\n\n Objective function:\n {self.best_function}\n'
                f'\n Used generations: {len(self.report)}'
                f'\n Used time: {time.time() - start_time:.3g} seconds\n'
            )
            sys.stdout.flush() 
        
        if not no_plot:
            self.plot_results()

        if enable_printing:
            if reason_to_stop is not None and 'iterations' not in reason_to_stop:
                sys.stdout.write(
                    f'\nWarning: GA is terminated because of {reason_to_stop}'
                )

        return self.result

    #endregion

    #region PLOTTING

    def plot_results(
        self,
        title: str = 'Genetic Algorithm',
        save_as: Optional[str] = None,
        dpi: int = 200,
        main_color: str = 'blue'
     ):
        """
        Simple plot of self.report (if not empty)
        """
        if len(self.report) == 0:
            sys.stdout.write("No results to plot!\n")
            return

        plot_several_lines(
            lines=[self.report],
            colors=[main_color],
            labels=['best of generation'],
            linewidths=[2],
            title=title,
            xlabel='Generation',
            ylabel='Minimized function',
            save_as=save_as,
            dpi=dpi
        )

    def plot_generation_scores(self, title: str = 'Last generation scores', save_as: Optional[str] = None):
        """
        Plots barplot of scores of last population
        """

        if not hasattr(self, 'result'):
            raise Exception(
                "There is no 'result' field into ga object! Before plotting generation u need to run seaching process"
            )

        plot_pop_scores(self.result.last_generation.scores, title, save_as)

    #endregion

    #region MUTATION
    def mut(self, x: array1D):
        """
        just mutation
        """

        for i in self.indexes_int_mut:
            if random.random() < self.prob_mut_discrete:
                x[i] = self.discrete_mutation(x[i], *self.var_bounds[i])

        for i in self.indexes_float_mut:                
            if random.random() < self.prob_mut:
                x[i] = self.real_mutation(x[i], *self.var_bounds[i])
            
        return x

    def mut_middle(self, x: array1D, p1: array1D, p2: array1D):
        """
        mutation oriented on parents
        """
        for i in self.indexes_int_mut:

            if random.random() < self.prob_mut_discrete:
                v1, v2 = p1[i], p2[i]
                if v1 < v2:
                    x[i] = random.randint(v1, v2)
                elif v1 > v2:
                    x[i] = random.randint(v2, v1)
                else:
                    x[i] = random.randint(*self.var_bounds[i])
                        
        for i in self.indexes_float_mut:                
            if random.random() < self.prob_mut:
                v1, v2 = p1[i], p2[i]
                if v1 != v2:
                    x[i] = random.uniform(v1, v2)
                else:
                    x[i] = random.uniform(*self.var_bounds[i])
        return x

    #endregion

    #region Set functions

    @staticmethod
    def default_set_function(function_for_set: Callable[[array1D], float]):
        """
        simple function for creating set_function 
        function_for_set just applies to each row of population
        """
        def func(matrix: array2D):
            return np.array(
                [function_for_set(row) for row in matrix]
            )
        return func

    @staticmethod
    def vectorized_set_function(function_for_set: Callable[[array1D], float]):
        """
        works like default, but faster for big populations and slower for little
        function_for_set just applyes to each row of population
        """

        func = np.vectorize(function_for_set, signature='(n)->()')
        return func

    @staticmethod
    def set_function_multiprocess(function_for_set: Callable[[array1D], float], n_jobs: int = -1):
        """
        like function_for_set but uses joblib with n_jobs (-1 goes to count of available processors)
        """
        try:
            from joblib import Parallel, delayed
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "this additional feature requires joblib package," 
                "run `pip install joblib` or `pip install --upgrade geneticalgorithm2[full]`" 
                "or use another set function"
            )

        def func(matrix: array2D):
            result = Parallel(n_jobs=n_jobs)(delayed(function_for_set)(matrix[i]) for i in range(matrix.shape[0]))
            return np.array(result)
        return func
            
    #endregion













            
            