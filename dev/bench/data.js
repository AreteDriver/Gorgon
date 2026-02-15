window.BENCHMARK_DATA = {
  "lastUpdate": 1771153823998,
  "repoUrl": "https://github.com/AreteDriver/Gorgon",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "AreteDriver@users.noreply.github.com",
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "email": "AreteDriver@users.noreply.github.com",
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "distinct": true,
          "id": "ede6010b44289942dad4064d476210a36de6d523",
          "message": "fix(ci): exclude benchmark tests from regular test runs\n\nAdd --ignore flag to CI test step and collect_ignore to conftest.py\nso benchmark tests only run in the dedicated benchmark job.\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-15T03:00:47-08:00",
          "tree_id": "e69c54d11f3b46d714239934a701f6902b27f37c",
          "url": "https://github.com/AreteDriver/Gorgon/commit/ede6010b44289942dad4064d476210a36de6d523"
        },
        "date": 1771153823576,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22120.371695996007,
            "unit": "iter/sec",
            "range": "stddev: 0.0000026564975196184318",
            "extra": "mean: 45.20719695596297 usec\nrounds: 8738"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 342.5256762228489,
            "unit": "iter/sec",
            "range": "stddev: 0.00004573452957982038",
            "extra": "mean: 2.9194891636368743 msec\nrounds: 275"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4373.528084316849,
            "unit": "iter/sec",
            "range": "stddev: 0.000026154887792268378",
            "extra": "mean: 228.6483545369073 usec\nrounds: 4276"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 32.416449160487204,
            "unit": "iter/sec",
            "range": "stddev: 0.0037876399087157448",
            "extra": "mean: 30.8485360333331 msec\nrounds: 30"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.216765861200022,
            "unit": "iter/sec",
            "range": "stddev: 0.017971490862648723",
            "extra": "mean: 97.87833190909043 msec\nrounds: 11"
          }
        ]
      }
    ]
  }
}