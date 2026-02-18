window.BENCHMARK_DATA = {
  "lastUpdate": 1771450275099,
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
          "id": "f571118d942ea6971580e9c1dd01b818aea5f6f3",
          "message": "Add comprehensive security features: 2FA, sessions, API keys, threat detection",
          "timestamp": "2026-02-15T11:01:02Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/54/commits/f571118d942ea6971580e9c1dd01b818aea5f6f3"
        },
        "date": 1771218862209,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22231.414070480947,
            "unit": "iter/sec",
            "range": "stddev: 0.0000024940861960304757",
            "extra": "mean: 44.98139420325081 usec\nrounds: 8039"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 340.4395636179898,
            "unit": "iter/sec",
            "range": "stddev: 0.00005638627214750265",
            "extra": "mean: 2.9373789267398687 msec\nrounds: 273"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4654.891804026282,
            "unit": "iter/sec",
            "range": "stddev: 0.000024585324015412167",
            "extra": "mean: 214.82776444665004 usec\nrounds: 4084"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.01724326096232,
            "unit": "iter/sec",
            "range": "stddev: 0.00017119449830711337",
            "extra": "mean: 28.557359371427538 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 8.694424873937917,
            "unit": "iter/sec",
            "range": "stddev: 0.013502679870224799",
            "extra": "mean: 115.01623333333555 msec\nrounds: 9"
          }
        ]
      },
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
          "id": "8bcccc4d6d64b741e999f053db18075d00492030",
          "message": "fix: resolve 27 CodeQL code scanning alerts\n\n- Add __all__ to workflow/executor.py to declare re-exports as public API (10 unused-import)\n- Close file handles properly in test fixtures using context managers (5 file-not-closed)\n- Add logging to empty except handlers in store, handler, db, workflows (4 empty-except)\n- Extract URL literals to variables to avoid substring sanitization FPs (3 url-sanitization)\n- Remove unused _persistent_budget_manager and _MIN_SECRET_KEY_ENTROPY_BITS (3 unused-global)\n- Prefix unused loop variables with underscore (2 unused-loop-variable)\n\n7250 tests, 0 failures.\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T03:39:09-08:00",
          "tree_id": "ff16ab95829ae5d84fd2c58b5c403330100dcc56",
          "url": "https://github.com/AreteDriver/Gorgon/commit/8bcccc4d6d64b741e999f053db18075d00492030"
        },
        "date": 1771415334040,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22010.71710828187,
            "unit": "iter/sec",
            "range": "stddev: 0.0000044370894919600936",
            "extra": "mean: 45.432413450252135 usec\nrounds: 8446"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 337.5404132917137,
            "unit": "iter/sec",
            "range": "stddev: 0.00003863731752259768",
            "extra": "mean: 2.962608211111499 msec\nrounds: 270"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4542.241934017037,
            "unit": "iter/sec",
            "range": "stddev: 0.000006863414574895705",
            "extra": "mean: 220.15560036795017 usec\nrounds: 4349"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.23555894325377,
            "unit": "iter/sec",
            "range": "stddev: 0.00020562536421866778",
            "extra": "mean: 28.38042108571293 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.429358237661365,
            "unit": "iter/sec",
            "range": "stddev: 0.006182295151193558",
            "extra": "mean: 106.05175610000117 msec\nrounds: 10"
          }
        ]
      },
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
          "id": "d74936e482d2a7a45dd939d54425dff3ac215e88",
          "message": "fix: resolve remaining 4 CodeQL alerts\n\n- Use bare _ for unused loop variables (CodeQL needs _ not _attempt)\n- Remove user input from log message to avoid log-injection alert\n- Use exact URL equality in test assertion to avoid substring-sanitization FP\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T03:44:40-08:00",
          "tree_id": "0d746742e02830c1317d61ae02c845d2e657211c",
          "url": "https://github.com/AreteDriver/Gorgon/commit/d74936e482d2a7a45dd939d54425dff3ac215e88"
        },
        "date": 1771415659611,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22360.805934323744,
            "unit": "iter/sec",
            "range": "stddev: 0.0000027217640581728326",
            "extra": "mean: 44.721107232767686 usec\nrounds: 9139"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 312.3129057864411,
            "unit": "iter/sec",
            "range": "stddev: 0.0005476307655484992",
            "extra": "mean: 3.2019169924530684 msec\nrounds: 265"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4417.83749239419,
            "unit": "iter/sec",
            "range": "stddev: 0.000022846658261216153",
            "extra": "mean: 226.35508927650997 usec\nrounds: 3954"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.13590145050743,
            "unit": "iter/sec",
            "range": "stddev: 0.0001610620435823809",
            "extra": "mean: 28.460917714281614 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 11.603596239535795,
            "unit": "iter/sec",
            "range": "stddev: 0.007076353918519368",
            "extra": "mean: 86.18017891667051 msec\nrounds: 12"
          }
        ]
      },
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
          "id": "d6059e4c6b88628c14ec82c98359197164e134f8",
          "message": "style: format files to pass ruff format check\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T03:49:15-08:00",
          "tree_id": "926ec63ba8a57766deb1afcc6c14b75df7d66b70",
          "url": "https://github.com/AreteDriver/Gorgon/commit/d6059e4c6b88628c14ec82c98359197164e134f8"
        },
        "date": 1771415937887,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22614.09729140565,
            "unit": "iter/sec",
            "range": "stddev: 0.00000252378264615542",
            "extra": "mean: 44.220204198911084 usec\nrounds: 9050"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 339.4692018525069,
            "unit": "iter/sec",
            "range": "stddev: 0.0002607304950727771",
            "extra": "mean: 2.945775329670353 msec\nrounds: 273"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4376.661960030054,
            "unit": "iter/sec",
            "range": "stddev: 0.000005575472735316071",
            "extra": "mean: 228.48463261099863 usec\nrounds: 3876"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.47414314031867,
            "unit": "iter/sec",
            "range": "stddev: 0.00018517672265389045",
            "extra": "mean: 28.1895462857124 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.796630142873216,
            "unit": "iter/sec",
            "range": "stddev: 0.005098391320022647",
            "extra": "mean: 102.07591645454463 msec\nrounds: 11"
          }
        ]
      },
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
          "id": "34c60153aa9ec80f8e7d792576928dd9e721b2ea",
          "message": "fix: resolve code scanning alerts — log injection and dead variable\n\n- workflows.py: log exception type name instead of user-influenced str(e)\n  to prevent log injection (CodeQL py/log-injection #221)\n- context_window.py: remove unused summary_tokens assignment\n  (CodeQL py/multiple-definition #226)\n- Dismissed #223-225 as false positives (CLI subcommand registration imports)\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T04:43:29-08:00",
          "tree_id": "7ebe4e6fc941d1e426340e8566017bef666e1918",
          "url": "https://github.com/AreteDriver/Gorgon/commit/34c60153aa9ec80f8e7d792576928dd9e721b2ea"
        },
        "date": 1771419212704,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22519.38842198598,
            "unit": "iter/sec",
            "range": "stddev: 0.000005145582289112391",
            "extra": "mean: 44.40617930030847 usec\nrounds: 7691"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 343.37458368366845,
            "unit": "iter/sec",
            "range": "stddev: 0.0000361202149938299",
            "extra": "mean: 2.9122714595592885 msec\nrounds: 272"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4548.127112349561,
            "unit": "iter/sec",
            "range": "stddev: 0.000005545489259658531",
            "extra": "mean: 219.870723772142 usec\nrounds: 4337"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.31133406482877,
            "unit": "iter/sec",
            "range": "stddev: 0.00012055594078777528",
            "extra": "mean: 28.319519114290056 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.995769317897219,
            "unit": "iter/sec",
            "range": "stddev: 0.00464766246380948",
            "extra": "mean: 100.04232472727442 msec\nrounds: 11"
          }
        ]
      },
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
          "id": "073245985553cac80b66f57bb1541a254fd3068a",
          "message": "fix: remove workflow_id from log message to resolve CodeQL log-injection alert #276\n\nThe workflow_id path parameter is user-controlled input. Even though it's\nsanitized via regex, CodeQL still traces it as tainted. Omitting it from\nthe log avoids the false positive while the exception type still provides\nsufficient debugging context.\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T11:58:45-08:00",
          "tree_id": "1c4e7922bc07493edf3006560cbc78f4219854e0",
          "url": "https://github.com/AreteDriver/Gorgon/commit/073245985553cac80b66f57bb1541a254fd3068a"
        },
        "date": 1771445320860,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 21773.406953901896,
            "unit": "iter/sec",
            "range": "stddev: 0.0000026167112527842276",
            "extra": "mean: 45.92758506361336 usec\nrounds: 12185"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 341.60008582978105,
            "unit": "iter/sec",
            "range": "stddev: 0.000036038179597941644",
            "extra": "mean: 2.9273997328510593 msec\nrounds: 277"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4542.827538273226,
            "unit": "iter/sec",
            "range": "stddev: 0.000005883564905013523",
            "extra": "mean: 220.12722067369302 usec\nrounds: 4305"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 35.64367982784182,
            "unit": "iter/sec",
            "range": "stddev: 0.00024039228809147017",
            "extra": "mean: 28.05546466666679 msec\nrounds: 36"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.953240464026651,
            "unit": "iter/sec",
            "range": "stddev: 0.007397682840991536",
            "extra": "mean: 91.29718308333186 msec\nrounds: 12"
          }
        ]
      },
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
          "id": "cef5e7f5fbb7d4c6271c64db60879a71fbc8e924",
          "message": "fix: align convergent dependency name with package metadata\n\nThe convergent package declares name=\"convergentAI\" in its pyproject.toml\nbut Gorgon depended on \"convergent\". Newer pip versions enforce strict\nname matching, causing the Benchmark CI job to fail.\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
          "timestamp": "2026-02-18T12:35:10-08:00",
          "tree_id": "e932ecf015f4192c324cb1d2ebaa90476ea2035b",
          "url": "https://github.com/AreteDriver/Gorgon/commit/cef5e7f5fbb7d4c6271c64db60879a71fbc8e924"
        },
        "date": 1771447490936,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22265.451359211034,
            "unit": "iter/sec",
            "range": "stddev: 0.000002532788967653569",
            "extra": "mean: 44.912630957571324 usec\nrounds: 9148"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 347.4246849656091,
            "unit": "iter/sec",
            "range": "stddev: 0.000033072705105460115",
            "extra": "mean: 2.8783216716422673 msec\nrounds: 268"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4520.272677262194,
            "unit": "iter/sec",
            "range": "stddev: 0.000006638971204290085",
            "extra": "mean: 221.22559221486452 usec\nrounds: 4316"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.82364349284844,
            "unit": "iter/sec",
            "range": "stddev: 0.00015367651273056409",
            "extra": "mean: 28.716122142858627 msec\nrounds: 35"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 8.813071803482506,
            "unit": "iter/sec",
            "range": "stddev: 0.005410703977445332",
            "extra": "mean: 113.46781488888445 msec\nrounds: 9"
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
          "id": "d559d262bdff9bf9fed01d912ec742a1e2d6902c",
          "message": "ci: bump actions/setup-python from 5 to 6",
          "timestamp": "2026-02-18T21:14:15Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/57/commits/d559d262bdff9bf9fed01d912ec742a1e2d6902c"
        },
        "date": 1771449893186,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22980.959111268672,
            "unit": "iter/sec",
            "range": "stddev: 0.0000034362827269332595",
            "extra": "mean: 43.514284811100495 usec\nrounds: 12654"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 351.1194581744562,
            "unit": "iter/sec",
            "range": "stddev: 0.00011216778490129684",
            "extra": "mean: 2.848033558718762 msec\nrounds: 281"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4525.271537611806,
            "unit": "iter/sec",
            "range": "stddev: 0.000010782574367521293",
            "extra": "mean: 220.98121442845968 usec\nrounds: 4505"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.42133344542788,
            "unit": "iter/sec",
            "range": "stddev: 0.0007621240822353194",
            "extra": "mean: 29.05175075757642 msec\nrounds: 33"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 11.940093099477785,
            "unit": "iter/sec",
            "range": "stddev: 0.004262921453513876",
            "extra": "mean: 83.75144076922953 msec\nrounds: 13"
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
          "id": "8313a9e2a1b13870da3f96367e3b3d153aff4daa",
          "message": "ci: bump actions/checkout from 4 to 6",
          "timestamp": "2026-02-18T21:14:15Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/56/commits/8313a9e2a1b13870da3f96367e3b3d153aff4daa"
        },
        "date": 1771449901914,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22601.828684960154,
            "unit": "iter/sec",
            "range": "stddev: 0.000002463674503031813",
            "extra": "mean: 44.24420757889498 usec\nrounds: 8893"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 347.0062893637009,
            "unit": "iter/sec",
            "range": "stddev: 0.000033971510562003825",
            "extra": "mean: 2.8817921480146134 msec\nrounds: 277"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4246.000462281977,
            "unit": "iter/sec",
            "range": "stddev: 0.00003615148144628384",
            "extra": "mean: 235.51575391552328 usec\nrounds: 4214"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 33.5714311718044,
            "unit": "iter/sec",
            "range": "stddev: 0.003502232191420905",
            "extra": "mean: 29.787231735293695 msec\nrounds: 34"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.449623997031368,
            "unit": "iter/sec",
            "range": "stddev: 0.012810605630030338",
            "extra": "mean: 95.69722320000125 msec\nrounds: 10"
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
          "id": "8c01b56f1c05e829c2c195c28774c733b923a953",
          "message": "deps: bump the python-minor group with 5 updates",
          "timestamp": "2026-02-18T21:14:15Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/58/commits/8c01b56f1c05e829c2c195c28774c733b923a953"
        },
        "date": 1771450267737,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 22567.23481658746,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025155402356004145",
            "extra": "mean: 44.31203061107762 usec\nrounds: 9147"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 343.1298742456261,
            "unit": "iter/sec",
            "range": "stddev: 0.00003520872821294376",
            "extra": "mean: 2.91434840000017 msec\nrounds: 275"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4527.7914506164625,
            "unit": "iter/sec",
            "range": "stddev: 0.000006488841456442863",
            "extra": "mean: 220.85822876489803 usec\nrounds: 3991"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.81266297509749,
            "unit": "iter/sec",
            "range": "stddev: 0.00017283998723075715",
            "extra": "mean: 28.725179705882574 msec\nrounds: 34"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 10.781950714765191,
            "unit": "iter/sec",
            "range": "stddev: 0.004268780654261868",
            "extra": "mean: 92.7475951666672 msec\nrounds: 12"
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
          "id": "1334e90d18576d6196a3a78de75ddb8aa45728b9",
          "message": "deps: bump bcrypt from 4.3.0 to 5.0.0",
          "timestamp": "2026-02-18T21:14:15Z",
          "url": "https://github.com/AreteDriver/Gorgon/pull/59/commits/1334e90d18576d6196a3a78de75ddb8aa45728b9"
        },
        "date": 1771450274749,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::TestWorkflowParseBenchmark::test_parse_20_step_workflow",
            "value": 21628.0241324712,
            "unit": "iter/sec",
            "range": "stddev: 0.0000025456220809557457",
            "extra": "mean: 46.236308683355475 usec\nrounds: 12725"
          },
          {
            "name": "tests/test_benchmarks.py::TestYAMLLoadBenchmark::test_load_yaml_10_steps",
            "value": 341.84701867074966,
            "unit": "iter/sec",
            "range": "stddev: 0.00003368315019989962",
            "extra": "mean: 2.9252851286766703 msec\nrounds: 272"
          },
          {
            "name": "tests/test_benchmarks.py::TestConditionEvalBenchmark::test_condition_evaluate_1000",
            "value": 4201.789069516623,
            "unit": "iter/sec",
            "range": "stddev: 0.000047441898935359556",
            "extra": "mean: 237.99386010470073 usec\nrounds: 4196"
          },
          {
            "name": "tests/test_benchmarks.py::TestCacheBenchmark::test_cache_set_get_1000",
            "value": 34.460149966353505,
            "unit": "iter/sec",
            "range": "stddev: 0.001483797525174256",
            "extra": "mean: 29.019026352943577 msec\nrounds: 34"
          },
          {
            "name": "tests/test_benchmarks.py::TestTaskStoreBenchmark::test_record_query_100",
            "value": 9.274455618731961,
            "unit": "iter/sec",
            "range": "stddev: 0.006211362643079634",
            "extra": "mean: 107.82304009092059 msec\nrounds: 11"
          }
        ]
      }
    ]
  }
}