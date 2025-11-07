# cortanaStats by faithvoid - https://github.com/faithvoid/repository.faithvoid/
# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xml.etree.ElementTree as ET
import urllib2
import re
import time
from datetime import datetime, timedelta

# Add-on settings
addon = xbmcaddon.Addon()
insignia_url = addon.getSetting("insignia_url")
xlinkkai_url = addon.getSetting("xlinkkai_url")

try:
    CHECK_INTERVAL = int(addon.getSetting("check_interval"))
except ValueError:
    CHECK_INTERVAL = 60

# Open the Insignia or XLink Kai RSS URLs.
def fetch_feed_root(feed_url):
    try:
        response = urllib2.urlopen(feed_url, timeout=10)
        xml_data = response.read()
        return ET.fromstring(xml_data)
    except Exception as e:
        xbmc.log("Error fetching or parsing RSS feed '%s': %s" % (feed_url, str(e)), xbmc.LOGERROR)
        return None

# Get Insignia & XLink Kai player counts.
def get_users_online(root):
    try:
        for item in root.findall(".//item"):
            title = item.find("title").text
            if title.startswith("Users Online:"):
                return int(title.split(":")[1].strip())
    except Exception as e:
        xbmc.log("Error extracting player count: %s" % str(e), xbmc.LOGERROR)
    return 0

# Get Insignia & XLink Kai sessions.
def get_sessions(root):
    try:
        for item in root.findall(".//item"):
            title = item.find("title").text
            if title.startswith("Active Games:"):
                return int(title.split(":")[1].strip())
    except Exception as e:
        xbmc.log("Error extracting sessions: %s" % str(e), xbmc.LOGERROR)
    return 0

# Fetch currently active games (skipping games with 0 players in 0 sessions) for Insignia and XLink Kai, then sort by the amount of players.
def set_top_active_games(insignia_root, xlink_root):
    def parse_insignia_games(root):
        games = []
        for item in root.findall(".//item"):
            category = item.find("category").text
            if category != "Games":
                continue
            title = item.find("title").text
            # Convert &amp; to &. Kind of hacky, but the ampersand is the only character really causing issues here.
            title = re.sub(r'&amp;', '&', title)
            if "(0 in 0 sessions)" in title:
                continue
            match = re.match(r"(.+): (\d+) players", title)
            if match:
                game_name, players = match.groups()
                games.append((int(players), title))
            else:
                match = re.match(r"(.+): 1 player", title)
                if match:
                    games.append((1, title))
        games.sort(reverse=True, key=lambda x: x[0])
        return [g[1] for g in games[:5]]

    def parse_xlink_games(root):
        games = []
        for item in root.findall(".//item"):
            category = item.find("category").text
            if category != "Games":
                continue
            title = item.find("title").text
            if "(0 in 0 sessions)" in title:
                continue
            match = re.match(r"(.+): (\d+) players", title)
            if match:
                game_name, players = match.groups()
                games.append((int(players), title))
        games.sort(reverse=True, key=lambda x: x[0])
        return [g[1] for g in games[:5]]

    insignia_games = parse_insignia_games(insignia_root)
    xlink_games = parse_xlink_games(xlink_root)

    for i in range(5):
        skin_value = insignia_games[i] if i < len(insignia_games) else ""
        xbmc.executebuiltin('Skin.SetString(insigniaSession{0}, "{1}")'.format(i + 1, skin_value))

    for i in range(5):
        skin_value = xlink_games[i] if i < len(xlink_games) else ""
        xbmc.executebuiltin('Skin.SetString(xlinkSession{0}, "{1}")'.format(i + 1, skin_value))

# Fetch Insignia statistics from the OGXbox RSS feed.
def get_insignia_statistics(root):
    stats = {"users_online": None, "active_games": None, "registered_users": None, "games_supported": None}
    try:
        for item in root.findall(".//item"):
            title = item.find("title").text
            if title.startswith("Users Online:"):
                stats["users_online"] = title
            elif title.startswith("Registered Users:"):
                stats["registered_users"] = title
            elif title.startswith("Games Supported:"):
                stats["games_supported"] = title
            elif title.startswith("Active Games:"):
                stats["active_games"] = title
    except Exception as e:
        xbmc.log("Error parsing Insignia stats: %s" % str(e), xbmc.LOGERROR)
    return stats

