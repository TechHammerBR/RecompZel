"""What the save editor knows about the game's save, beyond the entry names read from the game files: the items with
the names the game shows, what group they are in and which age has them normally; where hearts, magic, rupees, bag
sizes, bottles and small keys are kept and how; and names for entries the game files do not name.

The field numbers (murmur3 hashes of names the game files do not hold) were matched against a save of this game.
Adapted from an MIT-licensed save editor (see LICENSE in this folder).
"""
import nxsave

h = lambda name: nxsave.murmur3(name.encode())

# -- items: (id, the name the game shows, group, age that has it in the unmodded game, can be given here)
#    "can be given": a plain have-it item. The rest (bag sizes, wallets, ammo, heart pieces...) are set in the Stats tab.
ITEMS = (
    ('Weapon_Sword_Kokiri', 'Kokiri Sword', 'Swords', 'Young', True),
    ('Weapon_Sword_Master', 'Master Sword', 'Swords', 'Adult', True),
    ('Weapon_Sword_Giant', "Giant's Knife", 'Swords', 'Adult', True),
    ('Weapon_Sword_BrokenGiant', "Broken Giant's Knife", 'Swords', 'Adult', True),
    ('Weapon_Sword_Biggoron', 'Biggoron Sword', 'Swords', 'Adult', True),
    ('Weapon_Shield_Deku', 'Deku Shield', 'Shields', 'Young', True),
    ('Weapon_Shield_Hylian', 'Hylian Shield', 'Shields', 'Both', True),
    ('Weapon_Shield_Mirror', 'Mirror Shield', 'Shields', 'Adult', True),
    ('Obj_Armor_Child_Normal', 'Kokiri Tunic', 'Clothes', 'Young', True),
    ('Armor_Adult_Normal', "Hero's Clothes", 'Clothes', 'Adult', True),
    ('Armor_Adult_Goron', 'Goron Tunic', 'Clothes', 'Adult', True),
    ('Armor_Adult_Zora', 'Zora Tunic', 'Clothes', 'Adult', True),
    ('Armor_Adult_HeavyBoot', 'Iron Boots', 'Clothes', 'Adult', True),
    ('Armor_Adult_HoverBoot', 'Hover Boots', 'Clothes', 'Adult', True),
    ('Armor_Child_Mask_Keaton', 'Keaton Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Skull', 'Skull Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Spooky', 'Spooky Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Bunny', 'Bunny Hood', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Goron', 'Goron Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Zora', 'Zora Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Gerudo', 'Gerudo Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Truth', 'Mask of Truth', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Amiibo0', 'Fairy-Kid Mask', 'Masks', 'Young', True),
    ('Armor_Child_Mask_Amiibo1', 'Princess Mask', 'Masks', 'Young', True),
    ('Weapon_Range_SlingShot', 'Fairy Slingshot', 'Gear', 'Young', True),
    ('Item_Boomerang', 'Boomerang', 'Gear', 'Young', True),
    ('Weapon_Range_Bow', 'Fairy Bow', 'Gear', 'Adult', True),
    ('Item_Arrow_Fire', 'Fire Arrow', 'Gear', 'Adult', True),
    ('Item_Arrow_Ice', 'Ice Arrow', 'Gear', 'Adult', True),
    ('Item_Arrow_Light', 'Light Arrow', 'Gear', 'Adult', True),
    ('Item_Hookshot', 'Hookshot', 'Gear', 'Adult', True),
    ('Item_Longshot', 'Longshot', 'Gear', 'Adult', True),
    ('Item_Hammer', 'Megaton Hammer', 'Gear', 'Adult', True),
    ('Armor_GlassTruth', 'Lens of Truth', 'Gear', 'Both', True),
    ('Item_DinFire', "Din's Fire", 'Magic', 'Both', True),
    ('Item_FaroreWind', "Farore's Wind", 'Magic', 'Both', True),
    ('Item_NayruLove', "Nayru's Love", 'Magic', 'Both', True),
    ('Item_Ocarina_Fairy', 'Fairy Ocarina', 'Quest', 'Both', True),
    ('Item_Ocarina_Time', 'Ocarina of Time', 'Quest', 'Both', True),
    ('Item_Stone_Forest', 'Kokiri Emerald', 'Quest', 'Young', True),
    ('Item_Stone_Fire', 'Goron Ruby', 'Quest', 'Young', True),
    ('Item_Stone_Water', 'Zora Sapphire', 'Quest', 'Young', True),
    ('Item_Medal_Light', 'Light Medallion', 'Quest', 'Adult', True),
    ('Item_Medal_Forest', 'Forest Medallion', 'Quest', 'Adult', True),
    ('Item_Medal_Fire', 'Fire Medallion', 'Quest', 'Adult', True),
    ('Item_Medal_Water', 'Water Medallion', 'Quest', 'Adult', True),
    ('Item_Medal_Shadow', 'Shadow Medallion', 'Quest', 'Adult', True),
    ('Item_Medal_Spirit', 'Spirit Medallion', 'Quest', 'Adult', True),
    ('Item_AgonyStone', 'Echo Gem', 'Quest', 'Both', True),
    ('Item_Token_Gerudo', 'Gerudo Pass', 'Quest', 'Adult', True),
    ('Item_WeirdEgg', 'Weird Egg', 'Trade', 'Young', True),
    ('Item_AlarmCucco', 'Wake-Up Cucco', 'Trade', 'Young', True),
    ('Item_ZeldaLetter', "Zelda's Letter", 'Trade', 'Young', True),
    ('Item_PocketEgg', 'Pocket Egg', 'Trade', 'Adult', True),
    ('Item_PocketCucco', 'Pocket Cucco', 'Trade', 'Adult', True),
    ('Item_CojiroCucco', 'Cojiro', 'Trade', 'Adult', True),
    ('Item_OddMushroom', 'Odd Mushroom', 'Trade', 'Adult', True),
    ('Item_OddPowder', 'Odd Poultice', 'Trade', 'Adult', True),
    ('Item_PoacherSaw', "Poacher's Saw", 'Trade', 'Adult', True),
    ('Item_BrokenSword', 'Broken Goron Sword', 'Trade', 'Adult', True),
    ('Item_Prescription', 'Prescription', 'Trade', 'Adult', True),
    ('Item_EyeballFrog', 'Eyeball Frog', 'Trade', 'Adult', True),
    ('Item_EyeDrop', 'Specialty Eye Drops', 'Trade', 'Adult', True),
    ('Item_ClaimCheck', 'Biggoron Receipt', 'Trade', 'Adult', True),
    ('Armor_Child_Gauntlet_Goron', 'Goron Bracelet', 'Upgrades', 'Young', True),
    ('Armor_Adult_Gauntlet_Silver', 'Silver Gauntlets', 'Upgrades', 'Adult', True),
    ('Armor_Adult_Gauntlet_Gold', 'Golden Gauntlets', 'Upgrades', 'Adult', True),
    ('Item_Scale_Silver', 'Silver Scale', 'Upgrades', 'Both', True),
    ('Item_Scale_Gold', 'Golden Scale', 'Upgrades', 'Both', True),
    ('Item_Wallet_Small', 'Kokiri Wallet', 'Upgrades', 'Both', False),
    ('Item_Wallet_Medium', "Adult's Wallet", 'Upgrades', 'Both', False),
    ('Item_Wallet_Large', "Giant's Wallet", 'Upgrades', 'Both', False),
    ('Item_BulletBag_Small', 'Deku Seed Bag', 'Upgrades', 'Young', False),
    ('Item_BulletBag_Medium', 'Bigger Deku Seed Bag', 'Upgrades', 'Young', False),
    ('Item_BulletBag_Large', 'Biggest Deku Seed Bag', 'Upgrades', 'Young', False),
    ('Item_NutBag_Small', 'Deku Nut Bag', 'Upgrades', 'Both', False),
    ('Item_NutBag_Medium', 'Bigger Deku Nut Bag', 'Upgrades', 'Both', False),
    ('Item_NutBag_Large', 'Biggest Deku Nut Bag', 'Upgrades', 'Both', False),
    ('Item_StickBag_Small', 'Deku Stick Bag', 'Upgrades', 'Young', False),
    ('Item_StickBag_Medium', 'Bigger Deku Stick Bag', 'Upgrades', 'Young', False),
    ('Item_StickBag_Large', 'Biggest Deku Stick Bag', 'Upgrades', 'Young', False),
    ('Item_BombBag_Small', 'Bomb Bag', 'Upgrades', 'Both', False),
    ('Item_BombBag_Medium', 'Bigger Bomb Bag', 'Upgrades', 'Both', False),
    ('Item_BombBag_Large', 'Biggest Bomb Bag', 'Upgrades', 'Both', False),
    ('Item_Quiver_Small', 'Quiver', 'Upgrades', 'Adult', False),
    ('Item_Quiver_Medium', 'Bigger Quiver', 'Upgrades', 'Adult', False),
    ('Item_Quiver_Large', 'Biggest Quiver', 'Upgrades', 'Adult', False),
    ('Item_FairyBless_MP', 'Gift of Improved Spin', 'Upgrades', 'Both', False),
    ('Item_FairyBless_MPDouble', 'Gift of Doubled Magic', 'Upgrades', 'Both', False),
    ('Item_FairyBless_DefenseDouble', 'Gift of Halved Damage', 'Upgrades', 'Both', False),
    ('Item_DekuStick', 'Deku Stick', 'Ammo', 'Young', False),
    ('Item_DekuNut', 'Deku Nut', 'Ammo', 'Both', False),
    ('Item_DekuSeed', 'Deku Seed', 'Ammo', 'Young', False),
    ('Item_Bomb', 'Bomb', 'Ammo', 'Both', False),
    ('Item_Bombchu', 'Bombchu', 'Ammo', 'Both', False),
    ('Item_Arrow_Normal', 'Arrow', 'Ammo', 'Adult', False),
    ('Item_MagicBean', 'Magic Beans', 'Ammo', 'Young', False),
    ('Item_ScrubBusinessSeed', 'Business Scrub Seed', 'Ammo', 'Young', False),
    ('Item_Token_Gold', 'Gold Skulltula Token', 'Ammo', 'Both', False),
    ('Obj_Heart_Piece', 'Piece of Heart', 'Ammo', 'Both', False),
    ('Pouch_Range_BowAndArrow_Fire', 'Bow + Fire Arrow', 'Gear', 'Adult', False),
    ('Pouch_Range_BowAndArrow_Ice', 'Bow + Ice Arrow', 'Gear', 'Adult', False),
    ('Pouch_Range_BowAndArrow_Light', 'Bow + Light Arrow', 'Gear', 'Adult', False),
    ('Pouch_Amiibo', 'amiibo', 'Gear', 'Both', False),
)
GROUPS = ('Swords', 'Shields', 'Clothes', 'Masks', 'Gear', 'Magic', 'Quest', 'Trade', 'Upgrades', 'Ammo')
DEFAULT_CLOTHES = ('Obj_Armor_Child_Normal', 'Armor_Adult_Normal')   # (never taken away here)


