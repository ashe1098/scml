import copy
import itertools
import math
import sys
from os import PathLike
from random import randint, random, shuffle

import numpy as np
from negmas import Agent
from negmas.helpers import unique_name, get_full_type_name

from negmas.tournaments import WorldRunResults, TournamentResults, tournament

from scml.scml2020.agents import RandomAgent
from scml.scml2020.world import SCML2020World

if True:
    from typing import (
        Tuple,
        Union,
        Type,
        Iterable,
        Sequence,
        Optional,
        Callable,
        Any,
        Dict,
        List,
    )
    from .world import SCML2020Agent

__all__ = [
    "anac2020_tournament",
    "anac2020_collusion",
    "anac2020_std",
    "balance_calculator2020",
    "DefaultAgent",
]

DefaultAgent = RandomAgent


def integer_cut(n: int, l: int, l_m: Union[int, List[int]]) -> List[int]:
    """
    Generates l random integers that sum to n where each of them is at least l_m
    Args:
        n: total
        l: number of levels
        l_m: minimum per level

    Returns:

    """
    if not isinstance(l_m, Iterable):
        l_m = [l_m] * l
    sizes = np.asarray(l_m)
    if n < sizes.sum():
        raise ValueError(
            f"Cannot generate {l} numbers summing to {n}  with a minimum summing to {sizes.sum()}"
        )
    while sizes.sum() < n:
        sizes[randint(0, l - 1)] += 1
    return list(sizes.tolist())


def _realin(rng: Union[Tuple[float, float], float]) -> float:
    """
    Selects a random number within a range if given or the input if it was a float

    Args:
        rng: Range or single value

    Returns:

        the real within the given range
    """
    if isinstance(rng, float):
        return rng
    if abs(rng[1] - rng[0]) < 1e-8:
        return rng[0]
    return rng[0] + random() * (rng[1] - rng[0])


def _intin(rng: Union[Tuple[int, int], int]) -> int:
    """
    Selects a random number within a range if given or the input if it was an int

    Args:
        rng: Range or single value

    Returns:

        the int within the given range
    """
    if isinstance(rng, int):
        return rng
    if rng[0] == rng[1]:
        return rng[0]
    return randint(rng[0], rng[1])


def anac2020_config_generator(
    n_competitors: int,
    n_agents_per_competitor: int,
    agent_names_reveal_type: bool = False,
    non_competitors: Optional[Tuple[Union[str, SCML2020Agent]]] = None,
    non_competitor_params: Optional[Tuple[Dict[str, Any]]] = None,
    compact: bool = True,
    *,
    n_steps: Union[int, Tuple[int, int]] = (50, 100),
    n_processes: Tuple[int, int] = (2, 5),
    min_factories_per_level: int = 2,  # strictly guaranteed
    max_factories_per_level: int = 6,  # not strictly guaranteed
    n_default_managers: Tuple[int, int] = (0, 0),
    n_lines: int = 10,
    **kwargs,
) -> List[Dict[str, Any]]:

    if non_competitors is None:
        non_competitors = tuple(DefaultAgent)
    if isinstance(n_processes, Iterable):
        n_processes = tuple(n_processes)
    else:
        n_processes = [n_processes, n_processes]

    n_steps = _intin(n_steps)

    n_processes = randint(*n_processes)

    n_defaults = []
    for level in range(n_processes):
        n_defaults.append(_intin(n_default_managers))
    n_agents = n_agents_per_competitor * n_competitors
    n_a_list = integer_cut(n_agents, n_processes, 0)
    for i, n_a in enumerate(n_a_list):
        if n_a + n_defaults[i] < min_factories_per_level:
            n_defaults[i] = min_factories_per_level - n_a
        if n_a + n_defaults[i] > max_factories_per_level and n_defaults[i] > 1:
            n_defaults[i] = max(1, min_factories_per_level - n_a)
    n_f_list = [a + b for a, b in zip(n_defaults, n_a_list)]
    n_factories = sum(n_f_list)

    if non_competitor_params is None:
        non_competitor_params = [{}] * len(non_competitors)

    non_competitors = [get_full_type_name(_) for _ in non_competitors]

    max_def_agents = len(non_competitors) - 1
    agent_types = [None] * n_factories
    manager_params = [None] * n_factories
    first_in_level = 0
    for level in range(n_processes):
        n_d = n_defaults[level]
        n_f = n_f_list[level]
        assert (
            n_d <= n_f
        ), f"Got {n_f} total factories at level {level} out of which {n_d} are default!!"
        for j in range(n_f):
            if j >= n_f - n_d:  # default managers are last managers in the list
                def_indx = randint(0, max_def_agents)
                agent_types[first_in_level + j] = non_competitors[def_indx]
                params_ = copy.deepcopy(non_competitor_params[def_indx])
                if agent_names_reveal_type:
                    params_["name"] = f"_df_{level}_{j}"
                else:
                    params_[
                        "name"
                    ] = (
                        f"_df_{level}_{j}"
                    )  # because I use name to know that this is a default agent in evaluate.
                    # @todo do not use name to identify default agents in evaluation
                manager_params[first_in_level + j] = params_
        first_in_level += n_f

    world_name = unique_name("", add_time=True, rand_digits=4)
    agent_types = [
        get_full_type_name(_) if isinstance(_, SCML2020Agent) else _
        for _ in agent_types
    ]
    world_params = dict(
        name=world_name,
        agent_types=agent_types,
        time_limit=7200 + 3600,
        neg_time_limit=120,
        neg_n_steps=20,
        neg_step_time_limit=10,
        negotiation_speed=21,
        breach_penalty=0.2,
        interest_rate=0.08,
        bankruptcy_limit=1.0,
        initial_balance=None,
        start_negotiations_immediately=False,
        n_steps=n_steps,
        compact=compact,
    )
    world_params.update(kwargs)
    config = {
        "world_params": world_params,
        "compact": compact,
        "scoring_context": {},
        "non_competitors": non_competitors,
        "non_competitor_params": non_competitor_params,
        "agent_types": agent_types,
        "agent_params": manager_params,
    }
    config.update(kwargs)
    return [config]


