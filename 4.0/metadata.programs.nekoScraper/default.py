# -*- coding: utf-8 -*-
import sys, os, struct, json, urllib2, time, ast, shutil, datetime, re, xml.etree.ElementTree as ET
import xbmc, xbmcaddon, xbmcplugin, xbmcgui
from urlparse import parse_qsl
import urllib

addon = xbmcaddon.Addon()
LOG_PREFIX = "nekoScraper"

insignia_aware   = addon.getSetting('insignia_aware')
xlink_enabled    = addon.getSetting('xlink_enabled')
hawk_enabled    = addon.getSetting('hawk_enabled')

igdb_clientid    = addon.getSetting('igdb_clientid')
igdb_clientsecret= addon.getSetting('igdb_clientsecret')
_igdb_token_cache = {"token": None, "timestamp": 0}
_igdb_token_ttl = 3500  # ~58 minutes (tokens last 3600s)

def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log("[%s] %s" % (LOG_PREFIX, msg), level=level)

FEATURE_ID_TABLE = {
    0:"",1:"Players",2:"System Link",3:"Memory Unit",4:"HDD",
    5:"Custom Soundtracks",6:"Dolby Digital Sound",7:"480i",
    8:"HDTV",9:"HDTV 480p",10:"HDTV 720p",11:"HDTV 1080i",
    12:"HDTV 16x9",13:"Widescreen",14:"PAL 50Hz Only",
    15:"NTSC 60Hz Only",16:"Region",17:"Communicator Headset",
    18:"Steering Wheel",19:"Light Gun",20:"Arcade Stick",
    21:"Dance Pad",22:"Keyboard",23:"Flight Stick",
    24:"Unique Controller",25:"Ranking",
    26:"Xbox Live Aware",27:"Online Multiplayer",28:"Content Download",
    29:"User Generated Content",30:"Scoreboards",31:"Friends",
    32:"Voice",33:"Game Clips",34:"Clans",35:""
}

if addon.getSetting('insignia_aware') == "true":
    FEATURE_ID_TABLE[26] = "Insignia Aware"
if addon.getSetting('xlink_enabled') == "true":
    FEATURE_ID_TABLE[2]  = "XLink Kai"
if addon.getSetting('hawk_enabled') == "true":
    FEATURE_ID_TABLE[17]  = "Hawk Headset"

def get_igdb_token():
    global _igdb_token_cache
    if not igdb_clientid or not igdb_clientsecret:
        return None

    now = time.time()
    if _igdb_token_cache["token"] and (now - _igdb_token_cache["timestamp"]) < _igdb_token_ttl:
        return _igdb_token_cache["token"]

    try:
        data = "client_id=%s&client_secret=%s&grant_type=client_credentials" % (igdb_clientid, igdb_clientsecret)
        req = urllib2.Request("https://id.twitch.tv/oauth2/token", data.encode("utf-8"))
        res = urllib2.urlopen(req, timeout=10)
        token = json.load(res).get("access_token")
        if token:
            _igdb_token_cache["token"] = token
            _igdb_token_cache["timestamp"] = now
        return token
    except Exception as e:
        log("IGDB token error: %s" % e, xbmc.LOGERROR)
        return None