def stock(item):
    return f'PouchData.{item}.StockNum'


def got_flags(item):
    """The flags a save keeps for an item once it was found: had it, and its get scene was seen."""
    return (f'IsGet.{item}', f'HavePlayedGetEvent.{item}')


EQUIPPED = ('PlayerStatus.EquipWeapon', 'PlayerStatus.EquipShield',
            'PlayerStatus.AnotherEraEquipWeapon', 'PlayerStatus.AnotherEraEquipShield')

# -- hearts and magic: kept in progress.sav and again in caption.sav (the file-select screen), in quarters / tenths
VITALS = (  # (what, progress.sav entry, caption.sav entry, units per heart or per magic point)
    ('hearts', 'PlayerStatus.Life', 'CaptionData.Life', 4),
    ('max_hearts', 'PlayerStatus.MaxLife', 'CaptionData.MaxLife', 4),
    ('magic', 'PlayerStatus.MP', 'CaptionData.MP', 10),
    ('max_magic', 'PlayerStatus.MPMax', 'CaptionData.MPMax', 10),
)
MAGIC_METERS = ((0, 'No magic meter', ()),
                (24, 'Magic meter (24)', ('Item_FairyBless_MP',)),
                (48, 'Double magic meter (48)', ('Item_FairyBless_MP', 'Item_FairyBless_MPDouble')))

