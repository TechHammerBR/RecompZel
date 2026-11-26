/* The Teleport page's screenshots (gpu/vk/vk_menu.cpp), between the game side (host/hos_main.c) and the menu, C and C++: a
   place is its index in oot_tp_places (gpu/vk/oot_tp_places.h). */
#pragma once
#define OOT_TP_CAPTURE_ID 4093   /* rx_option_set(OOT_TP_CAPTURE_ID, place) from the game side: Link has stayed near that place */
#define OOT_TP_MAP_ID 4094       /* rx_option_set(OOT_TP_MAP_ID, place) from the game side: the place nearest Link, -1 none */
/* rx_option(HOS_OPT_TELEPORT_PICTURES) from the game side: whether the Travel page's pictures are taken (host/hos_main.c
   oot_capture_tick watches for Link settling at a place only then). Here and not in vk_api.h: that header is part of the
   shader cache's stamp, and a change to it makes every player prepare the shaders again */
#define HOS_OPT_TELEPORT_PICTURES 74   /* (43 is Discord status's, 72 and 73 the item wheel's) */
