"""Tests for GraphWalker workflow traversal."""

import sys

import pytest

sys.path.insert(0, "src")

from test_ai.workflow.graph_models import GraphNode, GraphEdge, WorkflowGraph
from test_ai.workflow.graph_walker import GraphWalker


class TestGraphWalkerBasics:
    """Basic GraphWalker tests."""

    @pytest.fixture
    def simple_graph(self):
        """Simple linear workflow: start -> step1 -> step2 -> end."""
        return WorkflowGraph(
            id="simple",
            name="Simple",
            nodes=[
                GraphNode(id="start", type="start"),
                GraphNode(id="step1", type="agent"),
                GraphNode(id="step2", type="shell"),
                GraphNode(id="end", type="end"),
            ],
            edges=[
                GraphEdge(id="e1", source="start", target="step1"),
                GraphEdge(id="e2", source="step1", target="step2"),
                GraphEdge(id="e3", source="step2", target="end"),
            ],
        )

    def test_get_start_nodes_simple(self, simple_graph):
        """get_start_nodes returns nodes with no incoming edges."""
        walker = GraphWalker(simple_graph)
        starts = walker.get_start_nodes()

        assert len(starts) == 1
        assert "start" in starts

    def test_get_start_nodes_with_start_type(self):
        """get_start_nodes includes nodes with type='start'."""
        graph = WorkflowGraph(
            id="test",
            name="Test",
            nodes=[
                GraphNode(id="explicit-start", type="start"),
                GraphNode(id="other", type="agent"),
            ],
            edges=[
                GraphEdge(id="e1", source="explicit-start", target="other"),
            ],
        )
        walker = GraphWalker(graph)
        starts = walker.get_start_nodes()

        assert "explicit-start" in starts

    def test_get_ready_nodes_initial(self, simple_graph):
        """get_ready_nodes returns start nodes when nothing completed."""
        walker = GraphWalker(simple_graph)
        ready = walker.get_ready_nodes(completed=set())

        assert "start" in ready
        assert len(ready) == 1

    def test_get_ready_nodes_after_start(self, simple_graph):
        """get_ready_nodes returns next node after start completes."""
        walker = GraphWalker(simple_graph)
        ready = walker.get_ready_nodes(completed={"start"})

        assert "step1" in ready
        assert "start" not in ready

    def test_get_ready_nodes_progression(self, simple_graph):
        """get_ready_nodes shows correct progression through workflow."""
        walker = GraphWalker(simple_graph)

        # Initially only start is ready
        ready = walker.get_ready_nodes(completed=set())
        assert ready == ["start"]

        # After start, step1 is ready
        ready = walker.get_ready_nodes(completed={"start"})
        assert ready == ["step1"]

        # After step1, step2 is ready
        ready = walker.get_ready_nodes(completed={"start", "step1"})
        assert ready == ["step2"]

        # After step2, end is ready
        ready = walker.get_ready_nodes(completed={"start", "step1", "step2"})
        assert ready == ["end"]

        # After all, nothing is ready
        ready = walker.get_ready_nodes(completed={"start", "step1", "step2", "end"})
        assert ready == []

    def test_get_downstream_nodes(self, simple_graph):
        """get_downstream_nodes returns immediate successors."""
        walker = GraphWalker(simple_graph)

        downstream = walker.get_downstream_nodes("start")
        assert downstream == ["step1"]

        downstream = walker.get_downstream_nodes("step1")
        assert downstream == ["step2"]

        downstream = walker.get_downstream_nodes("end")
        assert downstream == []

    def test_get_all_downstream(self, simple_graph):
        """get_all_downstream returns all reachable nodes."""
        walker = GraphWalker(simple_graph)

        all_down = walker.get_all_downstream("start")
        assert all_down == {"step1", "step2", "end"}

        all_down = walker.get_all_downstream("step2")
        assert all_down == {"end"}

        all_down = walker.get_all_downstream("end")
        assert all_down == set()