def anac2020_assigner(
    config: List[Dict[str, Any]],
    max_n_worlds: int,
    n_agents_per_competitor: int = 1,
    fair: bool = True,
    competitors: Sequence[Type[Agent]] = (),
    params: Sequence[Dict[str, Any]] = (),
) -> List[List[Dict[str, Any]]]:
    config = config[0]
    competitors = list(
        get_full_type_name(_) if not isinstance(_, str) and _ is not None else _
        for _ in competitors
    )
    n_competitors = len(competitors)
    params = (
        list(params) if params is not None else [dict() for _ in range(n_competitors)]
    )

    try:
        n_permutations = n_competitors
    except ArithmeticError:
        n_permutations = None

    agent_types = config["agent_types"]

    assignable_factories = [i for i, mtype in enumerate(agent_types) if mtype is None]
    shuffle(assignable_factories)
    assignable_factories = (
        np.asarray(assignable_factories)
        .reshape((n_competitors, n_agents_per_competitor))
        .tolist()
    )

    configs = []

    def _copy_config(perm_, c, indx):
        new_config = copy.deepcopy(c)
        new_config["world_params"]["name"] += f".{indx:05d}"
        for (a, p_), assignable in zip(perm_, assignable_factories):
            for factory in assignable:
                new_config["agent_types"][factory] = a
                new_config["agent_params"][factory] = copy.deepcopy(p_)
        return [new_config]

    if n_permutations is not None and max_n_worlds is None:
        k = 0
        permutation = list(zip(competitors, params))
        assert len(permutation) == len(assignable_factories)
        shuffle(permutation)
        for __ in range(n_permutations):
            k += 1
            perm = copy.deepcopy(permutation)
            perm = perm[-1:] + perm[:-1]
            configs.append(_copy_config(perm, config, k))
    elif max_n_worlds is None:
        raise ValueError(f"Did not give max_n_worlds and cannot find n_permutations.")
    else:
        permutation = list(zip(competitors, params))
        assert len(permutation) == len(assignable_factories)
        if fair:
            n_min = len(assignable_factories)
            n_rounds = int(max_n_worlds // n_min)
            if n_rounds < 1:
                raise ValueError(
                    f"Cannot guarantee fair assignment: n. competitors {len(assignable_factories)}, at least"
                    f" {n_min} runs are needed for fair assignment"
                )
            max_n_worlds = n_rounds * n_min
            k = 0
            for _ in range(n_rounds):
                shuffle(permutation)
                for __ in range(n_min):
                    k += 1
                    perm = copy.deepcopy(permutation)
                    perm = perm[-1:] + perm[:-1]
                    configs.append(_copy_config(perm, config, k))
        else:
            for k in range(max_n_worlds):
                perm = copy.deepcopy(permutation)
                shuffle(perm)
                configs.append(_copy_config(perm, config, k))

    return configs


def anac2020_world_generator(**kwargs):
    kwargs["world_params"]["agent_types"] = kwargs["agent_types"]
    world = SCML2020World(**SCML2020World.generate(**kwargs["world_params"]))
    return world


def balance_calculator2020(
    worlds: List[SCML2020World],
    scoring_context: Dict[str, Any],
    dry_run: bool,
    ignore_default=True,
) -> WorldRunResults:
    """A scoring function that scores factory managers' performance by the final balance only ignoring whatever still
    in their inventory.

    Args:

        worlds: The world which is assumed to be run up to the point at which the scores are to be calculated.
        scoring_context:  A dict of context parameters passed by the world generator or assigner.
        dry_run: A boolean specifying whether this is a dry_run. For dry runs, only names and types are expected in
                 the returned `WorldRunResults`
        ignore_default: Whether to ignore non-competitors (default agents)

    Returns:
        WorldRunResults giving the names, scores, and types of factory managers.

    """
    assert len(worlds) == 1
    world = worlds[0]
    result = WorldRunResults(
        world_names=[world.name], log_file_names=[world.log_file_name]
    )
    initial_balances = []
    for manager in world.agents.values():
        if "_df_" in manager.name and ignore_default:
            continue
        initial_balances.append(world.a2f[manager.id].initial_balance)
    normalize = all(_ != 0 for _ in initial_balances)
    for manager in world.agents.values():
        if "_df_" in manager.name and ignore_default:
            continue
        factory = world.a2f[manager.id]
        result.names.append(manager.name)
        result.ids.append(manager.id)
        result.types.append(manager.type_name)
        if dry_run:
            result.scores.append(None)
        if normalize:
            result.scores.append(
                (factory.current_balance - factory.initial_balance)
                / factory.initial_balance
            )
        else:
            result.scores.append(factory.current_balance - factory.initial_balance)
    return result


def anac2020_tournament(
    competitors: Sequence[Union[str, Type[SCML2020Agent]]],
    agent_names_reveal_type=False,
    n_configs: int = 5,
    max_worlds_per_config: int = 1000,
    n_runs_per_world: int = 5,
    n_agents_per_competitor: int = 5,
    tournament_path: str = "./logs/tournaments",
    total_timeout: Optional[int] = None,
    parallelism="parallel",
    scheduler_ip: Optional[str] = None,
    scheduler_port: Optional[str] = None,
    tournament_progress_callback: Callable[[Optional[WorldRunResults]], None] = None,
    world_progress_callback: Callable[[Optional[SCML2020World]], None] = None,
    name: str = None,
    verbose: bool = False,
    configs_only=False,
    compact=False,
    **kwargs,
) -> Union[TournamentResults, PathLike]:
    """
    The function used to run ANAC 2020 SCML tournament (collusion track).

    Args:

        name: Tournament name
        competitors: A list of class names for the competitors
        agent_names_reveal_type: If true then the type of an agent should be readable in its name (most likely at its
                                 beginning).
        n_configs: The number of different world configs (up to competitor assignment) to be generated.
        max_worlds_per_config: The maximum number of worlds to run per config. If None, then all possible assignments
                             of competitors within each config will be tried (all permutations).
        n_runs_per_world: Number of runs per world. All of these world runs will have identical competitor assignment
                          and identical world configuration.
        n_agents_per_competitor: Number of agents per competitor
        total_timeout: Total timeout for the complete process
        tournament_path: Path at which to store all results. A scores.csv file will keep the scores and logs folder will
                         keep detailed logs
        parallelism: Type of parallelism. Can be 'serial' for serial, 'parallel' for parallel and 'distributed' for distributed
        scheduler_port: Port of the dask scheduler if parallelism is dask, dist, or distributed
        scheduler_ip: IP Address of the dask scheduler if parallelism is dask, dist, or distributed
        world_progress_callback: A function to be called after everystep of every world run (only allowed for serial
                                 evaluation and should be used with cautious).
        tournament_progress_callback: A function to be called with `WorldRunResults` after each world finished
                                      processing
        verbose: Verbosity
        configs_only: If true, a config file for each
        compact: If true, effort will be made to reduce memory footprint including disableing most logs
        kwargs: Arguments to pass to the `world_generator` function

    Returns:

        `TournamentResults` The results of the tournament or a `PathLike` giving the location where configs were saved

    Remarks:

        Default parameters will be used in the league with the exception of `parallelism` which may use distributed
        processing

    """
    return anac2020_collusion(
        competitors=competitors,
        agent_names_reveal_type=agent_names_reveal_type,
        n_configs=n_configs,
        max_worlds_per_config=max_worlds_per_config,
        n_runs_per_world=n_runs_per_world,
        n_agents_per_competitor=n_agents_per_competitor,
        tournament_path=tournament_path,
        total_timeout=total_timeout,
        parallelism=parallelism,
        scheduler_ip=scheduler_ip,
        scheduler_port=scheduler_port,
        tournament_progress_callback=tournament_progress_callback,
        world_progress_callback=world_progress_callback,
        name=name,
        verbose=verbose,
        compact=compact,
        configs_only=configs_only,
        non_competitors=None,
        non_competitor_params=None,
        **kwargs,
    )


def anac2020_std(
    competitors: Sequence[Union[str, Type[SCML2020Agent]]],
    competitor_params: Optional[Sequence[Dict[str, Any]]] = None,
    agent_names_reveal_type=False,
    n_configs: int = 5,
    max_worlds_per_config: Optional[int] = 1000,
    n_runs_per_world: int = 5,
    min_factories_per_level: int = 5,
    tournament_path: str = "./logs/tournaments",
    total_timeout: Optional[int] = None,
    parallelism="parallel",
    scheduler_ip: Optional[str] = None,
    scheduler_port: Optional[str] = None,
    tournament_progress_callback: Callable[[Optional[WorldRunResults]], None] = None,
    world_progress_callback: Callable[[Optional[SCML2020World]], None] = None,
    non_competitors: Optional[Sequence[Union[str, Type[SCML2020Agent]]]] = None,
    non_competitor_params: Optional[Sequence[Union[str, Type[SCML2020Agent]]]] = None,
    name: str = None,
    verbose: bool = False,
    configs_only=False,
    compact=False,
    **kwargs,
) -> Union[TournamentResults, PathLike]:
    """
    The function used to run ANAC 2020 SCML tournament (standard track).

    Args:

        name: Tournament name
        competitors: A list of class names for the competitors
        competitor_params: A list of competitor parameters (used to initialize the competitors).
        agent_names_reveal_type: If true then the type of an agent should be readable in its name (most likely at its
                                 beginning).
        n_configs: The number of different world configs (up to competitor assignment) to be generated.
        max_worlds_per_config: The maximum number of worlds to run per config. If None, then all possible assignments
                             of competitors within each config will be tried (all permutations).
        n_runs_per_world: Number of runs per world. All of these world runs will have identical competitor assignment
                          and identical world configuration.
        min_factories_per_level: Minimum number of factories for each production level
        total_timeout: Total timeout for the complete process
        tournament_path: Path at which to store all results. A scores.csv file will keep the scores and logs folder will
                         keep detailed logs
        parallelism: Type of parallelism. Can be 'serial' for serial, 'parallel' for parallel and 'distributed' for
                     distributed
        scheduler_port: Port of the dask scheduler if parallelism is dask, dist, or distributed
        scheduler_ip: IP Address of the dask scheduler if parallelism is dask, dist, or distributed
        world_progress_callback: A function to be called after everystep of every world run (only allowed for serial
                                 evaluation and should be used with cautious).
        tournament_progress_callback: A function to be called with `WorldRunResults` after each world finished
                                      processing
        non_competitors: A list of agent types that will not be competing in the sabotage competition but will exist
                         in the world
        non_competitor_params: parameters of non competitor agents
        verbose: Verbosity
        configs_only: If true, a config file for each
        compact: If true, compact logs will be created and effort will be made to reduce the memory footprint
        kwargs: Arguments to pass to the `world_generator` function

    Returns:

        `TournamentResults` The results of the tournament or a `PathLike` giving the location where configs were saved

    Remarks:

        Default parameters will be used in the league with the exception of `parallelism` which may use distributed
        processing

    """
    if non_competitors is None:
        non_competitors = (DefaultAgent,)
        non_competitor_params = ({},)
    return tournament(
        competitors=competitors,
        competitor_params=competitor_params,
        non_competitors=non_competitors,
        non_competitor_params=non_competitor_params,
        agent_names_reveal_type=agent_names_reveal_type,
        n_configs=n_configs,
        n_runs_per_world=n_runs_per_world,
        max_worlds_per_config=max_worlds_per_config,
        tournament_path=tournament_path,
        total_timeout=total_timeout,
        parallelism=parallelism,
        scheduler_ip=scheduler_ip,
        scheduler_port=scheduler_port,
        tournament_progress_callback=tournament_progress_callback,
        world_progress_callback=world_progress_callback,
        name=name,
        verbose=verbose,
        configs_only=configs_only,
        n_agents_per_competitor=1,
        world_generator=anac2020_world_generator,
        config_generator=anac2020_config_generator,
        config_assigner=anac2020_assigner,
        score_calculator=balance_calculator2020,
        min_factories_per_level=min_factories_per_level,
        compact=compact,
        **kwargs,
    )


def anac2020_collusion(
    competitors: Sequence[Union[str, Type[DefaultAgent]]],
    competitor_params: Optional[Sequence[Dict[str, Any]]] = None,
    agent_names_reveal_type=False,
    n_configs: int = 5,
    max_worlds_per_config: Optional[int] = 1000,
    n_runs_per_world: int = 5,
    n_agents_per_competitor: int = 5,
    min_factories_per_level: int = 5,
    tournament_path: str = "./logs/tournaments",
    total_timeout: Optional[int] = None,
    parallelism="parallel",
    scheduler_ip: Optional[str] = None,
    scheduler_port: Optional[str] = None,
    tournament_progress_callback: Callable[[Optional[WorldRunResults]], None] = None,
    world_progress_callback: Callable[[Optional[SCML2020World]], None] = None,
    non_competitors: Optional[Sequence[Union[str, Type[SCML2020Agent]]]] = None,
    non_competitor_params: Optional[Sequence[Union[str, Type[SCML2020Agent]]]] = None,
    name: str = None,
    verbose: bool = False,
    configs_only=False,
    compact=False,
    **kwargs,
) -> Union[TournamentResults, PathLike]:
    """
    The function used to run ANAC 2020 SCML tournament (collusion track).

    Args:

        name: Tournament name
        competitors: A list of class names for the competitors
        competitor_params: A list of competitor parameters (used to initialize the competitors).
        agent_names_reveal_type: If true then the type of an agent should be readable in its name (most likely at its
                                 beginning).
        n_configs: The number of different world configs (up to competitor assignment) to be generated.
        max_worlds_per_config: The maximum number of worlds to run per config. If None, then all possible assignments
                             of competitors within each config will be tried (all permutations).
        n_runs_per_world: Number of runs per world. All of these world runs will have identical competitor assignment
                          and identical world configuration.
        n_agents_per_competitor: Number of agents per competitor
        min_factories_per_level: Minimum number of factories for each production level
        total_timeout: Total timeout for the complete process
        tournament_path: Path at which to store all results. A scores.csv file will keep the scores and logs folder will
                         keep detailed logs
        parallelism: Type of parallelism. Can be 'serial' for serial, 'parallel' for parallel and 'distributed' for
                     distributed
        scheduler_port: Port of the dask scheduler if parallelism is dask, dist, or distributed
        scheduler_ip: IP Address of the dask scheduler if parallelism is dask, dist, or distributed
        world_progress_callback: A function to be called after everystep of every world run (only allowed for serial
                                 evaluation and should be used with cautious).
        tournament_progress_callback: A function to be called with `WorldRunResults` after each world finished
                                      processing
        non_competitors: A list of agent types that will not be competing in the sabotage competition but will exist
                         in the world
        non_competitor_params: parameters of non competitor agents
        verbose: Verbosity
        configs_only: If true, a config file for each
        compact: If true, compact logs will be created and effort will be made to reduce the memory footprint
        kwargs: Arguments to pass to the `world_generator` function

    Returns:

        `TournamentResults` The results of the tournament or a `PathLike` giving the location where configs were saved

    Remarks:

        Default parameters will be used in the league with the exception of `parallelism` which may use distributed
        processing

    """
    if non_competitors is None:
        non_competitors = (DefaultAgent,)
        non_competitor_params = ({},)
    return tournament(
        competitors=competitors,
        competitor_params=competitor_params,
        non_competitors=non_competitors,
        non_competitor_params=non_competitor_params,
        agent_names_reveal_type=agent_names_reveal_type,
        n_configs=n_configs,
        n_runs_per_world=n_runs_per_world,
        max_worlds_per_config=max_worlds_per_config,
        tournament_path=tournament_path,
        total_timeout=total_timeout,
        n_agents_per_competitor=n_agents_per_competitor,
        parallelism=parallelism,
        scheduler_ip=scheduler_ip,
        scheduler_port=scheduler_port,
        tournament_progress_callback=tournament_progress_callback,
        world_progress_callback=world_progress_callback,
        name=name,
        verbose=verbose,
        configs_only=configs_only,
        world_generator=anac2020_world_generator,
        config_generator=anac2020_config_generator,
        config_assigner=anac2020_assigner,
        score_calculator=balance_calculator2020,
        min_factories_per_level=min_factories_per_level,
        compact=compact,
        **kwargs,
    )