def query_igdb_game(name, token):
    if not igdb_clientid or not token:
        return None

    try:
        safe = name.replace('"', '\\"')

        strict_query = (
            'fields name, summary, first_release_date, genres.name, involved_companies; '
            'where platforms = (11) & (name = "%s" | name ~ "%s"); '
            'limit 1;'
        ) % (safe, safe)

        fuzzy_query = (
            'search "%s"; '
            'fields name, summary, first_release_date, genres.name, involved_companies; '
            'where platforms = (11); '
            'limit 1;'
        ) % safe

        def make_request(query):
            req = urllib2.Request("https://api.igdb.com/v4/games", query.encode("utf-8"))
            req.add_header("Client-ID", igdb_clientid)
            req.add_header("Authorization", "Bearer %s" % token)
            req.add_header("Accept", "application/json")
            return json.load(urllib2.urlopen(req, timeout=10))

        result = make_request(strict_query)

        if not result:
            result = make_request(fuzzy_query)
            if not result:
                return None

        game = result[0]

        dev_name = ""
        if "involved_companies" in game and game["involved_companies"]:
            company_ids = ",".join([str(cid) for cid in game["involved_companies"]])
            q2 = 'fields company.name, developer; where id = (%s);' % company_ids

            req2 = urllib2.Request("https://api.igdb.com/v4/involved_companies", q2.encode("utf-8"))
            req2.add_header("Client-ID", igdb_clientid)
            req2.add_header("Authorization", "Bearer %s" % token)
            req2.add_header("Accept", "application/json")

            companies = json.load(urllib2.urlopen(req2, timeout=10))
            for c in companies:
                if c.get("developer") and c.get("company") and "name" in c["company"]:
                    dev_name = c["company"]["name"]
                    break

        game["developer_name"] = dev_name
        return game

    except Exception as e:
        log("IGDB query error: %s" % e, xbmc.LOGERROR)
        return None

def read_titleid_and_region(path):
    try:
        with open(path,'rb') as f:
            if f.read(4)!=b'XBEH':
                return None,None
            f.seek(0x104); base=struct.unpack('<I',f.read(4))[0]
            f.seek(0x118); cert=struct.unpack('<I',f.read(4))[0]
            off=cert-base
            f.seek(off+0x8); titleid=struct.unpack('<I',f.read(4))[0]
            f.seek(off+0x0E); region_byte=struct.unpack('B',f.read(1))[0]
            if region_byte&1: region="NTSC-U/C"
            elif region_byte&2: region="NTSC-J"
            elif region_byte&4: region="PAL"
            else: region="Unknown"
            return "%08X"%titleid,region
    except Exception as e:
        log("XBE parse error: %s"%e, xbmc.LOGERROR)
        return None,None

def query_mobcat(titleid):
    try:
        req=urllib2.Request("https://www.mobcat.zip/XboxIDs/api.php?id=%s&imgs"%titleid,headers={'User-Agent':'nekoScraper'})
        data=json.loads(urllib2.urlopen(req,timeout=10).read())
        return data if isinstance(data,list) and data else None
    except Exception as e:
        log("MobCat API error: %s"%e, xbmc.LOGERROR)
        return None

def get_region_entry(entries,region):
    regmap={"NTSC-U/C":["NTSC-U","NTSC-UC"],"NTSC-J":["NTSC-J","NTSC-JM"],"PAL":["PAL","PAL-GBR","PAL-AUS"]}
    valid=regmap.get(region,[])
    for e in entries or []:
        try:
            stats=json.loads(e.get("Cover_Stats") or "[]")
            for s in stats:
                if s in valid: return e
        except: pass
    return entries[0] if entries else None

def decode_features(raw):
    try:
        if isinstance(raw,basestring):
            raw=ast.literal_eval(raw.strip())
        if not isinstance(raw,dict): return "",""
        g,o=[],[]
        for k in raw:
            for f in raw[k]:
                if not f or f[0]==0: continue
                fid=f[1]; n=FEATURE_ID_TABLE.get(fid,"Unknown")
                s="%s %d-%d"%(n,f[2],f[3]) if len(f)==4 else "%s %d"%(n,f[2]) if len(f)==3 else n
                (g if fid<=25 else o).append(s)
        return ", ".join(g),", ".join(o)
    except Exception as e:
        log("Feature decode error: %s"%e, xbmc.LOGERROR)
        return "",""

def xml_escape(t):
    if t is None: return ""
    return (t.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
             .replace('"',"&quot;").replace("'","&apos;"))