# Fetch XLink Kai statistics from the OGXbox RSS feed.
def get_xlinkkai_statistics(root):
    stats = {
        "users_online": None,
        "users_today": None,
        "server_status": None,
        "supported_games": None,
        "total_users": None,
        "orbital_servers": None,
        "orbital_sync": None,
        "game_traffic": None,
        "orbital_traffic": None
    }
    try:
        for item in root.findall(".//item"):
            title = item.find("title").text
            if title.startswith("Users Online:"):
                stats["users_online"] = title
            elif title.startswith("Users Today:"):
                stats["users_today"] = title
            elif title.startswith("Server Status:"):
                stats["server_status"] = title
            elif title.startswith("Supported Games:"):
                stats["supported_games"] = title
            elif title.startswith("Total Users:"):
                stats["total_users"] = title
            elif title.startswith("Orbital Servers Online:"):
                stats["orbital_servers"] = title
            elif title.startswith("Orbital Mesh Sync:"):
                stats["orbital_sync"] = title
            elif title.startswith("Game Traffic:"):
                stats["game_traffic"] = title
            elif title.startswith("Orbital Server Traffic:"):
                stats["orbital_traffic"] = title
    except Exception as e:
        xbmc.log("Error parsing XLink Kai stats: %s" % str(e), xbmc.LOGERROR)
    return stats

# Fetch event-specific information from the OGXbox RSS feed.
def get_events(root):
    try:
        now = datetime.now()
        events = []

        def parse_day_label(day_label):
            cleaned_label = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', day_label)
            try:
                return datetime.strptime(cleaned_label, "%a, %b %d").date().replace(year=now.year)
            except Exception as e:
                xbmc.log("Failed to parse day label '{}': {}".format(day_label, e), xbmc.LOGERROR)
                return None

        for item in root.findall(".//item"):
            title_elem = item.find("title")
            desc_elem = item.find("description")
            if title_elem is None or desc_elem is None:
                continue

            # Convert &amp; to &. Kind of hacky, but the ampersand is the only character really causing issues here.
            title = re.sub(r'&amp;', '&', title_elem.text.strip())
            description = re.sub(r'&amp;', '&', desc_elem.text.strip())

            if not title.startswith("Game Event - "):
                continue

            title_match = re.match(r"Game Event - ([^:]+):\s*(.+)", title)
            if not title_match:
                continue
            day_label, game_name = title_match.groups()
            day_label = day_label.strip()
            game_name = game_name.strip()

            time_match = re.search(r"at (\d{1,2}:\d{2} (?:AM|PM) EST)", description)
            time_str = time_match.group(1) if time_match else "Time N/A"

            try:
                event_time = datetime.strptime(time_str, "%I:%M %p EST").time() if time_str != "Time N/A" else None

                if day_label.lower() == "today":
                    event_date = now.date()
                elif day_label.lower() == "tomorrow":
                    event_date = (now + timedelta(days=1)).date()
                else:
                    event_date = parse_day_label(day_label)
                    if event_date is None:
                        continue

                event_dt = datetime.combine(event_date, event_time) if event_time else None
            except Exception as e:
                xbmc.log("Failed to parse event time '{}': {}".format(time_str, e), xbmc.LOGERROR)
                continue

            label = "{}: {} ({})".format(day_label, game_name, time_str)
            events.append((event_dt if event_dt else datetime.max, label))

        events.sort(key=lambda x: x[0])
        top_events = events[:3]

        return "[CR]".join([e[1] for e in top_events])

    except Exception as e:
        xbmc.log("Error extracting upcoming events: {}".format(str(e)), xbmc.LOGERROR)
    return ""

