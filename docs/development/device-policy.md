# The rules by the PC

What the renderer decides by the PC it runs on (the GPU's vendor and driver, its memory, the PC's RAM and CPU count, the
OS) is moving into one file, `gpu/vk/device_policy.h`. This page says how it is laid out, how the switches over those
rules are read, how to read the log's `vk: policy:` lines, and what to do when a rule is added or changed.
`tests/test_device_policy.py` runs every rule on made-up PCs, with no game and no GPU.

## The three parts

- **`DeviceFacts`** is what `create_device` (`gpu/vk/vk_main.cpp`) learns of the PC, once, before the device is made:
  the vendor, device and driver ids, the driver's version and what it says of itself, the kind of GPU, the VRAM heap and
  what the driver allows at the start, the RAM, the CPU counts, and what the card can do (mesh shaders, the float add,
  subgroup sizes). A rule asks the facts, never Vulkan, so the check can make any PC up.
- **`device_policy(facts)`** gives the defaults: what each rule gives this PC with no switch set. It reads nothing else.
- **`device_policy_env(policy, facts, get)`** applies the switches, by one rule (below), and notes which fields a switch
  set (`policy.set(Sw::...)`) and which values it ignored.

The result is `dev.policy` (`gpu/vk/vk_internal.h`). The header is no file of the shader translation's stamp
(`nx2/translator_files.py`: `vk_shader.cpp`, `vk_bank.cpp`, `vk_state.h`, `eden/`, `sirit/`, `compat/`; an edit to one of
those has every player translate every program again), and of those files only `vk_shader.cpp` reads `dev.policy`. So a
rule the translation reads, when it is changed in the header, reaches the program cache only through the values
`translator_stamp` folds: each field `vk_shader.cpp` reads is folded there, itself or as the profile's value made from
it and its switch, and the check fails for a field that is read and not folded.

## Which rules are read from it

Each field's comment in the header says who decides. **Read**: the site uses `dev.policy`, and its switch is read by
`device_policy_env`. **Site**: the field is worked out by the same rule, for the log and the check, while the site still
decides with its own switch read; the step named in the comment moves it.

Read today: ASTC on the CPU, batched submits, serial compute builds, the pipeline cache's fetch lock, the part split
before a draw, the uniform snapshot, the uniform updates at each part's end, the occlusion copies, the mirrors, FSR 4's
tuning, invariant positions, the equal-depth margin, one program's builds at a time, the background workers and the
preparation's workers in play; and the shader translation's: the three vendor fixes that were `vk_vendor.h`'s
(out-of-bounds fetches, NaN tests on bits, the gather offset), the fragment shuffles' fallback, the long warp path, the
Deku Tree web's inlined loads and the networks left out. The mesh mode's rule for RADV is the header's too, but
`create_device` asks the driver itself, as the mode is chosen before the facts are whole.

The translation's switches keep their own reading for now. `RX_VK_FETCH_BOUNDS`, `RX_VK_NAN_BITS` and
`RX_VK_GATHER_OFFSET` are read by `device_policy_fixes_env` as numbers (0 off, another number on, a word off), not by the
one rule below; `RX_VK_WARP64` and `RX_VK_FRAG_SHUFFLE_FALLBACK` are read in `make_profile` (a value that starts with 1
on, any other off), and `RX_VK_NETWORK_KEEP` where the networks are left out.

The sizes that go by the driver's allowance (the spare capture buffers, the staging arenas kept, the damped squeeze, an
integrated GPU's texture budget) are written once, in `policy_rule`, and their sites call the rule with the allowance at
their own first use, after the renderer has allocated. The policy's own numbers use the allowance at the start, so the
log's can be higher than what a site gets. A switch for one of them is read by `device_policy_env`, and the site takes
the field when `policy.set(...)` says so.

Still decided at their sites, by rules the header repeats: the rest of device creation (the task + mesh
fallback, the float add's extension, the checkpoints, the presenter's queue), chosen before the facts are whole; the
texture uploads' thread counts, in functions that checks compile with no device; and the rules a tested header of
their own already holds (the texture and mirror budgets, the blocks at the start, the retired imports, the auto
settings, the GPU clock, the pipeline cache's load).

## The switches' one rule

For every switch `device_policy_env` reads:

- **A yes/no switch**: unset or empty is the PC's default; `0`, `false`, `off` and `no` (any case, spaces around them
  not counted) are off; any other value is on.