def download_artwork(xmid, folder):
    if not xmid:
        return

    try:
        url = "https://mobcat.zip/XboxIDs/title.php?%s&thumbnail=png" % xmid
        dest_main = os.path.join(folder, "icon.png")
        req = urllib2.Request(url, headers={'User-Agent':'nekoScraper'})
        resp = urllib2.urlopen(req, timeout=15)
        with open(dest_main, "wb") as f:
            shutil.copyfileobj(resp, f)
        resp.close()

        dest_icon = os.path.join(folder, "thumb.jpg")
        shutil.copy(dest_main, dest_icon)

        url = "https://mobcat.zip/XboxIDs/title.php?%s&thumbnail=unleashx" % xmid
        dest_poster = os.path.join(folder, "poster.jpg")
        req = urllib2.Request(url, headers={'User-Agent':'nekoScraper'})
        resp = urllib2.urlopen(req, timeout=15)
        with open(dest_poster, "wb") as f:
            shutil.copyfileobj(resp, f)
        resp.close()

    except Exception as e:
        log("Artwork download failed: %s -> %s" % (url, e), xbmc.LOGERROR)

def download_igdb_screenshots(game_id, token, folder):
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
    except:
        pass

    try:
        q = "fields image_id; where game = %d; limit 3;" % int(game_id)
        req = urllib2.Request("https://api.igdb.com/v4/screenshots", q.encode("utf-8"))
        req.add_header("Client-ID", igdb_clientid)
        req.add_header("Authorization", "Bearer %s" % token)
        req.add_header("Accept", "application/json")
        result = json.load(urllib2.urlopen(req, timeout=10))

        if not result or not isinstance(result, list):
            log("No screenshots found for game ID %s" % game_id)
            return

        for i, shot in enumerate(result):
            imgid = shot.get("image_id")
            if not imgid:
                continue
            url = "https://images.igdb.com/igdb/image/upload/t_screenshot_big/%s.jpg" % imgid
            dest = os.path.join(folder, "screenshot_%d.jpg" % (i+1))
            try:
                req = urllib2.Request(url, headers={'User-Agent': 'nekoScraper'})
                resp = urllib2.urlopen(req, timeout=15)
                tmp = dest + ".part"
                with open(tmp, "wb") as f:
                    shutil.copyfileobj(resp, f)
                resp.close()
                shutil.move(tmp, dest)
                log("Downloaded screenshot: %s" % dest)
            except Exception as e:
                log("Screenshot download failed: %s -> %s" % (url, e), xbmc.LOGERROR)
    except Exception as e:
        log("IGDB screenshot query error: %s" % e, xbmc.LOGERROR)

