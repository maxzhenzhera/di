import sys
from typing import Generator, Optional, Set, Tuple

from di.executors import SyncExecutor

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import pytest

from di import Container, Dependant
from di.typing import Annotated


def value_gen() -> Generator[int, None, None]:
    counter = 0
    while True:
        yield counter
        counter += 1


@pytest.mark.parametrize(
    "use_cache, scope, cached",
    [
        (True, "scope", True),
        # Not cached because it is in the execution scope
        (True, None, False),
        # Not cached because use_cache=False
        (False, "scope", False),
    ],
)
def test_cache_rules_between_dep(
    use_cache: bool, scope: Optional[Literal["scope"]], cached: bool
) -> None:

    gen = value_gen()

    def dep() -> int:
        return next(gen)

    container = Container(scopes=("scope", None))
    solved = container.solve(Dependant(dep, scope=scope, use_cache=use_cache))
    with container.enter_scope("scope"):
        with container.enter_scope(None):
            v1 = container.execute_sync(solved, executor=SyncExecutor())
        with container.enter_scope(None):
            v2 = container.execute_sync(solved, executor=SyncExecutor())
    was_cached = v1 == v2

    assert cached == was_cached


@pytest.mark.parametrize(
    "dep1_use_cache, dep2_use_cache, scope, expected",
    [
        (True, True, "scope", ({0}, {0})),
        # since dep1_use_cache=False, v1 is always "fresh"
        (False, True, "scope", ({0, 1}, {2, 1})),
        # same thing the other way around
        (True, False, "scope", ({0, 1}, {0, 2})),
        # no caching ocurrs
        (False, False, "scope", ({0, 1}, {2, 3})),
        # since the dependencies are scoped to a single execution
        # we get the same number within the execution but not between
        (True, True, None, ({0}, {1})),
        # but if one of the deps is marked with use_cache=False, we get
        # different numbers within an execution, just like before
        (False, True, None, ({0, 1}, {2, 3})),
        # same thing the other way around
        (True, False, None, ({0, 1}, {2, 3})),
        # no caching ocurrs
        (False, False, None, ({0, 1}, {2, 3})),
    ],
)
def test_cache_rules_multiple_deps(
    dep1_use_cache: bool,
    dep2_use_cache: bool,
    scope: Optional[Literal["scope"]],
    expected: Tuple[Set[float], Set[float]],
) -> None:

    gen = value_gen()

    def dep() -> int:
        return next(gen)

    def root_dep(
        v1: Annotated[int, Dependant(dep, use_cache=dep1_use_cache, scope=scope)],
        v2: Annotated[int, Dependant(dep, use_cache=dep2_use_cache, scope=scope)],
    ) -> Set[int]:
        # the order in which v1 and v2 are executed is an implementation detail
        # we represent the result as a set to avoid accidentally depending on that detail
        return {v1, v2}

    container = Container(scopes=("scope", None))
    solved = container.solve(Dependant(root_dep))
    with container.enter_scope("scope"):
        with container.enter_scope(None):
            v1 = container.execute_sync(solved, executor=SyncExecutor())
        with container.enter_scope(None):
            v2 = container.execute_sync(solved, executor=SyncExecutor())

    assert (v1, v2) == expected