- **A number**: decimal digits only, in the field's range (`RX_VK_EQ_BIAS` may have one point). Anything else (a sign, a
  space, a word, a number out of range) is ignored: the default stays, and the log's last `vk: policy:` line says so.
- Two switches only turn their rule off: `RX_VK_FSR4_TUNE` (an off word turns the tuning off; no value turns it on off
  AMD's GPUs) and `RX_VK_NO_INVARIANT` (on takes the invariant positions away).

Before this rule each site parsed its own switch, in seven ways. What changed with it:

| Switch | Value | Before | Now |
|---|---|---|---|
| `RX_VK_BATCH`, `RX_VK_MIRROR`, `RX_VK_OCC_COPY` | a word that is no number (`on`, `true`, `yes`) | off | on |
| the same three | `00`, or another number spelt unlike `0` that is zero | off | on |
| `RX_VK_COMPUTE_SERIAL` | anything not beginning with `1` that is no off word (`true`, `on`, `2`) | off | on |
| `RX_VK_ASTC_CPU`, `RX_VK_BATCH`, `RX_VK_COMPUTE_SERIAL`, `RX_VK_MIRROR`, `RX_VK_OCC_COPY`, `RX_VK_PCACHE_FETCH_LOCK` (Windows), `RX_VK_SPLIT_BEFORE_DRAW`, `RX_VK_SPLIT_UBFLUSH`, `RX_VK_UB_SNAPSHOT` | empty | off | the PC's default |
| `RX_VK_FSR4_TUNE` | a word that is no number and no off word (`abc`, `on`), or `00` | off | the PC's default |
| `RX_VK_EQ_BIAS` | empty, a word, a negative number | off (0) | the PC's default, said in the log (empty: not said) |
| `RX_VK_EQ_BIAS` | `1e2`, `64.`, `.5` and other forms that are not digits with one point, or over 65536 | as `atof` read them | ignored |
| `RX_VK_WORKERS` | `0`, a negative number, a word, empty | 1 | the PC's default, said in the log (empty: not said) |
| `RX_VK_WORKERS` | over 16 | 16 | the PC's default, said in the log |
| `RX_VK_WORKERS` | a number with a space or letters around it (` 4`, `4x`) | 4 | ignored |
| `RX_VK_CAP_SPARE_MB` | empty, a word | no limit | the PC's default |
| `RX_VK_CAP_SPARE_MB` | a negative number | a huge limit | ignored |
| `RX_VK_STAGING_KEEP_MB` | empty, a word | 0 (no arena kept) | the PC's default |
| `RX_VK_STAGING_KEEP_MB` | a negative number | a huge size (every arena kept) | ignored |
| the three sizes and the workers | digits followed by anything (`64MB`) | the digits | ignored |

`0` and `1` mean what they did on every one of them, and `RX_VK_NO_INVARIANT` reads every value as it did.

## The log's lines

After `vk: driver:` the start logs six lines:

```
vk: policy: facts 1002:73df, driver id 1, version 0x800161 (26.10.1 (AMD proprietary shader compiler)), type 2, Windows; VRAM ...
vk: policy: driver fixes on driver version 0x800161: fetch_bounds=1 ... task_mesh_fallback=1(seen on 0x800161) ...
vk: policy: can and measured: mirrors=1 import_chunk=4 MB ... batch_submits=0 ...
vk: policy: sizes by the allowance at the start (the sites read it later): textures 7158 MB, mirrors 2048, ...
vk: policy: auto settings and threads: auto_tier=4 ...; workers 4, ...
vk: policy: switches (* above: set by its switch; the other values are this PC's defaults): RX_VK_BATCH=1; RX_VK_WORKERS=abc ignored (not a whole number in its range)
```

- A `*` after a value says its switch set it; the last line names those switches with their values, and every value that
  was ignored. Without a `*` the value is the PC's default.
- A field its site still decides shows the default only: that site's own switch is not in it (`vk: switches set` at the
  start lists every switch the run set).
