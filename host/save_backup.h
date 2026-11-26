/* (hookshot) Save backups outside the game folder: host/save_backup.c */
#pragma once
#include <stddef.h>

/* The backups' folder: HOS_SAVE_BACKUPS, else %LOCALAPPDATA%\Hookshot\save-backups (Windows) or
   $XDG_DATA_HOME/hookshot/save-backups (~/.local/share/hookshot/save-backups). 0: no such place */
int hos_save_backups_dir(char *out, size_t cap);
/* A copy of <user_dir>/save as a new backup, when something there is newer than the last backup; the oldest past 20 go.
   1: one was made */
int hos_save_backup(const char *user_dir, const char *why);
/* hos_save_backup at most once every 20 s, for the game's commits of its save data (nn::fs::Commit) */
void hos_save_backup_on_commit(const char *user_dir);
/* <user_dir>/save holds no file at all and a backup exists: the newest one copied in. 1: restored */
int hos_save_restore_if_empty(const char *user_dir);