class TestGraphWalkerBranching:
    """Tests for branching logic."""

    @pytest.fixture
    def branch_graph(self):
        """Workflow with a branch: start -> branch -> (yes|no) -> end."""
        return WorkflowGraph(
            id="branch",
            name="Branch",
            nodes=[
                GraphNode(id="start", type="start"),
                GraphNode(
                    id="branch",
                    type="branch",
                    data={
                        "condition": {
                            "field": "status",
                            "operator": "equals",
                            "value": "approved",
                        }
                    },
                ),
                GraphNode(id="yes-path", type="agent"),
                GraphNode(id="no-path", type="agent"),
                GraphNode(id="end", type="end"),
            ],
            edges=[
                GraphEdge(id="e1", source="start", target="branch"),
                GraphEdge(
                    id="e2", source="branch", target="yes-path", source_handle="true"
                ),
                GraphEdge(
                    id="e3", source="branch", target="no-path", source_handle="false"
                ),
                GraphEdge(id="e4", source="yes-path", target="end"),
                GraphEdge(id="e5", source="no-path", target="end"),
            ],
        )

    def test_get_downstream_with_handle(self, branch_graph):
        """get_downstream_nodes can filter by handle."""
        walker = GraphWalker(branch_graph)

        # Without handle, gets both
        both = walker.get_downstream_nodes("branch")
        assert len(both) == 2

        # With handle, gets specific path
        true_path = walker.get_downstream_nodes("branch", handle="true")
        assert true_path == ["yes-path"]

        false_path = walker.get_downstream_nodes("branch", handle="false")
        assert false_path == ["no-path"]

    def test_evaluate_branch_true(self, branch_graph):
        """evaluate_branch returns 'true' when condition matches."""
        walker = GraphWalker(branch_graph)
        context = {"status": "approved"}

        result = walker.evaluate_branch("branch", context)
        assert result == "true"

    def test_evaluate_branch_false(self, branch_graph):
        """evaluate_branch returns 'false' when condition doesn't match."""
        walker = GraphWalker(branch_graph)
        context = {"status": "rejected"}

        result = walker.evaluate_branch("branch", context)
        assert result == "false"

    def test_evaluate_branch_missing_field(self, branch_graph):
        """evaluate_branch returns 'false' when field is missing."""
        walker = GraphWalker(branch_graph)
        context = {}  # No 'status' field

        result = walker.evaluate_branch("branch", context)
        assert result == "false"

    def test_get_ready_nodes_with_branch_decision(self, branch_graph):
        """get_ready_nodes respects branch decisions."""
        walker = GraphWalker(branch_graph)

        # After branch completes with "true" decision
        ready = walker.get_ready_nodes(
            completed={"start", "branch"}, branch_decisions={"branch": "true"}
        )
        assert "yes-path" in ready
        assert "no-path" not in ready

        # After branch completes with "false" decision
        ready = walker.get_ready_nodes(
            completed={"start", "branch"}, branch_decisions={"branch": "false"}
        )
        assert "no-path" in ready
        assert "yes-path" not in ready


