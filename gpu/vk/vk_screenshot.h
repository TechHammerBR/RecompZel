// (hookshot) F12: the game's picture as it is presented (its output resolution, HUD in, the Insert menu and the FPS counter
// out), written as a PNG in the game folder's screenshots folder. Asked for by players (Discord, "screenshot", 16/11):
// Windows' own key takes the whole screen, and with the mouse captured there was no way to keep what the game draws.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace mkwvk {
/// screenshots/Hookshot <date> <time>.png in `folder` (made when missing; " (2)", " (3)" when taken in the same second)
std::string screenshot_path(const std::string& folder);
/// The picture (RGBA, 4 bytes a pixel; the alpha is not kept) written as a PNG; whether it is on the disk
bool screenshot_write(const std::string& path, const uint8_t* rgba, uint32_t w, uint32_t h);
} // namespace mkwvk
