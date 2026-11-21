# The window's failed tests left out, for classification, 2026-11-21

As the user asked on 2026-11-21, option A of `2026-11-20-next-bet-options.md`
(note 101 of `TASKS.md`): for each of the window's 11 failed tests left out
that nobody has classified, what a person needs to classify it as one of
D-021's causes, F, C, N or O. D-021 fixed those rules first, and a1c09bf
committed them before this note's facts were gathered, but for what this
folder already held: the node ids, and the paths with no column in
`2026-11-19-window-report.txt`. The window's other 3 failed tests left out,
those of the missed pull requests, were classified in D-017, which is N under
D-021.

Everything below is FACT, but for the user's classification and one paragraph
marked INFERENCE. The facts are read from the copies of the records in this
folder, the manifest, the clone `~/code/distiller-pilots/urllib3`, and each
pull request's folder in the work directory,
`~/code/distiller-replay/urllib3/<pr>/`: there, `junit.xml` is the full run at
H, `rerun.xml` the rerun of its failed tests at H, and `junit-m.xml` the run at
M that recorded the coverage. Nothing was run for this note, and the agent
gives no cause and no inference about one: the classification is the user's
(Non-goals). Paths in tracebacks are relative to the head's worktree, and
quotes keep printable ASCII only.

## What the three pull requests have in common

- M is the merge-base: in each record, `coverage_commit` is `merge_base`. So
  the run at M is a run at the merge-base.
