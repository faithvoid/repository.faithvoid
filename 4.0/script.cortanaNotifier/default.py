import xbmc
import xbmcgui
import xbmcaddon
import urllib
import json
import urllib2
import xml.etree.ElementTree as ET
import re
from collections import deque
import os

addon = xbmcaddon.Addon()
INSIGNIA_EVENTS = addon.getSetting('insignia_events') == 'true'
XLINKKAI_EVENTS = addon.getSetting('xlinkkai_events') == 'true'
INSIGNIA_SESSIONS = addon.getSetting('insignia_sessions') == 'true'
XLINKKAI_SESSIONS = addon.getSetting('xlinkkai_sessions') == 'true'
INSIGNIA_NOTIFY_FILE = "Z:\\temp\\insignia\\notifications.txt"
INSIGNIA_EVENT_FILE = "Z:\\temp\\insignia\\events.txt"
XLINKKAI_NOTIFY_FILE = "Z:\\temp\\xlinkkai\\notifications.txt"
XLINKKAI_EVENT_FILE = "Z:\\temp\\xlinkkai\\events.txt"
REDUMP_JSON = 'https://github.com/MobCat/MobCats-original-xbox-game-list/raw/refs/heads/main/redump-xbox-info.json'
MOBCAT_API = 'https://mobcat.zip/XboxIDs/api.php?xmid={}&imgs'

game_event_queue = deque()
regular_notification_queue = deque()
monitor = xbmc.Monitor()

