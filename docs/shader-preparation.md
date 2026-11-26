# The shader preparation at a build

How a build prepares the game's shaders before the first start, what happens when the GPU driver dies or hangs on one
of them, and the files this leaves in the game folder's `cache/`.

## The run

A build's last step starts the game it has just built with `--prepare-shaders`
(`nx2/make_game.py` `prepare_shaders`; `scripts/dev_packs.py` `prepare` for a development base or runtime). The game
starts the Vulkan renderer with no window and no game, does what a first start does and exits
(`gpu/vk/vk_main.cpp` `started_up`):

1. **The shader programs** (`prepare_run`): every program of `hookshot_shaders.bin` translated, its shader modules
   created, each compute program's pipelines built.
2. **The predicted pipelines** (`predict_run`): only with Compile shaders on All.
3. **The noted pipelines** (`precompile_run`, `precompile_warm`): every pipeline the lists name, built into the
   pipeline cache and let go.
4. The pipeline cache written out.

Its progress goes to the Builder as `@@stage` and `@@progress` lines. A preparation that fails is never a failed build:
the build says `the shaders were not prepared now (<why>)` and the game prepares them at its first start.

Three calls of this run enter the driver's compiler: `vkCreateShaderModule`, `vkCreateGraphicsPipelines` and
`vkCreateComputePipelines`. Each goes through a guard in `gpu/vk/vk_draw.cpp` (`guarded_shader_module`,
`guarded_graphics`, `guarded_compute`) that catches an access violation on the calling thread, answers it as a failure
of that one call and has the program written to `cache/hookshot_driver_faults.txt` (`gpu/vk/driver_faults.h`), so
that it is not handed to that driver again. The guards cannot catch a driver that ends the process another way (a
fault on a thread of its own, an abort, a stack overflow) or that never returns. Before the supervisor, such a run
was lost whole, and the game's first start then died or hung in the same shader.

## The journal

A run started with `--prepare-journal <file>` appends one line to that file before each of those calls and one after
it (`gpu/vk/prepare_journal.h`; the calls are journalled in `vk_draw.cpp`'s `extern_guarded_shader_module`,
`guarded_graphics_held` and `guarded_compute_held`). A game run, and a preparation not given the argument, write
nothing and pay one read of a bool per call.

```
run <vendor> <driver> <from>
b <seq> <kind> <vendor> <driver> <program> <detail>
e <seq> <result> <ms>
t <seq> <s>
```

- `run`: a process opened the journal. Its entries are numbered from `<from>` + 1.
- `b`: before the call. `<kind>` is `module`, `graphics` or `compute`. `<vendor> <driver> <program>` is the text of a
  line of `hookshot_driver_faults.txt` (`driver_faults::line`: the vendor id, `driverVersion` and the program's key,
  in hex). Program 0 is a shader of the renderer's own. `<detail>` is the module's size or the pipeline's create flags.
- `e`: after it, with the `VkResult` in decimal (`-77`: a fault the guard caught) and the milliseconds it took.
- `t`: the entry has been open for `<s>` seconds, longer than one gets. The run ends itself right after.

A pipeline's create info names its shader modules, not its program, so the run remembers which program each module
was made for and names a pipeline by its first module that has one.

**Durability.** The file is opened once for appending. Each line is one `fwrite` followed by `fflush`, under one
lock, before the driver is entered. `fflush` hands the line to the operating system (`write` on Linux, `WriteFile`
through the C runtime on Windows); from then on it is in the system's file cache and reaches the file however the
process ends (a signal, `TerminateProcess`, an unhandled exception, `_Exit`). There is no `fsync` or
`FlushFileBuffers`: a power loss is not covered, and would cost a disk write per shader. A reader skips a last line
with no line end and treats the journal as incomplete. A `.pending` marker is created before each write and removed only
after a successful flush. A write, flush or marker error ends the run with status 7; a surviving marker or incomplete line
also prevents the supervisor from attributing the run to a program, even if the process died for another reason.

## The run's arguments and exit statuses

The supervisor's arguments reach the renderer as switches (`host/prepare_args.h`), as `--compile-shaders` does:

| Argument | Switch | What it does |
|---|---|---|
| `--prepare-journal <file>` | `HOOKSHOT_PREPARE_JOURNAL` | Keeps the journal |
| `--prepare-entry-limit <s>` | `HOOKSHOT_PREPARE_ENTRY_S` | An entry open for longer is named with a `t` line and the run ends with status 6 |
| `--prepare-from <n>` | `HOOKSHOT_PREPARE_FROM` | Started again past entry n: entries are numbered from n + 1, and the run before is taken off the steps' crash markers (below) |
| `--prepare-skip <file>` | `HOOKSHOT_PREPARE_SKIP` | `skip <program>`: never handed to the driver, its calls answer as a preparation skip. `alone <program>`: a suspect; all calls are serialized during diagnosis |

| Exit status | Meaning |
|---|---|
| 0 | Prepared |
| 3 | No usable Vulkan on this PC |
| 4 | Nothing moved in the whole run for `RX_VK_PREPARE_STALL_S` (300 s): the run left `hookshot_prepare_skipped` and gave up (`prepare_watchdog`). Unchanged |
| 6 | One journalled entry passed its limit; the journal's `t` line names it (`prepare_entry_watch`) |
| 7 | The journal or its marker could not be written or flushed; no program is attributed to this run |
| anything else | The process died: a signal on Linux, an exception code on Windows |