- A driver's fix that is on says the driver version it was seen on, where the report it came from names one, beside the
  version this PC runs (`on driver version ...`). No rule has an upper bound yet: none has a report of a driver that
  fixed it. A report whose log shows a fix on with a much newer driver is where to look for one.

## Adding or changing a rule

1. The rule goes in `device_policy()`, as a test of the facts: the **driver** (`driver_id`) when the reason is one driver's
   code, the vendor only when it is the hardware's; a version bound when the report names a driver that fixed it. Its
   field's comment says the PCs it is for, why, the issue, the driver version it was seen on, and its switch.
2. A fact it needs and the struct lacks is added to `DeviceFacts` and filled in `create_device`.
3. Its switch, if it has one, is read in `device_policy_env` by the one rule, has a value in the `Sw` enum, and a row in
   `gpu/vk/switches.def`. Prefer no switch, or a default right for every PC, to a new one.
4. The site reads `dev.policy`. It does not ask Vulkan, the vendor id or the environment again.
5. `tests/test_device_policy.py` gets the field (`BOOLS` or `NUMS`), its value on every made-up PC, and a case for its
   switch; a check that compiled the site's rule includes `device_policy.h` and makes the policy instead.
6. A rule that changes what a GPU gets says so in the pull request, with the GPUs and how.

## Rules corrected when they moved

Each is one line in `device_policy()` with a comment that says how to go back.

| Rule | Before | Now | Who gets something else |
|---|---|---|---|
| Compute for mesh programs under Automatic (`mesh_mode`, issue 2245) | AMD's GPUs off Windows | Mesa's RADV | AMDVLK on Linux: its own mesh shaders (it had the compute path). Nothing was run on AMDVLK either way; `RX_VK_MESH_SHADERS=compute` is the old answer |
| One program's builds one at a time (`fault_gate_serial`, issue 996) | every AMD GPU | AMD's Windows driver | RADV and AMDVLK: a program's variants build side by side, as on NVIDIA and Intel. `RX_VK_DRIVER_FAULTS=2` is the old answer |
| Compute pipelines built one at a time (`compute_builds_serial`, issue 496) | every Intel GPU | Intel's Windows driver | Mesa's Intel driver (ANV): compute pipelines build on the background workers. `RX_VK_COMPUTE_SERIAL=1` is the old answer |
| Batched submits not on GCN (`batch_submits`) | RADV with no stage pinned to 32 lanes and 64-lane waves | RADV without 16-bit stage inputs (GCN 1-4, the definition the fallback's phi limit uses) | RADV on Vega and the Raven Ridge and Picasso APUs (GFX9): batched submits on (they were off). RADV with `RX_VK_NO_SUBGROUP_PIN=1` on a 64-lane card: on (the switch turned them off). `RX_VK_BATCH=0` is the old answer |

## Rules left as they are, and why

These look keyed on the wrong fact, and each needs a run on hardware to settle:

- **The float add's list** (`native_fadd_listed`): NVIDIA's driver and three Intel families on Windows. Lunar Lake, Arc A
  and Iris Xe keep the loop that lost adds on their siblings; it needs one run each, and on AMD's and Mesa's drivers.
- **The equal-depth margin, the part split before a draw, the uniform snapshot** ask for Intel, the vendor, so Mesa's
  driver gets them too. Their reports are from Intel's Windows driver, but none names the compiler or the cause.
- **Invariant positions, out-of-bounds fetches, the Deku Tree web's loads** ask for "not NVIDIA" or "NVIDIA", so NVK
  counts as NVIDIA's compiler. Needs a run on NVK.
- **Unoptimized task and mesh programs** (`mesh_no_optimizer`) are on for AMDVLK and for AMD's Windows driver on RDNA 3
  and 4, where nothing was measured.
- **The uniform updates at each part's end and the snapshot** are by Intel where the reason is "no mirrors".
- **The small cards' sizes**: the mirrors' third of the card up to 6.5 GB (a 4 GB card gets 1365 MB where
  `mirror_budget.h` argues for 256), the thresholds around 8 GB that compare differently (`<` and `<=`), and a GPU that is
  neither discrete nor integrated getting a dedicated card's budgets.
- **The worker counts' steps** (2 workers up to 8 threads, 4 at 15, 6 at 16).
