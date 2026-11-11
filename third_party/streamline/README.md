# NVIDIA Streamline: headers only

`include/` is a copy of the public headers of NVIDIA's Streamline SDK, version 2.14.16
(https://github.com/NVIDIA-RTX/Streamline, `include/`), under the MIT license in `LICENSE.txt`.

Only headers are kept here: the game loads `sl.interposer.dll` and its plugins at run time, and never links them. The DLLs
are NVIDIA's own builds, are not part of this repository, and `nvngx_dlssg.dll` is under the NVIDIA RTX SDKs License (use
only with NVIDIA GPUs). See `docs/dlss-frame-generation.md`.
