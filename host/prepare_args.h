/* (hookshot) The arguments the Builder's supervisor gives a --prepare-shaders run (nx2/prepare_supervisor.py;
   docs/shader-preparation.md). Each takes one value and reaches the renderer as a switch, as --compile-shaders
   does (RX_VK_COMPILE_SHADERS), since the renderer is handed no command line:

     --prepare-journal <file>     HOOKSHOT_PREPARE_JOURNAL   a line before and after each driver compile call
                                                             (gpu/vk/prepare_journal.h)
     --prepare-from <n>           HOOKSHOT_PREPARE_FROM      started again past entry n: numbers go on from n + 1, and the
                                                             run before is not counted against the steps' crash markers
     --prepare-skip <file>        HOOKSHOT_PREPARE_SKIP      the programs left out ("skip <key>") and the suspects built one
                                                             at a time ("alone <key>")
     --prepare-entry-limit <s>    HOOKSHOT_PREPARE_ENTRY_S   seconds one entry gets inside the driver before the run ends
                                                             itself with exit status 6

   Paths are UTF-8, as every path of the game (the exe's manifest on Windows). */
#ifndef HOS_PREPARE_ARGS_H
#define HOS_PREPARE_ARGS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The switch an argument sets with its value, or NULL: not one of these */
static inline const char *hos_prepare_arg_switch(const char *arg) {
    if (!strcmp(arg, "--prepare-journal")) return "HOOKSHOT_PREPARE_JOURNAL";
    if (!strcmp(arg, "--prepare-from")) return "HOOKSHOT_PREPARE_FROM";
    if (!strcmp(arg, "--prepare-skip")) return "HOOKSHOT_PREPARE_SKIP";
    if (!strcmp(arg, "--prepare-entry-limit")) return "HOOKSHOT_PREPARE_ENTRY_S";
    return NULL;
}

/* Every such argument of the command line set as its switch, wherever it stands (before the renderer is loaded) */
static inline void hos_prepare_args_env(int argc, char **argv) {
    for (int i = 1; i + 1 < argc; i++) {
        const char *name = hos_prepare_arg_switch(argv[i]);
        if (!name) continue;
        const char *value = argv[++i];
#ifdef _WIN32
        const size_t size = strlen(name) + strlen(value) + 2;
        char *set = (char *)malloc(size);
        if (!set) continue;
        snprintf(set, size, "%s=%s", name, value);
        _putenv(set);   /* (copied by the C runtime) */
        free(set);
#else
        setenv(name, value, 1);
#endif
    }
}

#endif
