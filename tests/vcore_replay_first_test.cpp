// The virtual cores' ordering functions are included unchanged from host/hos_thread.c (tests/test_vcore_replay_first.py
// cuts them out). Only the thread, the lock, the wake-up and vc_acquire are synthetic: nothing here blocks.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)

struct HosThread {
    int priority = 16, ideal_core = -2;
    uint64_t core_mask = 0x3f;
    int vc_held = 0, vc_last = 0, vc_queued = 0, vc_escaped = 0, vc_starved = 0;
    int vc_boost = 0;
    int vc_kick = 0;
    int vc_prio_over = 0;
    int64_t vc_since = 0, vc_took = 0, vc_cap_until = 0, vc_free_until = 0;
    // (a long wait's cause, HOS_VCORE_LOG_MS: host/hos_thread.c)
    int64_t vc_held_at = 0, vc_kick_at = 0, vc_by_held = 0, vc_by_asked = 0;
    char vc_by[48] = {};
    int vc_by_prio = 0;
    char name[32] = "t";
    int vc_cv = 0;
    int acquires = 0, boost_at_acquire = -1;
    struct Ctx *run_ctx = nullptr;
    struct { int poll = 0; } ctx;
};
struct Ctx { int poll; };
static int vc_lock;
static HosThread *vc_owner[8];
static HosThread *vc_queue[1024];
static int vc_nq;
static struct { long long yields, kicks, boosts; } vc_st;
// (main's background-thread cap off, as by default: HOS_BG_CAP unset)
static int vc_bg_cap(void) { return 0; }
static int vc_held_n(void) { int n = 0; for (int k = 0; k < 6; k++) n += vc_owner[k] != nullptr; return n; }
static int64_t hos_now_ns(void) { return 0; }
static int vc_capped(const HosThread *) { return 0; }
static int vc_cores(void) { return 6; }
static int hos_thread_core(HosThread *t) { return t->ideal_core >= 0 ? t->ideal_core : 0; }
#define AcquireSRWLockExclusive(lock) (void)(lock)
#define ReleaseSRWLockExclusive(lock) (void)(lock)
#define WakeConditionVariable(cv) (++*(cv))   // (vc_cv counts the wake-ups)
#define HOS_CHAIN(kind, key) (void)(key)
// (the production vc_acquire waits for a core: here it only notes that the thread asked, and with what place)
static void vc_acquire(HosThread *t) {
    t->acquires++;
    t->boost_at_acquire = t->vc_boost;
}

#define vc_prio vcp   // (host/hos_thread.c: a thread's place, its vc_boost taken off)
#include "actual_vcore.inc"

static void reset() {
    for (auto &o : vc_owner) o = nullptr;
    vc_nq = 0;
}
static void enqueue(HosThread *t, int64_t since) {
    t->vc_since = since;
    t->vc_queued = 1;
    vc_queue[vc_nq++] = t;
}
// OoT: a job executor, priority 16, core 0 only; the Presentation Thread, priority 17, any core.
static HosThread executor() { HosThread t; t.priority = 16, t.core_mask = 1; return t; }
static HosThread presenter(int boost) { HosThread t; t.priority = 17, t.core_mask = 0x3f, t.vc_boost = boost; return t; }

int main() {
    {   // a free core goes to the better waiter, as before, when the replaying thread has no place ahead
        reset();
        HosThread e = executor(), p = presenter(0);
        enqueue(&e, 1), enqueue(&p, 2);
        vc_grant(0, nullptr);
        CHECK(vc_owner[0] == &e && e.vc_held == 1 && e.vc_cv == 1 && !e.vc_queued);
        CHECK(!p.vc_held && p.vc_queued && vc_nq == 1);
    }
    {   // with its place (two steps) it goes ahead of a thread one step better, whichever waited longer
        reset();
        HosThread e = executor(), p = presenter(2);
        enqueue(&e, 1), enqueue(&p, 2);
        vc_grant(0, nullptr);
        CHECK(vc_owner[0] == &p && p.vc_held == 1 && p.vc_cv == 1);
        CHECK(!e.vc_held && e.vc_queued);
        CHECK(vc_prio(&p) == 15 && vc_prio(&e) == 16 && vc_better(&p, &e) && !vc_better(&e, &p));
    }
    {   // but not ahead of a thread better than the place reaches (audio, priority 3)
        reset();
        HosThread audio, p = presenter(2);
        audio.priority = 3;
        enqueue(&p, 1), enqueue(&audio, 2);
        vc_grant(0, nullptr);
        CHECK(vc_owner[0] == &audio && !p.vc_held);
    }
    {   // nor onto a core its mask leaves out
        reset();
        HosThread e = executor(), p = presenter(2);
        p.core_mask = 2;   // (core 1 only)
        enqueue(&e, 1), enqueue(&p, 2);
        vc_grant(0, nullptr);
        CHECK(vc_owner[0] == &e && !p.vc_held);
    }
    {   // holding the core with its place, it is not made to hand it to the executor at a checkpoint (strict) or a yield
        reset();
        HosThread e = executor(), p = presenter(2);
        vc_take(&p, 0);
        enqueue(&e, 1);
        p.vc_kick = 1;
        vc_yield(&p, 1);
        CHECK(vc_owner[0] == &p && p.vc_held == 1 && p.acquires == 0 && p.vc_kick == 0);
        vc_yield(&p, 0);
        CHECK(vc_owner[0] == &p && p.acquires == 0 && vc_st.yields == 0);
    }
    {   // without the place the same checkpoint hands the core over, as before
        reset();
        vc_st.yields = 0;
        HosThread e = executor(), p = presenter(0);
        vc_take(&p, 0);
        enqueue(&e, 1);
        vc_yield(&p, 1);
        CHECK(vc_owner[0] == &e && !p.vc_held && p.acquires == 1 && vc_st.yields == 1);
    }
    {   // a yield to a thread better than the place reaches keeps the place for when the core comes back
        reset();
        vc_st.yields = 0;
        HosThread audio, p = presenter(2);
        audio.priority = 3;
        vc_take(&p, 0);
        enqueue(&audio, 1);
        vc_yield(&p, 1);
        CHECK(vc_owner[0] == &audio && !p.vc_held && p.acquires == 1 && p.boost_at_acquire == 2 && p.vc_boost == 2);
    }
    {   // giving the core up for a block ends the place, and the executor that waited has its core
        reset();
        HosThread e = executor(), p = presenter(2);
        vc_take(&p, 0);
        enqueue(&e, 1);
        vc_release(&p);
        CHECK(p.vc_boost == 0 && !p.vc_held && vc_owner[0] == &e && e.vc_held == 1);
        CHECK(vc_prio(&p) == 17);
    }
    std::puts("vcore replay first: ok");
    return 0;
}
