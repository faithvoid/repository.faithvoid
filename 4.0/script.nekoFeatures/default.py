import os
import xbmc
import xbmcgui
import xbmcaddon
import xml.etree.ElementTree as ET

ADDON = xbmcaddon.Addon()
DIALOG = xbmcgui.Dialog()

FEATURE_ID_TABLE = {
    0: "", 1: "Players", 2: "System Link", 3: "Memory Unit", 4: "HDD",
    5: "Custom Soundtracks", 6: "Dolby Digital Sound", 7: "480i",
    8: "HDTV", 13: "Widescreen", 14: "PAL 50Hz Only",
    15: "NTSC 60Hz Only", 16: "Region", 17: "Communicator Headset",
    18: "Steering Wheel", 19: "Light Gun", 20: "Arcade Stick",
    21: "Dance Pad", 22: "Keyboard", 23: "Flight Stick",
    24: "Unique Controller", 25: "Ranking",
    26: "Xbox Live Aware", 27: "Online Multiplayer", 28: "Content Download",
    29: "User Generated Content", 30: "Scoreboards", 31: "Friends",
    32: "Voice", 33: "Game Clips", 34: "Clans", 35: "XLink Kai", 36: "Insignia Aware"
}

NAME_TO_ID = {v.lower(): k for k, v in FEATURE_ID_TABLE.items() if v}

SYNONYMS = {
    'memory unit': 'memory unit',
    '480i': '480i',
    'hdtv': 'hdtv',
    '720p': 'hdTV 720p',
    '1080i': 'hdTV 1080i',
    'widescreen': 'widescreen',
    'pal': 'pal 50hz only',
    'ntsc': 'ntsc 60hz only',
    'headset': 'communicator headset',
    'xbox live': 'xbox live aware',
}

def normalize_feature_name(s):
    s_low = " ".join(s.strip().lower().split())
    for known in NAME_TO_ID.keys():
        if known in s_low:
            return FEATURE_ID_TABLE[NAME_TO_ID[known]].strip()
    for syn, canonical in SYNONYMS.items():
        if syn in s_low:
            cannon_low = canonical.lower()
            for known in NAME_TO_ID.keys():
                if known in cannon_low:
                    return FEATURE_ID_TABLE[NAME_TO_ID[known]].strip()
    return s.strip()

def parse_default_xml(path):
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        title_el = root.find('title')
        title = title_el.text.strip() if title_el is not None and title_el.text else os.path.basename(os.path.dirname(path))

        fg = root.find('features_general')
        fo = root.find('features_online')

        parts = []

        if fg is not None and fg.text:
            parts.append(fg.text.strip())

        if fo is not None and fo.text:
            parts.append(fo.text.strip())

        features_text = ", ".join(parts)

        return title, features_text

    except:
        return None, ''

def scan_for_defaults(base_path):
    feature_map = {}
    if not os.path.isdir(base_path):
        return feature_map

    for root, dirs, files in os.walk(base_path):
        for fname in files:
            if fname.lower() == 'default.xml' and os.path.basename(root).lower() == '_resources':
                default_path = os.path.join(root, fname)
                game_folder = os.path.dirname(root)
                title, features_text = parse_default_xml(default_path)
                if title is None:
                    continue

                parts = []
                if features_text:
                    for part in features_text.replace(';', ',').replace('|', ',').split(','):
                        p = part.strip()
                        if p:
                            parts.append(p)
                if not parts:
                    parts = ['(none)']

                for p in parts:
                    norm = normalize_feature_name(p)
                    if not norm:
                        norm = p
                    feature_map.setdefault(norm, []).append({
                        'title': title,
                        'folder': game_folder,
                        'default_xml': default_path,
                        'feature_full': p
                    })
    return feature_map

def find_launchable_xbe(folder):
    try:
        for fname in os.listdir(folder):
            if fname.lower().endswith('.xbe'):
                return os.path.join(folder, fname)
        return None
    except:
        return None

def launch_xbe(path):
    if not path or not os.path.exists(path):
        DIALOG.ok("Error", "No XBE file found: %s" % path)
        return False
    xbmc.executebuiltin('RunXBE(%s)' % xbmc.translatePath(path))
    return True

def main():
    folder_override = None
    if len(sys.argv) > 1:
        path = xbmc.translatePath(sys.argv[1])
        if os.path.isdir(path):
            folder_override = path

    base_folder = folder_override or ADDON.getSetting('scan_folder')
    if not base_folder or not os.path.isdir(base_folder):
        DIALOG.ok("Default folder not set", "Please set a default scan folder in the add-on settings.")
        return

    feature_map = scan_for_defaults(base_folder)
    if not feature_map:
        DIALOG.ok("No games found", "No _resources/default.xml files with features were found under %s" % base_folder)
        return

    while True:
        base_features = sorted(feature_map.keys(), key=str.lower)
        sel = DIALOG.select("Features", base_features)
        if sel < 0:
            break
        chosen_base = base_features[sel]

        sub_features = sorted(set(g['feature_full'] for g in feature_map[chosen_base]))

        if len(sub_features) <= 1:
            chosen_sub = sub_features[0] if sub_features else None
        else:
            sel2 = DIALOG.select("Sub-Features", sub_features)
            if sel2 < 0:
                continue
            chosen_sub = sub_features[sel2]

        if chosen_sub:
            games = [g for g in feature_map[chosen_base] if g['feature_full'] == chosen_sub]
        else:
            games = feature_map[chosen_base]

        game_labels = ["%s" % (g['title']) for g in games]
        selg = DIALOG.select("Games with: %s" % (chosen_sub if chosen_sub else chosen_base), game_labels)
        if selg < 0:
            continue
        game = games[selg]

        candidate = find_launchable_xbe(game['folder'])
        if candidate:
            launch_xbe(candidate)
        else:
            DIALOG.ok("No XBE found", "Could not find any .xbe file in %s" % game['folder'])

if __name__ == '__main__':
    main()
