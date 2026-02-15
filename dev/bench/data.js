window.BENCHMARK_DATA = {
  "lastUpdate": 1771195711295,
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
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "2b2062aeeb7c2cf9f40d94eb7eff0f23c15ea2a1",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/2b2062aeeb7c2cf9f40d94eb7eff0f23c15ea2a1"
        },
        "date": 1771189702355,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22106.351966114766,
            "unit": "iter/sec",
            "range": "stddev: 0.0000021402762235562545",
            "extra": "mean: 45.235867117868565 usec\nrounds: 7834"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 340.24360954260277,
            "unit": "iter/sec",
            "range": "stddev: 0.00014882037932315205",
            "extra": "mean: 2.939070630435419 msec\nrounds: 276"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4294.689960983441,
            "unit": "iter/sec",
            "range": "stddev: 0.000006157520395546525",
            "extra": "mean: 232.84567898610547 usec\nrounds: 3788"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.222772270202505,
            "unit": "iter/sec",
            "range": "stddev: 0.00017563624299972574",
            "extra": "mean: 28.3907238285719 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.584575358518034,
            "unit": "iter/sec",
            "range": "stddev: 0.011311662688652612",
            "extra": "mean: 94.47710145454639 msec\nrounds: 11"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "4d67ee9de9ac336aa5922cc35c502c3bc34a8416",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/4d67ee9de9ac336aa5922cc35c502c3bc34a8416"
        },
        "date": 1771190553658,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22549.94686208655,
            "unit": "iter/sec",
            "range": "stddev: 0.0000023142378281243277",
            "extra": "mean: 44.346002503505225 usec\nrounds: 7988"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 338.5553848223822,
            "unit": "iter/sec",
            "range": "stddev: 0.00006237140803535999",
            "extra": "mean: 2.95372646494645 msec\nrounds: 271"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4647.259917780698,
            "unit": "iter/sec",
            "range": "stddev: 0.000011069493165797654",
            "extra": "mean: 215.1805618131965 usec\nrounds: 4279"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.9271508697176,
            "unit": "iter/sec",
            "range": "stddev: 0.00013497513248438597",
            "extra": "mean: 28.631021285707448 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.713389583201195,
            "unit": "iter/sec",
            "range": "stddev: 0.004589540472514548",
            "extra": "mean: 102.95067354545816 msec\nrounds: 11"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "bf0e922b475f858acffd91d6933ca9dfb31f500a",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/bf0e922b475f858acffd91d6933ca9dfb31f500a"
        },
        "date": 1771191344750,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 21243.131827964666,
            "unit": "iter/sec",
            "range": "stddev: 0.0000027916067141433735",
            "extra": "mean: 47.07403823967191 usec\nrounds: 10591"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 317.72491779853937,
            "unit": "iter/sec",
            "range": "stddev: 0.00033626465149113113",
            "extra": "mean: 3.1473766896497324 msec\nrounds: 261"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4787.876670483461,
            "unit": "iter/sec",
            "range": "stddev: 0.000025703713199188117",
            "extra": "mean: 208.86085186046031 usec\nrounds: 4192"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.704412179539666,
            "unit": "iter/sec",
            "range": "stddev: 0.00020861657256081274",
            "extra": "mean: 28.81477994286732 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 11.52916360911282,
            "unit": "iter/sec",
            "range": "stddev: 0.012205215023836539",
            "extra": "mean: 86.73656076921186 msec\nrounds: 13"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "98709e53b817a33c982d24c83acf0e4ebb5d6b45",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/98709e53b817a33c982d24c83acf0e4ebb5d6b45"
        },
        "date": 1771192229129,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22278.006005375468,
            "unit": "iter/sec",
            "range": "stddev: 0.000004987864555104169",
            "extra": "mean: 44.88732069462184 usec\nrounds: 6910"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 341.70924654897203,
            "unit": "iter/sec",
            "range": "stddev: 0.00003549186603302335",
            "extra": "mean: 2.926464560439353 msec\nrounds: 273"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4439.13267892912,
            "unit": "iter/sec",
            "range": "stddev: 0.000006751834673562465",
            "extra": "mean: 225.2692298985838 usec\nrounds: 4241"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.04975098348735,
            "unit": "iter/sec",
            "range": "stddev: 0.00011562514090448466",
            "extra": "mean: 28.53087317142768 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.235937499409665,
            "unit": "iter/sec",
            "range": "stddev: 0.005640743009144052",
            "extra": "mean: 108.27271190000118 msec\nrounds: 10"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "d40c75cc811d11abd0bbffa0eaf612588446c5cd",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/d40c75cc811d11abd0bbffa0eaf612588446c5cd"
        },
        "date": 1771195343230,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22238.945403279933,
            "unit": "iter/sec",
            "range": "stddev: 0.000003354145435189545",
            "extra": "mean: 44.966161023647906 usec\nrounds: 8210"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 341.4683621884331,
            "unit": "iter/sec",
            "range": "stddev: 0.000035573646609585685",
            "extra": "mean: 2.9285289963354444 msec\nrounds: 273"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4544.658650310915,
            "unit": "iter/sec",
            "range": "stddev: 0.000007502678446421693",
            "extra": "mean: 220.03852807109877 usec\nrounds: 4346"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.18359270130344,
            "unit": "iter/sec",
            "range": "stddev: 0.00021578832192395715",
            "extra": "mean: 28.422339028582297 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.55098652264701,
            "unit": "iter/sec",
            "range": "stddev: 0.010355115597712123",
            "extra": "mean: 94.77786725000215 msec\nrounds: 12"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "committer": {
            "name": "AreteDriver",
            "username": "AreteDriver"
          },
          "id": "54d91668c80b1416bc36f69d675d7ae55c652a67",
          "message": "Add Convergent intent-graph coordination for parallel workflows",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/52/commits/54d91668c80b1416bc36f69d675d7ae55c652a67"
        },
        "date": 1771195710732,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22173.14366620409,
            "unit": "iter/sec",
            "range": "stddev: 0.0000026208230782097898",
            "extra": "mean: 45.099604054980354 usec\nrounds: 9519"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 340.2791146436607,
            "unit": "iter/sec",
            "range": "stddev: 0.00027382685222584286",
            "extra": "mean: 2.938763964538926 msec\nrounds: 282"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4494.340233928918,
            "unit": "iter/sec",
            "range": "stddev: 0.000007128542582599284",
            "extra": "mean: 222.50206881329225 usec\nrounds: 3851"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.341102062284534,
            "unit": "iter/sec",
            "range": "stddev: 0.0007142085048631644",
            "extra": "mean: 29.11962458823534 msec\nrounds: 34"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.915356988847368,
            "unit": "iter/sec",
            "range": "stddev: 0.002715286260451157",
            "extra": "mean: 91.61404441666339 msec\nrounds: 12"
          }
        ]
      }
    ]
  }
}