- The pilot's coverage measures the package alone: `coverage_source =
  "urllib3"` in `pilots/urllib3.toml`, line 30. No file under `test/` or
  `dummyserver/` has a column, and every row below holds paths under
  `src/urllib3/` only.
- `test/contrib/test_pyopenssl.py`, which none of the three changes, has a
  `setup_module` that calls `urllib3.contrib.pyopenssl.inject_into_urllib3()`
  and skips the module if PyOpenSSL cannot be imported, and imports test
  classes of other modules, at lines 35 to 52 of #5050's and #5097's heads and
  38 to 55 of #4962's:

```python
from ..test_ssl import TestSSL  # noqa: E402, F401
from ..test_util import TestUtilSSL  # noqa: E402, F401
from ..with_dummyserver.test_https import (  # noqa: E402, F401
    TestHTTPS_IPV4SAN,
    TestHTTPS_IPV6SAN,
    TestHTTPS_TLSv1,
    TestHTTPS_TLSv1_1,
    TestHTTPS_TLSv1_2,
    TestHTTPS_TLSv1_3,
)
from ..with_dummyserver.test_socketlevel import (  # noqa: E402, F401
    TestClientCerts,
    TestSNI,
    TestSocketClosing,
)
from ..with_dummyserver.test_socketlevel import (  # noqa: E402, F401
    TestSSL as TestSocketSSL,
)
```

  pytest collects each imported class again under this file's node ids, as
  the JUnit files show: `test.contrib.test_pyopenssl.TestClientCerts` beside
  `test.with_dummyserver.test_socketlevel.TestClientCerts`, and
  `test.contrib.test_pyopenssl.TestSSL` beside `test.test_ssl.TestSSL`.

## #4962 and #5050: four tests of `TestClientCerts`

| | #4962 | #5050 |
|---|---|---|
| Run, start | 24362830593, 2026-04-13T19:33:17Z | 26326541760, 2026-05-23T07:07:55Z |
| CI job, in the manifest | failed, steps no longer given | failed in a test step, Run tests |
| H | ae81f84b758e | 8456785e9914 |
| Merge-base and M | c21b1c16cd8c | c2a56d9e5243 |
| Commits from the merge-base to H | one, "Fix proxy_ssl_context mutation when target uses cert_reqs='CERT_NONE'" | one, "fix: do not mutate caller-supplied proxy_ssl_context verify_mode" |
| Verdict | caught, with a rerun file | caught, with a rerun file |

The changed paths, from `git diff --numstat`; "no column" is the record's
`no_column`, and neither record has an import-only path:

| Path | #4962 | #5050 |
|---|---|---|
| `changelog/4961.bugfix.rst` | +4, no column | +4, no column |
| `src/urllib3/connection.py` | +15 -2 | +10 -2 |
| `test/test_connection.py` | +76, no column | |
| `test/with_dummyserver/test_proxy_poolmanager.py` | +21, no column | |
| `test/test_ssl.py` | | +52, no column |

In `src/urllib3/connection.py`, the same file at both merge-bases (blob
84e1dab9), both change the same two places:

- in `HTTPSConnection._connect_tls_proxy`, line 861 of the merge-base, the call
  to `_ssl_wrap_socket_and_match_hostname` passes, instead of
  `cert_reqs=self.cert_reqs`, `cert_reqs=proxy_cert_reqs` in #4962, set to
  `ssl_context.verify_mode` when the proxy's `ssl_context` is not `None` and
  to `None` otherwise, and `cert_reqs=None` in #5050;
- in `_ssl_wrap_socket_and_match_hostname`, line 901, the line
  `context.verify_mode = resolve_cert_reqs(cert_reqs)` runs only
  `if default_ssl_context:`.

The tests they add: #4962, `TestConnection.test_ssl_wrap_socket_does_not_mutate_user_context`
and `TestConnection.test_connect_tls_proxy_does_not_use_target_cert_reqs` in
`test/test_connection.py`, and `TestHTTPProxyManager.test_https_proxy_ssl_context_not_mutated`
in `test/with_dummyserver/test_proxy_poolmanager.py`; #5050, a class
`TestSslWrapSocketAndMatchHostname` with
`test_caller_supplied_ssl_context_verify_mode_not_mutated`, in `test/test_ssl.py`.

### The four tests, the same in both records

| Node id | Row at M, in both records |
|---|---|
| `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_invalid_cert_file` | `src/urllib3/contrib/pyopenssl.py`, `src/urllib3/http2/probe.py` |
| `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_keyfile_with_invalid_password` | `src/urllib3/contrib/pyopenssl.py`, `src/urllib3/http2/probe.py` |
| `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_invalid_cert_file` | `src/urllib3/http2/probe.py` |
| `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_keyfile_with_invalid_password` | `src/urllib3/http2/probe.py` |

Their code is in `test/with_dummyserver/test_socketlevel.py`, the same file at
both heads and changed by neither pull request: `class
TestClientCerts(SocketDummyServerTestCase)` at line 175, whose `setup_class`
writes a CA, a certificate and keys made with `trustme` into a temporary
directory, and the two tests at lines 384 and 394:

```python
    def test_load_keyfile_with_invalid_password(self) -> None:
        assert ssl_.SSLContext is not None
        context = ssl_.SSLContext(ssl_.PROTOCOL_SSLv23)
        with pytest.raises(ssl.SSLError):
            context.load_cert_chain(
                certfile=self.cert_path,
                keyfile=self.password_key_path,
                password=b"letmei",
            )

    def test_load_invalid_cert_file(self) -> None:
        assert ssl_.SSLContext is not None
        context = ssl_.SSLContext(ssl_.PROTOCOL_SSLv23)
        with pytest.raises(ssl.SSLError):
            context.load_cert_chain(certfile=self.password_key_path)
```

`SocketDummyServerTestCase` is in `dummyserver/testcase.py`, the same file at
both heads and changed by neither: `server_thread` is a class variable, line
50, that the class method `_start_server` sets, line 72, and `teardown_method`,
which pytest runs after each test, calls `quit_server_thread` on it when the
attribute exists, lines 133 to 151:

```python
    @staticmethod
    def quit_server_thread(server_thread: SocketServerThread) -> None:
        if server_thread.quit_event:
            server_thread.quit_event.set()
        # in principle the maximum time that the thread can take to notice
        # the quit_event is LONG_TIMEOUT and the thread should terminate
        # shortly after that, we give 5 seconds leeway just in case
        server_thread.join(LONG_TIMEOUT * 2 + 5.0)
        if server_thread.is_alive():
            raise Exception("server_thread did not exit")

    @classmethod
    def teardown_class(cls) -> None:
        if hasattr(cls, "server_thread"):
            cls.quit_server_thread(cls.server_thread)

    def teardown_method(self) -> None:
        if hasattr(self, "server_thread"):
            self.quit_server_thread(self.server_thread)