PICTURE = 0x63696A32     # caption.sav: the picture taken when the slot was saved (a JPEG)

# -- Link's age (found by saving one slot as adult, then as child, and comparing; unnamed in the game files)
IS_CHILD = 0x46080375            # on: young Link (the game writes it; the map below is what decides his age)
# the map Link is saved on. Outdoors each area has a young and an adult map ("KakarikoVillage_Child" / "_Adult"):
# the game loads that map, and its version is what makes Link young or adult. Dungeons have one map for both ages.
CURRENT_MAP = 'Sequence_CurrentBanc'               # progress.sav: "KakarikoVillage_Adult"
CAPTION_MAP = 0x0CCCC6CD                           # caption.sav: "KakarikoVillage/KakarikoVillage_Adult"
BOTH_AGES = ('DeathMountainCrater', 'DeathMountainTrail', 'DesertColossus', 'GerudoValley', 'GoronCity', 'Graveyard',
             'HountedWasteland', 'HyruleField', 'KakarikoVillage', 'KokiriForest', 'LostWood', 'Market',
             'SacredForestMeadow', 'ZoraDomain', 'ZoraFountain', 'ZoraRiver')   # (the game files' Banc folder)


def other_age_map(name, to_child):
    """The other age's version of a map name ("KakarikoVillage_Adult" -> "KakarikoVillage_Child"), or None when the
    map has no version for that age (a dungeon, a house, Gerudo Fortress)."""
    import re
    m = re.match(r'^(.*?)([A-Za-z0-9]+)_(Child|Adult)(\b.*)$', name or '')
    if not m or m.group(2) not in BOTH_AGES:
        return None
    return f'{m.group(1)}{m.group(2)}_{"Child" if to_child else "Adult"}{m.group(4)}'