try:
    req = urllib2.Request(REDUMP_JSON, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib2.urlopen(req)
    REDUMP_DATA = json.load(response)
except Exception as e:
    REDUMP_DATA = {}
    xbmc.log("Error loading JSON: {}".format(str(e)), xbmc.LOGERROR)

def clear_notifications_file(file_path):
    folder = os.path.dirname(file_path)
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    open(file_path, "w").close()

def load_notifications(file_path):
    folder = os.path.dirname(file_path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return set(f.read().strip().split("\n"))
    return set()

def save_notifications(notifications, file_path):
    folder = os.path.dirname(file_path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(file_path, "w") as f:
        for notification in notifications:
            f.write("%s\n" % notification)

def clean_title(title):
    if not title:
        return ""
    title = re.sub(r'\s+', ' ', title.strip())
    title = title.replace("&amp;", "&")
    return title

def extract_game_id(link):
    if link:
        match = re.search(r'/games/(\w+)', link)
        if match:
            return match.group(1)
    return None

def get_game_thumbnail(game_id):
    if game_id and len(game_id) >= 4:
        game_id_upper = game_id.upper()
        folder = game_id_upper[:4]
        return "https://raw.githubusercontent.com/MobCat/MobCats-original-xbox-game-list/main/icon/{0}/{1}.png".format(folder, game_id_upper)
    return ""

def get_xlinkkai_thumbnail(title_name):
    title_name_clean = clean_title(title_name)
    title_name_clean = re.sub(r'(\s*[:\-]\s*\d+\s*players?\b|\(\d+\s*players?\))', '', title_name_clean, flags=re.IGNORECASE)
    title_name_clean = title_name_clean.strip().lower()

    xmid = None

    for key, game in REDUMP_DATA.items():
        if 'Name' in game and clean_title(game['Name']).lower() == title_name_clean:
            xmid = key
            break

    if not xmid:
        xbmc.log("XMID not found for game: '{}'".format(title_name), xbmc.LOGDEBUG)
        return ""

    try:

        api_url = MOBCAT_API.format(urllib.quote(xmid))
        req = urllib2.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib2.urlopen(req)
        data = json.load(response)

        if isinstance(data, list) and len(data) > 0:
            title_id = data[0].get('Title_ID')
            if title_id:

                return get_game_thumbnail(title_id)
        xbmc.log("No Title ID found in MobCat API response for '{}'".format(title_name), xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log("Error fetching Title ID from MobCat API for '{}': {}".format(title_name, str(e)), xbmc.LOGERROR)

    return ""

def display_notification(header, message, thumbnail):
    dialog = xbmcgui.Dialog()
    if thumbnail:
        dialog.notification(header, message, thumbnail, 5000)
    else:
        dialog.notification(header, message, "", 5000)

def process_notifications():
    while game_event_queue:
        header, message, thumb = game_event_queue.popleft()
        display_notification(header, message, thumb)

    while regular_notification_queue:
        header, message, thumb = regular_notification_queue.popleft()
        display_notification(header, message, thumb)

def fetch_insignia_events():
    if not INSIGNIA_EVENTS:
        return
    current_notifications = load_notifications(INSIGNIA_EVENT_FILE)
    new_notifications = set()
    try:
        url = 'http://ogxbox.org/rss/insignia.xml'
        req = urllib2.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib2.urlopen(req)
        data = response.read()
        root = ET.fromstring(data)

        for item in root.findall('.//item'):
            title_element = item.find('title')
            link_element = item.find('link')
            if title_element is None:
                continue

            title = title_element.text
            link = link_element.text if link_element is not None else None

            if title.startswith("Game Event - Today") or title.startswith("Game Event - Tomorrow"):
                clean_title_text = re.sub(r'^Game Event - ', '', title)
                clean_title_text = clean_title(clean_title_text)
                if clean_title_text not in current_notifications:
                    game_id = extract_game_id(link)
                    thumb_url = get_game_thumbnail(game_id)
                    game_event_queue.append(("Insignia - Event", clean_title_text, thumb_url))
                    new_notifications.add(clean_title_text)

        save_notifications(new_notifications, INSIGNIA_EVENT_FILE)
    except Exception as e:
        error_msg = "RSS Error: " + str(e)
        regular_notification_queue.append(("RSS Feed Error", error_msg, ""))
        new_notifications.add(error_msg)

def fetch_insignia_sessions():
    if not INSIGNIA_SESSIONS:
        return
    current_notifications = load_notifications(INSIGNIA_NOTIFY_FILE)
    new_notifications = set()
    try:
        url = 'http://ogxbox.org/rss/insignia.xml'
        req = urllib2.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib2.urlopen(req)
        data = response.read()
        root = ET.fromstring(data)

        for item in root.findall('.//item'):
            title_element = item.find('title')
            link_element = item.find('link')
            if title_element is None:
                continue

            title = title_element.text
            link = link_element.text if link_element is not None else None

            if "(0 in 0 sessions)" in title:
                continue

            match = re.search(r'(\d+) players?', title)
            if match:
                players = int(match.group(1))
                if players > 0:
                    clean_title_text = clean_title(title)
                    new_notifications.add(clean_title_text)
                    if clean_title_text not in current_notifications:
                        game_id = extract_game_id(link)
                        thumb_url = get_game_thumbnail(game_id)
                        regular_notification_queue.append(("Insignia", clean_title_text, thumb_url))

        save_notifications(new_notifications, INSIGNIA_NOTIFY_FILE)
    except Exception as e:
        error_msg = "RSS Error: " + str(e)
        regular_notification_queue.append(("RSS Feed Error", error_msg, ""))
        new_notifications.add(error_msg)

def fetch_xlinkkai_events():
    if not XLINKKAI_EVENTS:
        return
    current_notifications = load_notifications(XLINKKAI_EVENT_FILE)
    new_notifications = set()
    try:
        url = 'http://ogxbox.org/rss/xlinkkai.xml'
        req = urllib2.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib2.urlopen(req)
        data = response.read()
        root = ET.fromstring(data)
        for item in root.findall('.//item'):
            title_element = item.find('title')
            if title_element is None:
                continue
            title = title_element.text
            if title.startswith("Game Event - Today") or title.startswith("Game Event - Tomorrow"):
                clean_title_text = re.sub(r'^Game Event - ', '', title)
                clean_title_text = clean_title(clean_title_text)
                if clean_title_text not in current_notifications:
                    thumb_url = get_xlinkkai_thumbnail(clean_title_text)
                    game_event_queue.append(("XLink Kai - Event", clean_title_text, thumb_url))
                    new_notifications.add(clean_title_text)
        save_notifications(new_notifications, XLINKKAI_EVENT_FILE)
    except Exception as e:
        regular_notification_queue.append(("RSS Feed Error", "XLink Kai RSS Error: " + str(e), ""))


def fetch_xlinkkai_sessions():
    if not XLINKKAI_SESSIONS:
        return
    current_notifications = load_notifications(XLINKKAI_NOTIFY_FILE)
    new_notifications = set()
    try:
        url = 'http://ogxbox.org/rss/xlinkkai.xml'
        req = urllib2.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib2.urlopen(req)
        data = response.read()
        root = ET.fromstring(data)
        for item in root.findall('.//item'):
            title_element = item.find('title')
            if title_element is None:
                continue
            title = title_element.text
            if "(0 in 0 sessions)" in title:
                continue
            match = re.search(r'(\d+) players?', title)
            if match:
                players = int(match.group(1))
                if players > 0 and title not in current_notifications:
                    clean_title_text = clean_title(title)
                    thumb_url = get_xlinkkai_thumbnail(clean_title_text)
                    regular_notification_queue.append(("XLink Kai", clean_title_text, thumb_url))
                    new_notifications.add(clean_title_text)
        save_notifications(new_notifications, XLINKKAI_NOTIFY_FILE)
    except Exception as e:
        regular_notification_queue.append(("RSS Feed Error", "XLink Kai RSS Error: " + str(e), ""))

clear_notifications_file(INSIGNIA_NOTIFY_FILE)
clear_notifications_file(XLINKKAI_NOTIFY_FILE)
fetch_insignia_events()
fetch_xlinkkai_events()
process_notifications()

while not monitor.abortRequested():
    fetch_insignia_sessions()
    fetch_xlinkkai_sessions()
    process_notifications()
    monitor.waitForAbort(60)