```

### Their failures

In both pull requests, in the full run at H and again in the rerun, each of
the four ended with an `error` and no `failure`: `failed on teardown with
"Exception: server_thread did not exit"`, raised at `dummyserver/testcase.py:142`
from `teardown_method`, line 151, after about 5.2 s. At M, all four passed, in
0.002 to 0.005 s.

The class's tests, in the order of the JUnit files, which is the same in both
files and both pull requests. pytest writes a test that fails and then errors
in its teardown as two test cases:

| Test | At H | At M |
|---|---|---|
| `test_client_certs_two_files` | passed | passed |
| `test_client_certs_one_file` | passed | passed |
| `test_missing_client_certs_raises_error` | passed | passed |
| `test_client_cert_with_string_password` | failure, then an error in its teardown after about 5.2 s | passed |
| `test_client_cert_with_bytes_password` | failure, then an error in its teardown after about 5.2 s | passed |
| `test_load_keyfile_with_invalid_password` | an error in its teardown after about 5.2 s | passed |
| `test_load_invalid_cert_file` | an error in its teardown after about 5.2 s | passed |

The failure of `test_client_cert_with_string_password` and
`test_client_cert_with_bytes_password`, in both files and both pull requests:
`urllib3.exceptions.InsecureRequestWarning: Unverified HTTPS request is being
made to host 'localhost'.`, followed by the warning's advice; their error in
the teardown is the four's. Both failed again in the rerun and were selected:
neither record lists them among `failed_left_out`, and both runs are caught.

The runs' other failed tests: in #4962,
`test/with_dummyserver/test_https.py::TestHTTPS_TLSv1_2::test_http2_probe_blocked_per_thread`
failed again in the rerun and was selected, and
`test/contrib/test_pyopenssl.py::TestHTTPS_TLSv1_2::test_http2_probe_blocked_per_thread`
did not, the record's one `not_reproduced`. #5050's full run had no other
failed test. At M, no test failed in #4962's run, and in #5050's only
`test/contrib/test_pyopenssl.py::TestHTTPS_TLSv1_3::test_http2_probe_blocked_per_thread`.

## #5097: three parametrizations of one `TestSSL` test

| | #5097 |
|---|---|
| Run, start | 28520178605, 2026-07-01T13:13:30Z |
| CI job, in the manifest | failed in a test step, Run tests |
| H | eed4289edca6 |
| Merge-base and M | c420e267acb7 |
| Commits from the merge-base to H | one, "Deal with ssl.PROTOCOL_TLSv1 removal from Python built with OpenSSL 4+" |
| Verdict | caught, with a rerun file |

The changed paths; the record has no import-only path:

| Path | Lines | In the record's `no_column` |
|---|---|---|
| `src/urllib3/contrib/pyopenssl.py` | +3 -1 | no |
| `test/test_ssl.py` | +6 -6 | yes |
| `test/test_util.py` | +15 -9 | yes |

What the diff changes:

- `src/urllib3/contrib/pyopenssl.py`: the entry `ssl.PROTOCOL_TLSv1:
  OpenSSL.SSL.TLSv1_METHOD` leaves the dict literal `_openssl_versions`, and
  is added after it only `if hasattr(ssl, "PROTOCOL_TLSv1") and
  hasattr(OpenSSL.SSL, "TLSv1_METHOD")`.
- `test/test_ssl.py`: in the parametrizations of
  `test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors` and
  of `test_create_urllib3_context_ssl_version_and_ssl_min_max_version_no_error`,
  each `"ssl_version": ssl.PROTOCOL_TLSv1` becomes
  `"ssl_version": ssl.PROTOCOL_SSLv23`, three in each.
- `test/test_util.py`: `TestUtilSSL.test_resolve_ssl_version` takes its cases
  from a list, `candidate_version`, of three cases for `PROTOCOL_SSLv23`, and
  three for `PROTOCOL_TLSv1` only `if hasattr(ssl, "PROTOCOL_TLSv1")`. Before,
  its decorator held four cases: three for `PROTOCOL_TLSv1` and one for
  `PROTOCOL_SSLv23`.

### The three tests

| Node id | Row at M |
|---|---|
| `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs0]` | `src/urllib3/http2/probe.py`, `src/urllib3/util/ssl_.py` |
| `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs1]` | `src/urllib3/http2/probe.py`, `src/urllib3/util/ssl_.py` |
| `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs2]` | `src/urllib3/http2/probe.py`, `src/urllib3/util/ssl_.py` |

Their code is in `test/test_ssl.py`, which the pull request changed: `class
TestSSL` at line 14, and the test with its parametrization at lines 179 to
205 of H; at the merge-base, the three `ssl_version`s were `ssl.PROTOCOL_TLSv1`:

```python
    @pytest.mark.parametrize(
        "kwargs",
        [
            {
                "ssl_version": ssl.PROTOCOL_SSLv23,
                "ssl_minimum_version": ssl.TLSVersion.MINIMUM_SUPPORTED,
            },
            {
                "ssl_version": ssl.PROTOCOL_SSLv23,
                "ssl_maximum_version": ssl.TLSVersion.TLSv1,
            },
            {
                "ssl_version": ssl.PROTOCOL_SSLv23,
                "ssl_minimum_version": ssl.TLSVersion.MINIMUM_SUPPORTED,
                "ssl_maximum_version": ssl.TLSVersion.MAXIMUM_SUPPORTED,
            },
        ],
    )
    def test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors(
        self, kwargs: dict[str, typing.Any]
    ) -> None:
        with pytest.raises(ValueError) as e:
            ssl_.create_urllib3_context(**kwargs)

        assert str(e.value) == (
            "Can't specify both 'ssl_version' and either 'ssl_minimum_version' or 'ssl_maximum_version'"
        )