# -- rupees
RUPEES, CAPTION_RUPEES = 'PlayerStatus.CurrentRupee', 'CaptionData.CurrentRupee'
WALLET_NAME = 0x3E42AFFA      # the wallet's item name (text)
RUPEE_LIMIT = 0xE0010A50
WALLETS = (('Item_Wallet_Small', 'Kokiri Wallet', 200), ('Item_Wallet_Medium', "Adult's Wallet", 500),
           ('Item_Wallet_Large', "Giant's Wallet", 1000))

# -- bags and the quiver: how much each holds, which sizes were found, and (for three) the name of the bag held
BAGS = (  # (key, label, size entry, name entry or None, item prefix, sizes)
    ('seeds', 'Deku Seed Bag', 0xAE8CC742, 0xD732DD7F, 'Item_BulletBag', (30, 40, 50)),
    ('nuts', 'Deku Nut Bag', 0x735B00F7, 0x0DA3A7A7, 'Item_NutBag', (20, 30, 40)),
    ('sticks', 'Deku Stick Bag', 0x457616B0, 0x2808EE1C, 'Item_StickBag', (10, 20, 30)),
    ('bombs', 'Bomb Bag', 0xE753508B, None, 'Item_BombBag', (20, 30, 40)),
    ('arrows', 'Quiver', 0x418DB791, None, 'Item_Quiver', (30, 40, 50)),
)
SIZES = ('Small', 'Medium', 'Large')

AMOUNTS = (  # (label, item, the bag that limits it, else the most there can be)
    ('Deku Sticks', 'Item_DekuStick', 'sticks', None),
    ('Deku Nuts', 'Item_DekuNut', 'nuts', None),
    ('Deku Seeds', 'Item_DekuSeed', 'seeds', None),
    ('Bombs', 'Item_Bomb', 'bombs', None),
    ('Bombchus', 'Item_Bombchu', 'bombs', None),
    ('Arrows', 'Item_Arrow_Normal', 'arrows', None),
    ('Magic Beans', 'Item_MagicBean', None, 10),
    ('Business Scrub Seeds', 'Item_ScrubBusinessSeed', None, 30),
    ('Gold Skulltula Tokens', 'Item_Token_Gold', None, 100),
    ('Pieces of Heart', 'Obj_Heart_Piece', None, 3),
)

SMALL_KEYS = (  # (label, entry, the most the place has)
    ('Bottom of the Well', 'DungeonInfo.BottomOfTheWell.SmallKeyNum', 2),
    ('Forest Temple', 'DungeonInfo.ForestTemple.SmallKeyNum', 5),
    ('Fire Temple', 'DungeonInfo.FireTemple.SmallKeyNum', 7),
    ('Water Temple', 'DungeonInfo.WaterTemple.SmallKeyNum', 4),
    ('Shadow Temple', 'DungeonInfo.ShadowTemple.SmallKeyNum', 5),
    ('Spirit Temple', 'DungeonInfo.SpiritTemple.SmallKeyNum', 5),
    ('Gerudo Fortress', 'DungeonInfo.GerudoFortress.SmallKeyNum', 4),
    ('Gerudo Training Ground', 'DungeonInfo.GerudoTrainingGround.SmallKeyNum', 8),
    ("Ganon's Castle", 'DungeonInfo.InsideGanonCastle.SmallKeyNum', 1),
)

# -- bottles: (had, in use, contents) for each of the five
BOTTLES = (('PouchData.BottleA.StockNum', 0xF39CE410, 0x7D48DF76),
           ('PouchData.BottleB.StockNum', 0x000FF6EA, 0x1EDD164A),
           ('PouchData.BottleC.StockNum', 0xF63B1194, 0xB80C70A8),
           ('PouchData.BottleD.StockNum', 0xB7F052CE, 0xE4C1B1FC),
           ('PouchData.BottleE.StockNum', 0xE27B136D, 0x365E1953))