class TestConditionEvaluation:
    """Tests for condition evaluation operators."""

    @pytest.fixture
    def condition_branch(self):
        """Create a branch node for testing conditions."""

        def _make_branch(operator, value=None):
            return WorkflowGraph(
                id="test",
                name="Test",
                nodes=[
                    GraphNode(
                        id="branch",
                        type="branch",
                        data={
                            "condition": {
                                "field": "test_field",
                                "operator": operator,
                                "value": value,
                            }
                        },
                    ),
                ],
                edges=[],
            )

        return _make_branch

    def test_equals_operator(self, condition_branch):
        """equals operator tests equality."""
        graph = condition_branch("equals", "target")
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": "target"}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": "other"}) == "false"

    def test_not_equals_operator(self, condition_branch):
        """not_equals operator tests inequality."""
        graph = condition_branch("not_equals", "target")
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": "other"}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": "target"}) == "false"

    def test_contains_operator_string(self, condition_branch):
        """contains operator works with strings."""
        graph = condition_branch("contains", "world")
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": "hello world"}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": "hello"}) == "false"

    def test_contains_operator_list(self, condition_branch):
        """contains operator works with lists."""
        graph = condition_branch("contains", "b")
        walker = GraphWalker(graph)

        assert (
            walker.evaluate_branch("branch", {"test_field": ["a", "b", "c"]}) == "true"
        )
        assert walker.evaluate_branch("branch", {"test_field": ["a", "c"]}) == "false"

    def test_greater_than_operator(self, condition_branch):
        """greater_than operator compares numbers."""
        graph = condition_branch("greater_than", 10)
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": 15}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": 10}) == "false"
        assert walker.evaluate_branch("branch", {"test_field": 5}) == "false"

    def test_less_than_operator(self, condition_branch):
        """less_than operator compares numbers."""
        graph = condition_branch("less_than", 10)
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": 5}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": 10}) == "false"
        assert walker.evaluate_branch("branch", {"test_field": 15}) == "false"

    def test_in_operator(self, condition_branch):
        """in operator tests membership."""
        graph = condition_branch("in", ["a", "b", "c"])
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": "b"}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": "d"}) == "false"

    def test_not_empty_operator(self, condition_branch):
        """not_empty operator tests truthiness."""
        graph = condition_branch("not_empty")
        walker = GraphWalker(graph)

        assert walker.evaluate_branch("branch", {"test_field": "value"}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": [1, 2, 3]}) == "true"
        assert walker.evaluate_branch("branch", {"test_field": ""}) == "false"
        assert walker.evaluate_branch("branch", {"test_field": []}) == "false"
        assert walker.evaluate_branch("branch", {"test_field": None}) == "false"


class TestGraphWalkerLoops:
    """Tests for loop handling."""

    @pytest.fixture
    def while_loop_graph(self):
        """Workflow with a while loop."""
        return WorkflowGraph(
            id="while-loop",
            name="While Loop",
            nodes=[
                GraphNode(id="start", type="start"),
                GraphNode(
                    id="loop",
                    type="loop",
                    data={
                        "loop_type": "while",
                        "max_iterations": 5,
                        "condition": {
                            "field": "counter",
                            "operator": "less_than",
                            "value": 3,
                        },
                    },
                ),
                GraphNode(id="body", type="agent"),
                GraphNode(id="end", type="end"),
            ],
            edges=[
                GraphEdge(id="e1", source="start", target="loop"),
                GraphEdge(id="e2", source="loop", target="body"),
                GraphEdge(id="e3", source="body", target="loop"),
                GraphEdge(id="e4", source="loop", target="end"),
            ],
        )

    @pytest.fixture
    def count_loop_graph(self):
        """Workflow with a count loop."""
        return WorkflowGraph(
            id="count-loop",
            name="Count Loop",
            nodes=[
                GraphNode(
                    id="loop",
                    type="loop",
                    data={"loop_type": "count", "count": 3, "max_iterations": 10},
                ),
            ],
            edges=[],
        )

    @pytest.fixture
    def foreach_loop_graph(self):
        """Workflow with a for-each loop."""
        return WorkflowGraph(
            id="foreach-loop",
            name="ForEach Loop",
            nodes=[
                GraphNode(
                    id="loop",
                    type="loop",
                    data={
                        "loop_type": "for_each",
                        "collection": "items",
                        "item_variable": "current_item",
                        "max_iterations": 100,
                    },
                ),
            ],
            edges=[],
        )

    def test_should_continue_loop_while_true(self, while_loop_graph):
        """should_continue_loop returns True when while condition is true."""
        walker = GraphWalker(while_loop_graph)

        result = walker.should_continue_loop("loop", {"counter": 0}, iteration=0)
        assert result is True

        result = walker.should_continue_loop("loop", {"counter": 2}, iteration=1)
        assert result is True

    def test_should_continue_loop_while_false(self, while_loop_graph):
        """should_continue_loop returns False when while condition is false."""
        walker = GraphWalker(while_loop_graph)

        result = walker.should_continue_loop("loop", {"counter": 3}, iteration=0)
        assert result is False

        result = walker.should_continue_loop("loop", {"counter": 5}, iteration=1)
        assert result is False

    def test_should_continue_loop_max_iterations(self, while_loop_graph):
        """should_continue_loop stops at max_iterations."""
        walker = GraphWalker(while_loop_graph)

        # Even if condition would be true, stop at max_iterations
        result = walker.should_continue_loop("loop", {"counter": 0}, iteration=5)
        assert result is False

    def test_should_continue_loop_count(self, count_loop_graph):
        """should_continue_loop respects count loop type."""
        walker = GraphWalker(count_loop_graph)

        assert walker.should_continue_loop("loop", {}, iteration=0) is True
        assert walker.should_continue_loop("loop", {}, iteration=1) is True
        assert walker.should_continue_loop("loop", {}, iteration=2) is True
        assert walker.should_continue_loop("loop", {}, iteration=3) is False

    def test_should_continue_loop_foreach(self, foreach_loop_graph):
        """should_continue_loop respects for_each loop type."""
        walker = GraphWalker(foreach_loop_graph)
        context = {"items": ["a", "b", "c"]}

        assert walker.should_continue_loop("loop", context, iteration=0) is True
        assert walker.should_continue_loop("loop", context, iteration=1) is True
        assert walker.should_continue_loop("loop", context, iteration=2) is True
        assert walker.should_continue_loop("loop", context, iteration=3) is False

    def test_get_loop_item(self, foreach_loop_graph):
        """get_loop_item returns correct item from collection."""
        walker = GraphWalker(foreach_loop_graph)
        context = {"items": ["first", "second", "third"]}

        assert walker.get_loop_item("loop", context, iteration=0) == "first"
        assert walker.get_loop_item("loop", context, iteration=1) == "second"
        assert walker.get_loop_item("loop", context, iteration=2) == "third"
        assert walker.get_loop_item("loop", context, iteration=3) is None


class TestGraphWalkerCycleDetection:
    """Tests for cycle detection."""

    def test_detect_cycles_no_cycles(self):
        """detect_cycles returns empty list for acyclic graph."""
        graph = WorkflowGraph(
            id="acyclic",
            name="Acyclic",
            nodes=[
                GraphNode(id="a", type="agent"),
                GraphNode(id="b", type="agent"),
                GraphNode(id="c", type="agent"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="c"),
            ],
        )
        walker = GraphWalker(graph)

        cycles = walker.detect_cycles()
        assert cycles == []

    def test_detect_cycles_simple_cycle(self):
        """detect_cycles finds simple cycle."""
        graph = WorkflowGraph(
            id="cyclic",
            name="Cyclic",
            nodes=[
                GraphNode(id="a", type="agent"),
                GraphNode(id="b", type="agent"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="a"),  # Back edge
            ],
        )
        walker = GraphWalker(graph)

        cycles = walker.detect_cycles()
        assert len(cycles) >= 1

    def test_detect_cycles_self_loop(self):
        """detect_cycles finds self-loop."""
        graph = WorkflowGraph(
            id="self-loop",
            name="Self Loop",
            nodes=[
                GraphNode(id="a", type="loop"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="a"),  # Self loop
            ],
        )
        walker = GraphWalker(graph)

        cycles = walker.detect_cycles()
        assert len(cycles) >= 1


class TestGraphWalkerTopologicalSort:
    """Tests for topological sort."""

    def test_topological_sort_linear(self):
        """topological_sort returns correct order for linear graph."""
        graph = WorkflowGraph(
            id="linear",
            name="Linear",
            nodes=[
                GraphNode(id="a", type="agent"),
                GraphNode(id="b", type="agent"),
                GraphNode(id="c", type="agent"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="c"),
            ],
        )
        walker = GraphWalker(graph)

        order = walker.topological_sort()

        # a must come before b, b must come before c
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_diamond(self):
        """topological_sort handles diamond pattern."""
        graph = WorkflowGraph(
            id="diamond",
            name="Diamond",
            nodes=[
                GraphNode(id="top", type="start"),
                GraphNode(id="left", type="agent"),
                GraphNode(id="right", type="agent"),
                GraphNode(id="bottom", type="end"),
            ],
            edges=[
                GraphEdge(id="e1", source="top", target="left"),
                GraphEdge(id="e2", source="top", target="right"),
                GraphEdge(id="e3", source="left", target="bottom"),
                GraphEdge(id="e4", source="right", target="bottom"),
            ],
        )
        walker = GraphWalker(graph)

        order = walker.topological_sort()

        # top must come first, bottom must come last
        assert order[0] == "top"
        assert order[-1] == "bottom"

    def test_topological_sort_cyclic_raises(self):
        """topological_sort raises for cyclic graph."""
        graph = WorkflowGraph(
            id="cyclic",
            name="Cyclic",
            nodes=[
                GraphNode(id="a", type="agent"),
                GraphNode(id="b", type="agent"),
            ],
            edges=[
                GraphEdge(id="e1", source="a", target="b"),
                GraphEdge(id="e2", source="b", target="a"),
            ],
        )
        walker = GraphWalker(graph)

        with pytest.raises(ValueError) as exc:
            walker.topological_sort()

        assert "cycle" in str(exc.value).lower()


class TestGraphWalkerParallel:
    """Tests for parallel execution patterns."""

    @pytest.fixture
    def parallel_graph(self):
        """Workflow with parallel paths."""
        return WorkflowGraph(
            id="parallel",
            name="Parallel",
            nodes=[
                GraphNode(id="start", type="start"),
                GraphNode(id="task1", type="agent"),
                GraphNode(id="task2", type="agent"),
                GraphNode(id="task3", type="agent"),
                GraphNode(id="end", type="end"),
            ],
            edges=[
                GraphEdge(id="e1", source="start", target="task1"),
                GraphEdge(id="e2", source="start", target="task2"),
                GraphEdge(id="e3", source="start", target="task3"),
                GraphEdge(id="e4", source="task1", target="end"),
                GraphEdge(id="e5", source="task2", target="end"),
                GraphEdge(id="e6", source="task3", target="end"),
            ],
        )

    def test_get_ready_nodes_parallel(self, parallel_graph):
        """get_ready_nodes returns all parallel tasks at once."""
        walker = GraphWalker(parallel_graph)

        # After start, all three tasks should be ready
        ready = walker.get_ready_nodes(completed={"start"})
        assert set(ready) == {"task1", "task2", "task3"}

    def test_get_ready_nodes_waits_for_all(self, parallel_graph):
        """get_ready_nodes waits for all parallel tasks before end."""
        walker = GraphWalker(parallel_graph)

        # End is not ready until all tasks complete
        ready = walker.get_ready_nodes(completed={"start", "task1"})
        assert "end" not in ready

        ready = walker.get_ready_nodes(completed={"start", "task1", "task2"})
        assert "end" not in ready

        ready = walker.get_ready_nodes(completed={"start", "task1", "task2", "task3"})
        assert "end" in ready
