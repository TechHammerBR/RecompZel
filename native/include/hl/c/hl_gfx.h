/* Hookshot native engine: the graphics front end's C surface for the layer that runs guest code (engine/host/hl_gfx.c).
   docs/native-engine/gfx-record-job.md has the plan and the check. */
#ifndef HL_C_GFX_H
#define HL_C_GFX_H

#include <stddef.h>
#include <stdint.h>

#include "hl/c/hl_bridge.h"

#ifdef __cplusplus
extern "C" {
#endif

enum { HL_GFX_OFF = 0, HL_GFX_SHELL = 1 };

/* Starts the front end (once; the host must outlive the process). mode: HL_GFX_*. check: 1 to keep the pass check (the
   OS layer then feeds it every NVN call a pass makes, and runs each pass on the path hl_gfx_check_next_native says).
   Returns 1 when the native pass is in use. */
int hl_gfx_start(const hl_guest_host *host, int mode, int check);

/* The guest address of the pass's listener (answered), and the native pass: call it with the listener's two arguments on
   the thread that runs the listener. Returns the listener's result. */
uint64_t hl_gfx_pass_address(void);
uint32_t hl_gfx_record_pass(uint64_t listener, uint64_t args);

/* The check. Per pass: next_native says which path it takes (1 native, 0 the translated listener); begin starts the
   calling thread's recording (args: the pass's argument block, whose mode it reads before the pass); call adds one NVN
   call to it (op: the OS layer's number of the procedure; x: x0..x7; f: the low 32 bits of s0..s3); end files it. */
int hl_gfx_check_next_native(void);
void hl_gfx_check_begin(uint64_t args);
void hl_gfx_check_call(uint32_t op, const uint64_t *x, const uint32_t *f);
void hl_gfx_check_end(int native);

/* One line of counters for the log (op_names: the procedures' names by op, n_names of them). Returns the length written. */
int hl_gfx_report(char *out, size_t cap, const char *const *op_names, size_t n_names);

/* ---- the render-state function (guest 0x80077d60: called directly, answered through an entry gate) ---- */

/* The NVN procedures native code calls, in the native side's numbering (hl/gfx/Nvn.h): how many, each one's NVN name,
   and the game's global that holds it (the OS layer checks that the procedure it calls is the one the game calls). */
uint32_t hl_gfx_nvn_count(void);
const char *hl_gfx_nvn_name(uint32_t proc);
uint64_t hl_gfx_nvn_global(uint32_t proc);

typedef struct hl_gfx_host {
    void *user;
    /* calls NVN procedure `proc` on the calling thread's guest context: x[0..nx) in x0.., f[0..nf) in the low 32 bits
       of s0..; returns x0 after the call (a query's answer) */
    uint64_t (*nvn)(void *user, uint32_t proc, const uint64_t *x, uint32_t nx, const uint32_t *f, uint32_t nf);
    /* n bytes of guest memory at `guest` were written by native code */
    void (*written)(void *user, uint64_t guest, uint64_t n);
    /* one line for the log (the check's mismatches) */
    void (*log)(void *user, const char *line);
} hl_gfx_host;

/* Starts the native render-state function (once; the hosts must outlive the process). check: 1 to compare each call
   (below) instead of answering it. Returns 1. */
int hl_gfx_state_start(const hl_guest_host *host, const hl_gfx_host *gfx, int check);
uint64_t hl_gfx_state_address(void);

/* The native answer, on the thread that runs the call (block x0, key w1, sp the caller's stack pointer): writes the
   block and calls the NVN procedures. Returns 1 when it answered, 0 when the call reaches guest code the native version
   does not run (the material's state callback): the translated body must run. */
int hl_gfx_state_apply(uint64_t block, uint64_t key, uint64_t sp);

/* The check, per call: begin runs the native version into a recording (no procedure called, nothing written) and
   returns 1 when it would answer (0: not compared; run the translated body as always); then the caller runs the
   translated body with the tap feeding call (proc: the native numbering, hl_gfx_nvn_count or more for a procedure the
   native side does not know; x: x0..x7; f: s0..s3); end compares the calls and the block's bytes. */
int hl_gfx_state_check_begin(uint64_t block, uint64_t key, uint64_t sp);
void hl_gfx_state_check_call(uint32_t proc, const uint64_t *x, const uint32_t *f);
void hl_gfx_state_check_end(void);

/* One line of the render-state function's counters. Returns the length written. */
int hl_gfx_state_report(char *out, size_t cap);

/* ---- the sub-mesh submission (guest 0x80078fc0: called directly, answered through an entry gate) ---- */

/* Starts it (once; the hosts must outlive the process). check: 1 to compare each call in segments instead of answering
   it. Returns 1. */
int hl_gfx_draw_start(const hl_guest_host *host, const hl_gfx_host *gfx, int check);
/* The function, its shared preparation (called back between the prologue and the submission), the link register the
   function's own call of it leaves, and the frame the function sets up before that call. */
uint64_t hl_gfx_draw_address(void);
uint64_t hl_gfx_draw_prepare_address(void);
uint64_t hl_gfx_draw_prepare_return(void);
uint64_t hl_gfx_draw_frame(void);

/* The native answer, on the thread that runs the call (x0 drawable, x1 block, w2 sub-mesh, w3 mask). begin returns 0
   when the call is left to the translated body (not a direct path), 1 when it answered whole (the sub-mesh is out of
   range), 2 when the caller must now call the preparation (x0 the block, x1 the drawable, w2 0; on the same context,
   its stack pointer lowered by the frame) and then end with its result. */
int hl_gfx_draw_begin(uint64_t drawable, uint64_t block, uint32_t sub_mesh, uint32_t mask);
void hl_gfx_draw_end(uint64_t prepared);

/* The check, per call: begin runs the native prologue into a recording and returns 1 when the call is compared (a
   direct path; 0: run the translated body as always). The caller then runs the translated body with the tap feeding
   call (as for the render state). At the checkpoint, the preparation's entry from that body: segment closes the
   prologue's segment (compares it); the caller runs the translated preparation with the tap paused, then prepared runs
   the native submission on what it left into a recording (it asks NVN queries through the table: keep the context's
   registers around it); the tap resumes. end compares the submission's segment (or the prologue's, when the body
   returned without reaching the checkpoint). */
int hl_gfx_draw_check_begin(uint64_t drawable, uint64_t block, uint32_t sub_mesh, uint32_t mask);
void hl_gfx_draw_check_segment(void);
void hl_gfx_draw_check_prepared(uint64_t prepared);
void hl_gfx_draw_check_call(uint32_t proc, const uint64_t *x, const uint32_t *f);
void hl_gfx_draw_check_end(void);

/* One line of the submission's counters. Returns the length written. */
int hl_gfx_draw_report(char *out, size_t cap);

/* ---- the shared preparation (guest 0x8008fc00: called directly, answered through an entry gate on its cached path) ---- */

/* Starts it (once; the hosts must outlive the process). check: 1 to compare each call instead of answering it; state: 1
   to take the state step natively too (else a call that needs it is left to the translation). Returns 1. */
int hl_gfx_prep_start(const hl_guest_host *host, const hl_gfx_host *gfx, int check, int state);
uint64_t hl_gfx_prep_address(void);

/* The native answer, on the thread that runs the call (x0 block, x1 drawable, sp the caller's stack pointer): returns 1 when it answered, with the
   function's result in *result (the block and the command buffer written, the NVN call made), 0 when the call leaves
   the cached path: the translated body must run. Every call is counted by the route it takes. */
int hl_gfx_prep_apply(uint64_t block, uint64_t drawable, uint64_t sp, uint64_t *result);

/* The check, per call: begin decides natively into a recording (nothing called, nothing written) and counts the route;
   the caller then runs the translated body with the tap feeding call (proc: the native numbering; group: the
   procedure's kind, HL_GFX_PREP_GROUP_*); end compares the calls, the bytes and the result when the native version
   would have answered, and files the call's shape (its route and how many calls of each kind) in the paths' histogram. */
enum {
    HL_GFX_PREP_GROUP_OTHER = 0,
    HL_GFX_PREP_GROUP_STATE,      /* the render state's setters and binds */
    HL_GFX_PREP_GROUP_PROGRAM,    /* BindProgram */
    HL_GFX_PREP_GROUP_UNIFORM,    /* BindUniformBuffer */
    HL_GFX_PREP_GROUP_STORAGE,    /* BindStorageBuffer */
    HL_GFX_PREP_GROUP_TEXTURE,    /* BindTexture(s), texture handles and views */
    HL_GFX_PREP_GROUP_CALL,       /* CallCommands */
    HL_GFX_PREP_GROUPS
};
void hl_gfx_prep_check_begin(uint64_t block, uint64_t drawable, uint64_t sp);
void hl_gfx_prep_check_call(uint32_t proc, uint32_t group, const uint64_t *x, const uint32_t *f);
void hl_gfx_prep_check_end(uint64_t result);

/* One line of the preparation's counters (routes, the check), and one line of its histogram's most frequent shapes (0
   when there is none). Return the length written. */
int hl_gfx_prep_report(char *out, size_t cap);
int hl_gfx_prep_shapes(char *out, size_t cap);

/* ---- the key-0xa0 draw function (guest 0x8008d640: reached through the item body's table, answered by pointer) ---- */

/* One call: x0 the list of draw entries, w1 their count, x2 the render-state block, x3 the key's first word, w5 the
   item's flags, and the stack pointer at the entry. */
typedef struct hl_gfx_var_call {
    uint64_t list;
    uint32_t count;
    uint64_t block, mask;
    uint32_t flags;
    uint64_t sp;
} hl_gfx_var_call;

/* What the native loop calls back, on the thread that runs the call: the translated function on a sublist of the
   entries (the function is a loop over its list and keeps nothing between entries but the block), and the shared
   preparation (x0 block, x1 drawable; the function's own frame below the stack pointer `sp`), returning its w0. */
typedef struct hl_gfx_var_host {
    void *user;
    void (*translate)(void *user, uint64_t list, uint32_t count);
    uint64_t (*prepare)(void *user, uint64_t block, uint64_t drawable, uint64_t sp);
    /* the check: 1 while the translated function runs on an entry the native version answers (the OS layer's tap then
       feeds hl_gfx_var_check_call, and the preparation's gate hl_gfx_var_prep_begin / _end), 0 after */
    void (*recording)(void *user, int on);
} hl_gfx_var_host;

/* Starts it (once; the hosts must outlive the process). native: 1 to answer the entries of the plain path natively, 0
   to only classify them (every entry is then run by the translation). check: 1 to compare each native entry with the
   translated one (see hl_gfx_var_check_*). Returns 1. */
int hl_gfx_var_start(const hl_guest_host *host, const hl_gfx_host *gfx, int native, int check);
uint64_t hl_gfx_var_address(void);
uint64_t hl_gfx_var_prepare_return(void);

/* The call, all of it: every entry natively or through host->translate. */
void hl_gfx_var_run(const hl_gfx_var_call *call, const hl_gfx_var_host *host);

/* The check, per entry the native version answers: the entry's translated run is recorded (the NVN calls the tap feeds,
   each call of the shared preparation as a segment with its result and what it left in the block), the memory the
   entry may write is put back, the native entry runs into a recording with the preparation replayed from its segment,
   and the two lists of calls and the bytes left are compared; the translated run's state is then put back. */
void hl_gfx_var_check_call(uint32_t proc, const uint64_t *x, const uint32_t *f);
void hl_gfx_var_prep_begin(uint64_t block);
void hl_gfx_var_prep_end(uint64_t result, int answered);

/* One line of the function's counters. Returns the length written. */
int hl_gfx_var_report(char *out, size_t cap);

#ifdef __cplusplus
}
#endif
#endif