BOTTLE_CONTENTS = ((0xBE69DE49, 'Empty'), (0xEABA6067, 'Red Potion'), (0x049D37C1, 'Green Potion'),
                   (0xF383D6E5, 'Blue Potion'), (0x73356827, 'Milk'), (0xEEF6E4B0, 'Half Milk'),
                   (0x6F49E357, 'Fairy'), (0x1E834EF8, 'Fish'), (0x74D62ECB, 'Bug'), (0x1C293517, 'Blue Fire'),
                   (0x02084F9E, 'Poe'), (0xCDC21471, 'Big Poe'), (0x0F24E808, "Ruto's Letter"))

# -- names for entries the game files do not name (shown in the All entries tab)
EXTRA_NAMES = {
    WALLET_NAME: 'PlayerStatus.Wallet (item name)',
    RUPEE_LIMIT: 'PlayerStatus.RupeeLimit',
    PICTURE: 'CaptionData.Picture (JPEG)',
    IS_CHILD: 'PlayerStatus.IsChild (young Link)',
    CAPTION_MAP: 'CaptionData.Banc (the map, for the file-select screen)',
    174442925: 'PouchData.SUAx',
    2269937364: 'Progress ID',
}
for _k, _label, _size, _name, _prefix, _ in BAGS:
    EXTRA_NAMES[_size] = f'{_label} - holds'
    if _name:
        EXTRA_NAMES[_name] = f'{_label} - bag held (item name)'
for _i, (_, _use, _what) in enumerate(BOTTLES):
    EXTRA_NAMES[_use] = f'Bottle {"ABCDE"[_i]} - in use'
    EXTRA_NAMES[_what] = f'Bottle {"ABCDE"[_i]} - contents'


DUNGEONS = ('InsideTheDekuTree', 'DodongoCavern', 'InsideJabuJabuBelly', 'Insidejabujabu', 'InsidejaubjabuBelly',
            'DreamBossStage', 'FinalBattleField', 'ForestTemple',
            'FireTemple', 'WaterTemple', 'ShadowTemple', 'SpiritTemple', 'BottomOfTheWell', 'IceCavern',
            'GerudoTrainingGround', 'InsideGanonCastle', 'GanonCastle', 'EscapeFromCrumblingGanonCastle',
            'DungeonInfo')
PLACES = ('KokiriForest', 'LostWood', 'SacredForestMeadow', 'HyruleField', 'Market', 'HyruleCastle',
          'TempleOfTime', 'KakarikoVillage', 'GraveYard', 'DeathMountain', 'MountainTrail', 'GoronCity',
          'ZoraRiver', 'ZoraDomain', 'ZoraFountain', 'LakeHylia', 'LonLonRanch', 'GerudoValley', 'GerudoFortress',
          'HountedWasteland', 'HauntedWasteland', 'DesertColossus', 'DreamWorld', 'IsVisitLocation', 'Found_',
          'Zorariver', 'HrlField', 'UnderTheGrave')


def flag_group(name):
    """The Progress tab's group for a flag, from how its name starts."""
    first = name.replace('.', '_').split('_')[0]
    if name.startswith(('IsGet.', 'HavePlayedGetEvent.', 'Get_', 'Get.')):
        return 'Items found'
    if name.startswith(('HavePlayedEvent.', 'SubEvent')):
        return 'Events and cutscenes'
    if name.startswith(('HaveTalk', 'HavePlayedNavi', 'NaviHint', 'NaviChat', 'GossipStone', 'BlewOcarinaByGossip',
                        'HaveRead')):
        return 'Talks, Navi and Gossip Stones'
    if first in DUNGEONS or name.startswith(DUNGEONS):
        return 'Dungeons'
    if first in PLACES or name.startswith(PLACES):
        return 'Places'
    if name.startswith(('MiniGame', 'Minigame', 'GetSwordBigGoron', 'Fishing')):
        return 'Mini-games and side quests'
    if name.startswith(('ActionGuide', 'UI', 'Tutorial')):
        return 'Tutorials and menus'
    if name.startswith(('Npc', 'NPC', 'Sage')):
        return 'People'
    return 'Other'


FLAG_GROUPS = ('Items found', 'Events and cutscenes', 'Talks, Navi and Gossip Stones', 'Dungeons', 'Places',
               'Mini-games and side quests', 'Tutorials and menus', 'People', 'Other')