**Where a run started again goes on.** It does not skip work by number: what the run before finished is in the caches
(the program cache keeps each translated program, the driver's own cache what it compiled), so the same steps go
through it quickly, and the pipeline cache file is built again in this process. `--prepare-from` keeps the entry
numbers going and forgives the crash markers: each step of a start (`gpu/vk/crash_markers.h`) counts the starts that
died inside it and is let go after one or two, with its notes. A death the journal has explained is not such a
start, so the run puts each marker back one start (`vk_draw.cpp` `prepare_restart_forgive`).

## The supervisor

`nx2/prepare_supervisor.py` `supervise` starts the run with a journal and a limit per entry
(240 s, below the run's own 300 s so that a stuck shader is named before the whole run gives up;
`HOOKSHOT_PREPARE_ENTRY_S` in the Builder's environment sets another, 0 none). After each run it reads the journal:

| The run ended | The journal's last run left open | Then |
|---|---|---|
| 0 | | Done |
| 3, or 4 | | Given up, as before |
| 7, incomplete line, or pending marker | | Given up without attributing the run |
| 6 | the entry its `t` line names | That program is the culprit, "timed out" |
| died, or stopped for 15 minutes of silence | entries of one program | That program is the culprit ("crashed"; "timed out" after silence) |
| | entries of several programs (several threads were compiling) | Started again with those as suspects; all driver calls are serialized so a subsequent death has only one call open |
| | only shaders of the renderer's own | Given up: no list can leave those out |
| | a program that was already left out | Given up: the run does not follow the list |
| died | nothing | Started once more as it was; a second such death gives up |
| silence | nothing | Given up, as before |

A crashed culprit is appended to `cache/hookshot_driver_faults.txt` at once. A timed-out program is skipped only for this
preparation: a slow compile may complete if tried again in the game. The run is started again with
`--prepare-from <the journal's last entry>` and `--prepare-skip`. **Bounds:** 8 culprits (the ninth is listed too, and
the preparation is then given up) and 20 starts in all. Giving up is what a failed preparation always was; the
crashed culprits found until then stay listed. The 240 s limit still needs validation on slow hardware.

The Builder's log gets a line for each culprit and each restart, starting with `shader preparation:`.

## What is left in cache/

- `hookshot_driver_faults.txt`: one `<vendor> <driver version> <program key>` line for each crashed culprit, as the game's own
  guards write them.
- `hookshot_prepare_results.txt`: the result list of the last supervised preparation that kept a journal: the driver,
  the number of runs, how it ended, the totals (`built`, `cold`, `failed`, `faulted`, `crashed`, `timed-out`,
  `interrupted`), a row for each program left out, a row for every other entry that was not built, and the 20 slowest
  that were. `cold` is an ask that compiles nothing and found no cache; `interrupted` is an entry that was open when a
  run ended and was not named the culprit.
- The journal (`hookshot_prepare_journal.txt`), its `.pending` marker, and the list for the next run (`hookshot_prepare_skip.txt`) exist only
  while a preparation runs.

All of it is made from the game on the player's PC and stays there.

## What the game does with a culprit

Nothing new. At its first driver compile the game reads `hookshot_driver_faults.txt` and keeps the lines of its own
vendor and driver version (`driver_faults::parse`, `vk_draw.cpp` `fault_quarantine`), logging
`vk: N programs the driver faulted on in earlier runs are not asked of it`. For such a program `make_module` makes no
shader module and `build_graphics` builds no pipeline (`vk: a pipeline of <key> left out: the driver faulted on that
program`), so its draws are left out. A driver update has another `driverVersion` and tries them again; so does
deleting the file. `RX_VK_DRIVER_FAULTS=0` turns the list off.

The unit left out is the program, as it is for a fault caught in play: one pipeline state that kills the driver takes
every draw of its program with it.

## Testing it

- `python -I -B tests/test_prepare_journal.py`: the writer compiled alone and killed inside an entry, read back by
  the supervisor's parser; the game's own reader on the line the supervisor appends.
- `python -I -B tests/test_prepare_supervisor.py`: the policy against a stand-in game that dies or hangs in given
  programs, on one thread and on several.
- In the game, `RX_VK_TEST_PREPARE_FAULT` makes a journalled preparation die (`crash:`) or never return (`hang:`)
  in the first driver call of chosen programs, as a driver that fails on those shaders: `crash:<n>` every program
  whose key is a multiple of n (about one in n; `crash:1` is a driver that fails on everything, for the bounds),
  `crash:=<key>` one program. The same programs in every run, so the suspects' run meets the same one again; an
  entry number would not be the same entry in two runs on several threads. On a built game folder:

  ```
  RX_VK_TEST_PREPARE_FAULT=crash:=<key> python -I nx2/prepare_supervisor.py <game folder>
  RX_VK_TEST_PREPARE_FAULT=hang:=<key> python -I nx2/prepare_supervisor.py <game folder> --entry-limit 20
  ```

  (a key: any program of an earlier `cache/hookshot_prepare_results.txt`'s slowest rows.) The preparation then
  finishes after two or three starts, `hookshot_prepare_results.txt` names the program, and the game's next start
  logs that one program is not asked of the driver. Delete the program's line from
  `cache/hookshot_driver_faults.txt` afterwards. The preparation only has entries where it has work: in a folder
  that is already prepared and warmed, delete `cache/hookshot_pipelines.bin.built` first.