# Update skin settings after fetching the required session/statistic/player count information.
def update_skins():

    insignia_root = fetch_feed_root(insignia_url)
    xlink_root = fetch_feed_root(xlinkkai_url)

    if not insignia_root or not xlink_root:
        return

    insignia_users = get_users_online(insignia_root)
    xlinkkai_users = get_users_online(xlink_root)
    insignia_sessions = get_sessions(insignia_root)
    xlinkkai_sessions = get_sessions(xlink_root)

    combined_string_header = "- {} on Insignia, {} on XLink Kai -".format(insignia_users, xlinkkai_users)
    combined_string = "({} [Insignia] | {} [XLink Kai])".format(insignia_users, xlinkkai_users)
    insignia_string = "({} players)".format(insignia_users)
    xlink_string = "({} players)".format(xlinkkai_users)
    xlinksession_string = "({})".format(xlinkkai_sessions)
    insigniasession_string = "({})".format(insignia_sessions)

    xlink_stats = get_xlinkkai_statistics(xlink_root)
    insignia_stats = get_insignia_statistics(insignia_root)

    set_top_active_games(insignia_root, xlink_root)

    # Update the skin settings once session/statistic/player count information is retrieved.
    xbmc.executebuiltin('Skin.SetString(onlinePlayers, "{}")'.format(combined_string))
    xbmc.executebuiltin('Skin.SetString(onlinePlayersHeader, "{}")'.format(combined_string_header))

    xbmc.executebuiltin('Skin.SetString(onlineInsigniaPlayers, "{}")'.format(insignia_string))
    xbmc.executebuiltin('Skin.SetString(onlineXLinkPlayers, "{}")'.format(xlink_string))
    xbmc.executebuiltin('Skin.SetString(activeXLinkSessions, "{}")'.format(xlinksession_string))
    xbmc.executebuiltin('Skin.SetString(activeInsigniaSessions, "{}")'.format(insigniasession_string))

    xbmc.executebuiltin('Skin.SetString(insigniaUsersOnline, "{}")'.format(insignia_stats["users_online"]))
    xbmc.executebuiltin('Skin.SetString(insigniaRegisteredUsers, "{}")'.format(insignia_stats["registered_users"]))
    xbmc.executebuiltin('Skin.SetString(insigniaGamesSupported, "{}")'.format(insignia_stats["games_supported"]))
    xbmc.executebuiltin('Skin.SetString(insigniaActiveGames, "{}")'.format(insignia_stats["active_games"]))

    xbmc.executebuiltin('Skin.SetString(xlinkUsersOnline, "{}")'.format(xlink_stats["users_online"]))
    xbmc.executebuiltin('Skin.SetString(xlinkUsersToday, "{}")'.format(xlink_stats["users_today"]))
    xbmc.executebuiltin('Skin.SetString(xlinkServerStatus, "{}")'.format(xlink_stats["server_status"]))
    xbmc.executebuiltin('Skin.SetString(xlinkSupportedGames, "{}")'.format(xlink_stats["supported_games"]))
    xbmc.executebuiltin('Skin.SetString(xlinkTotalUsers, "{}")'.format(xlink_stats["total_users"]))
    xbmc.executebuiltin('Skin.SetString(xlinkOrbitalServers, "{}")'.format(xlink_stats["orbital_servers"]))
    xbmc.executebuiltin('Skin.SetString(xlinkOrbitalSync, "{}")'.format(xlink_stats["orbital_sync"]))
    xbmc.executebuiltin('Skin.SetString(xlinkGameTraffic, "{}")'.format(xlink_stats["game_traffic"]))
    xbmc.executebuiltin('Skin.SetString(xlinkOrbitalTraffic, "{}")'.format(xlink_stats["orbital_traffic"]))

def update_events():
    insignia_root = fetch_feed_root(insignia_url)
    xlink_root = fetch_feed_root(xlinkkai_url)

    if not insignia_root or not xlink_root:
        return

    insignia_events = get_events(insignia_root)
    xlink_events = get_events(xlink_root)

    # Update the skin settings once event information is retrieved.
    xbmc.executebuiltin('Skin.SetString(insigniaEvents, "{}")'.format(insignia_events))
    xbmc.executebuiltin('Skin.SetString(xlinkEvents, "{}")'.format(xlink_events))

if __name__ == '__main__':
    # Update events once at startup. To constantly fetch events, move "update_events()" under "update_skins()".
    update_events()
    # Updates player counts, sessions, and statistics once per check interval.
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        update_skins()
        # Wait for however many seconds are listed in CHECK_INTERVAL, or exit immediately if XBMC4Xbox is shutting down.
        if monitor.waitForAbort(CHECK_INTERVAL):
            break