def create_synopsis_xml(out_path, info, region=None):
    name = info.get("Full_Name") or info.get("Title_Name") or ""
    pub  = info.get("Publisher") or ""
    dev  = info.get("Developer") or ""
    tid  = info.get("Title_ID") or ""
    feats = info.get("Features")
    fg, fo = decode_features(feats) if feats else ("", "")

    esrb = info.get("XBE_Rating", "")
    esrb = re.sub(r"^\(\d+\)\s*", "", esrb)
    release_date = info.get("Release_Date", "")
    year = ""

    token = get_igdb_token()
    ig = None
    genres = ""

    if token and name:
        ig = query_igdb_game(name, token)
        if ig:
            if ig.get("developer_name"):
                dev = ig["developer_name"]

            if ig.get("first_release_date"):
                try:
                    release_date = time.strftime("%Y-%m-%d", time.gmtime(ig["first_release_date"]))
                    year = time.strftime("%Y", time.gmtime(ig["first_release_date"]))
                except:
                    pass
            if ig.get("genres"):
                genres = ", ".join([g["name"] for g in ig["genres"] if "name" in g])
            if ig.get("summary"):
                info["Overview"] = ig["summary"]

            screenshots_dir = os.path.join(os.path.dirname(out_path), "screenshots")
            if ig.get("id"):
                download_igdb_screenshots(ig["id"], token, screenshots_dir)

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<synopsis>",
        "  <title>%s</title>" % xml_escape(name),
        "  <developer>%s</developer>" % xml_escape(dev),
        "  <publisher>%s</publisher>" % xml_escape(pub),
        "  <platform>Xbox</platform>",
        "  <region>%s</region>" % xml_escape(region or ""),
        "  <features_general>%s</features_general>" % xml_escape(fg),
        "  <features_online>%s</features_online>" % xml_escape(fo),
        "  <titleid>%s</titleid>" % xml_escape(tid),
        "  <overview>%s</overview>" % xml_escape(info.get("Overview") or "")
    ]

    if year:
        xml.append("  <year>(%s)</year>" % xml_escape(year))
    if release_date:
        xml.append("  <release_date>%s</release_date>" % xml_escape(release_date))
    if esrb:
        xml.append("  <esrb>%s</esrb>" % xml_escape(esrb))
    if genres:
        xml.append("  <genre>%s</genre>" % xml_escape(genres))

    xml.append("</synopsis>")

    try:
        txt = "\n".join(xml)
        if isinstance(txt, unicode): txt = txt.encode("utf-8")
        with open(out_path, "wb") as f:
            f.write(txt)
        log("Wrote synopsis to %s" % out_path)
    except Exception as e:
        log("XML write failed: %s" % e, xbmc.LOGERROR)

def load_metadata(root_dir):
    path=os.path.join(root_dir,"_resources","default.xml")
    if not os.path.exists(path): return {}
    tree=ET.parse(path); root=tree.getroot(); info={}
    def get_text(tag):
        el=root.find(tag)
        return el.text.strip() if el is not None and el.text else ""
    info["title"]=get_text("title")
    info["developer"]=get_text("developer")
    info["publisher"]=get_text("publisher")
    info["overview"]=get_text("overview")
    info["year"]=get_text("year")
    info["genre"]=[g.strip() for g in get_text("genre").split(",") if g]
    info["platform"]=[get_text("platform")]
    info["region"]=get_text("region")
    info["generalfeature"] = get_text("features_general")
    info["onlinefeature"] = get_text("features_online")
    info["esrb"] = get_text("esrb")
    info["release_date"] = get_text("release_date")

    return info

def get_details(path, handle):
    root_dir=os.path.dirname(path)
    resdir=os.path.join(root_dir,"_resources")
    xmlpath=os.path.join(resdir,"default.xml")
    artdir=os.path.join(resdir,"artwork")

    if not os.path.exists(xmlpath):
        tid,reg=read_titleid_and_region(path)
        if not tid: return False
        entries=query_mobcat(tid)
        info=get_region_entry(entries,reg) if entries else {"Title_ID":tid}
        if not os.path.exists(resdir):
            try: os.makedirs(resdir)
            except: pass
        if not os.path.exists(artdir):
            try: os.makedirs(artdir)
            except: pass
        create_synopsis_xml(xmlpath, info, reg)
        xmid=info.get("XMID")
        if xmid: download_artwork(xmid, artdir)

    info=load_metadata(root_dir)
    if not info.get("title"):
        return False

    li=xbmcgui.ListItem(info["title"], offscreen=True)
    li.setInfo("program", info)
    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=li)
    return True

def get_params(argv):
    result={'handle':int(argv[0])}
    if len(argv)<2 or not argv[1]: return result
    result.update(parse_qsl(argv[1].lstrip('?')))
    return result

def run():
    params=get_params(sys.argv[1:])
    action=params.get("action")
    if action=="getdetails" and "url" in params:
        url=urllib.unquote(params["url"]).decode("utf-8")
        ok=get_details(url, params["handle"])
        if not ok:
            xbmcplugin.endOfDirectory(params["handle"], succeeded=False)
    else:
        xbmcplugin.endOfDirectory(params["handle"])

if __name__=="__main__":
    run()