```

### Their failures

In the full run at H and again in the rerun, each of the three failed with
`Failed: DID NOT RAISE ValueError`, at `test/test_ssl.py:200`,
`with pytest.raises(ValueError) as e:`. At M, all three passed.

The run's other failed tests: the same three parametrizations collected from
`test/test_ssl.py`, `test/test_ssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs0]`
to `[kwargs2]`, failed the same way; and
`test_create_urllib3_context_ssl_version_and_ssl_min_max_version_no_error[kwargs0]`
to `[kwargs2]`, collected from both files, failed with `Failed: DID NOT WARN.
No warnings of type (<class 'FutureWarning'>,) were emitted.` All nine failed
again in the rerun and were selected: the record lists none of them among
`failed_left_out`, and the run is caught. Two probe tests failed in the full
run and not in the rerun, the record's two `not_reproduced`:
`test/contrib/test_pyopenssl.py::TestHTTPS_TLSv1_3::test_http2_probe_blocked_per_thread`
and `test/with_dummyserver/test_https.py::TestHTTPS_TLSv1_2::test_http2_probe_blocked_per_thread`.
At M, two tests failed, and no other:
`test/contrib/test_pyopenssl.py::TestHTTPS_TLSv1_2::test_http2_probe_blocked_per_thread`
and `test/contrib/test_pyopenssl.py::TestHTTPS_TLSv1_3::test_http2_probe_blocked_per_thread`.

## The classification

Classified by the user on 2026-11-21 (D-023), from this note and a reading of
the code, with no new run, by D-021's causes as D-022 applies them. Each row
counts once (D-021): these 11 and D-017's 3 are the share's 14. The reasons
are the user's, translated from Spanish.

| Pull request | Node id | Cause | Why |
|---|---|---|---|
| #4962 | `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_invalid_cert_file` | O | reason a |
| #4962 | `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_keyfile_with_invalid_password` | O | reason a |
| #4962 | `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_invalid_cert_file` | O | reason a |
| #4962 | `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_keyfile_with_invalid_password` | O | reason a |
| #5050 | `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_invalid_cert_file` | O | reason a |
| #5050 | `test/contrib/test_pyopenssl.py::TestClientCerts::test_load_keyfile_with_invalid_password` | O | reason a |
| #5050 | `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_invalid_cert_file` | O | reason a |
| #5050 | `test/with_dummyserver/test_socketlevel.py::TestClientCerts::test_load_keyfile_with_invalid_password` | O | reason a |
| #5097 | `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs0]` | C | reason b |
| #5097 | `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs1]` | C | reason b |
| #5097 | `test/contrib/test_pyopenssl.py::TestSSL::test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors[kwargs2]` | C | reason b |

- Reason a: "An error in the teardown: server_thread did not exit. The thread
  is left behind by earlier tests that the change affected; D-022 classifies
  this propagation between tests as O."
- Reason b: "The pull request changes PROTOCOL_TLSv1 to PROTOCOL_SSLv23 in
  test/test_ssl.py, imported code that the coverage does not measure. At H and
  in the rerun the expected ValueError is not raised; at M it passed."
- The user's note on the whole: "11 cases: 8 O and 3 C. The eight O are
  propagation through a thread left by another test, as D-022 says. The
  certificates are generated in a temporary directory and are not files of
  the repository that the pull request changed. The classification rests on
  the note and on a review of the code; no new runs were made."

## The share, and what section 13.2 can conclude

By D-021's rule, with the report's `clopper_pearson_upper`:

| Cause | Failed tests left out |
|---|---|
| F, a file dependency | 0 |
| C, code that the coverage does not measure | 3, #5097's |
| N, a cause other than the change | 3, D-017's |
| O, any other cause | 8, #4962's and #5050's |
| All | 14 |

- The share of file dependencies is 0 out of 14. Its one-sided 95% upper bound
  is 19.3%, above 10%, and its lower bound, 1 minus the upper bound of 14 out
  of 14, is 0%, below 10%: by D-021 the share is undecided, neither marginal
  nor not marginal.
- No failed test left out of the window came from a file dependency, and so
  no miss did either.
- Marginal at 10% takes at least 29 classified failed tests left out with no
  file dependency: 0 out of 29 gives 9.8%, and 0 out of 28 gives 10.1%. The
  window has no more to classify, so the other 15 would have to come from pull
  requests whose figures nobody has seen (option B of the note of options).
- The 14 are not 14 independent draws, as the bound takes them: they are the
  same 4 tests in two pull requests that change the same two places of
  `src/urllib3/connection.py`, 3 parametrizations of one test, and one flaky
  test function under three classes (D-021).
- The no-column rate is judged only on pull requests whose no-column rate
  nobody has seen (D-021), so nothing about "low" follows from the window.

INFERENCE: the window gave its 14 failed tests left out over 52 pull requests
with a red run, in 6 of them. At that rate, 15 more would take some 56 more
pull requests with a red run, about another window; since they come in
bundles, the real count could be far from that.

## Where each fact comes from

- The records: the lines of #4962, #5050 and #5097 in
  `2026-11-19-window-records-urllib3.jsonl`; the runs and the CI job's
  outcome: `2026-11-17-window-red-runs.csv`.
- The diffs, with `git -C ~/code/distiller-pilots/urllib3 diff <merge-base> <H>`:
  - #4962: `c21b1c16cd8c08dd26876e223bc198a2b4de4fb3` to
    `ae81f84b758e94fe7c51212c320b03518f9d7d7e`;
  - #5050: `c2a56d9e524344c715ecbb891fcd25f962a67405` to
    `8456785e9914d0665943e2770916c3198a8a2821`;
  - #5097: `c420e267acb739917bee96e021ad9a2d27de8aae` to
    `eed4289edca6ee92c0116c6266c8e42267c159ef`.
- The code, with `git show <H>:<path>` in the same clone.
- The outcomes and messages: each test case of `junit.xml`, `rerun.xml` and
  `junit-m.xml` in `~/code/distiller-replay/urllib3/<pr>/`, read with
  defusedxml, and the lists of failed tests beside them, `junit.xml.failed`,
  `rerun.xml.failed` and `junit-m.xml.failed`. #4962 has no
  `junit-m.xml.failed`, and its `junit-m.xml` holds no `failure` and no
  `error`.
