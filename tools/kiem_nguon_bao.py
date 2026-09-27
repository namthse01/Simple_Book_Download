# -*- coding: utf-8 -*-
"""Quet thu cac RSS ung vien: con song khong, co bao nhieu bai, bai moi nhat bao gio."""
from __future__ import annotations
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

UNG_VIEN = {
"vn": [
 ("VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss", "vi"),
 ("Tuoi Tre", "https://tuoitre.vn/rss/tin-moi-nhat.rss", "vi"),
 ("Thanh Nien", "https://thanhnien.vn/rss/home.rss", "vi"),
 ("VietnamNet", "https://vietnamnet.vn/rss/tin-moi-nhat.rss", "vi"),
 ("Dan Tri", "https://dantri.com.vn/rss/home.rss", "vi"),
 ("Lao Dong", "https://laodong.vn/rss/home.rss", "vi"),
 ("Tien Phong", "https://tienphong.vn/rss/home.rss", "vi"),
 ("VTV", "https://vtv.vn/trong-nuoc.rss", "vi"),
 ("Nhan Dan", "https://nhandan.vn/rss/trang-chu-1727.rss", "vi"),
 ("VOV", "https://vov.vn/rss/tin-moi-nhat.rss", "vi"),
 ("VietnamPlus", "https://www.vietnamplus.vn/rss/tin-moi.rss", "vi"),
 ("Znews", "https://znews.vn/rss/tin-moi.html", "vi"),
 ("Bao Chinh Phu", "https://baochinhphu.vn/rss/home.rss", "vi"),
 ("Nguoi Lao Dong", "https://nld.com.vn/rss/home.rss", "vi"),
 ("SGGP", "https://www.sggp.org.vn/rss/trangchu.rss", "vi"),
],
"us": [
 ("NPR", "https://feeds.npr.org/1001/rss.xml", "en"),
 ("CBS News", "https://www.cbsnews.com/latest/rss/main", "en"),
 ("NBC News", "https://feeds.nbcnews.com/nbcnews/public/news", "en"),
 ("ABC News", "https://abcnews.go.com/abcnews/topstories", "en"),
 ("USA Today", "https://rssfeeds.usatoday.com/usatoday-NewsTopStories", "en"),
 ("Politico", "https://rss.politico.com/politics-news.xml", "en"),
 ("The Hill", "https://thehill.com/news/feed/", "en"),
 ("Los Angeles Times", "https://www.latimes.com/world-nation/rss2.0.xml", "en"),
 ("CNN", "http://rss.cnn.com/rss/edition.rss", "en"),
 ("Washington Post", "https://feeds.washingtonpost.com/rss/world", "en"),
 ("Time", "https://time.com/feed/", "en"),
 ("Newsweek", "https://www.newsweek.com/rss", "en"),
 ("Fox News", "https://moxie.foxnews.com/google-publisher/latest.xml", "en"),
 ("PBS NewsHour", "https://www.pbs.org/newshour/feeds/rss/headlines", "en"),
 ("Axios", "https://api.axios.com/feed/", "en"),
 ("VOA News", "https://www.voanews.com/api/zq$omekvi_", "en"),
],
"uk": [
 ("BBC News", "https://feeds.bbci.co.uk/news/rss.xml", "en"),
 ("The Guardian", "https://www.theguardian.com/uk/rss", "en"),
 ("Sky News", "https://feeds.skynews.com/feeds/rss/home.xml", "en"),
 ("The Independent", "https://www.independent.co.uk/news/uk/rss", "en"),
 ("The Telegraph", "https://www.telegraph.co.uk/rss.xml", "en"),
 ("Daily Mail", "https://www.dailymail.co.uk/articles.rss", "en"),
 ("Evening Standard", "https://www.standard.co.uk/rss", "en"),
 ("The Mirror", "https://www.mirror.co.uk/news/?service=rss", "en"),
 ("Metro", "https://metro.co.uk/feed/", "en"),
 ("The Economist", "https://www.economist.com/latest/rss.xml", "en"),
 ("Financial Times", "https://www.ft.com/rss/home", "en"),
 ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
],
"fr": [
 ("Le Monde", "https://www.lemonde.fr/rss/une.xml", "fr"),
 ("Le Figaro", "https://www.lefigaro.fr/rss/figaro_actualites.xml", "fr"),
 ("Liberation", "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml", "fr"),
 ("France 24", "https://www.france24.com/fr/rss", "fr"),
 ("France 24 (EN)", "https://www.france24.com/en/rss", "en"),
 ("RFI", "https://www.rfi.fr/fr/rss", "fr"),
 ("RFI (EN)", "https://www.rfi.fr/en/rss", "en"),
 ("L'Express", "https://www.lexpress.fr/rss/alaune.xml", "fr"),
 ("Les Echos", "https://services.lesechos.fr/rss/les-echos-monde.xml", "fr"),
 ("20 Minutes", "https://www.20minutes.fr/feeds/rss-une.xml", "fr"),
 ("Ouest-France", "https://www.ouest-france.fr/rss/une", "fr"),
 ("France Info", "https://www.francetvinfo.fr/titres.rss", "fr"),
 ("Le Point", "https://www.lepoint.fr/24h-infos/rss.xml", "fr"),
 ("Courrier International", "https://www.courrierinternational.com/feed/all/rss.xml", "fr"),
],
"cn": [
 ("Xinhua (EN)", "https://english.news.cn/rss/worldrss.xml", "en"),
 ("People's Daily (EN)", "http://en.people.cn/rss/China.xml", "en"),
 ("China Daily", "http://www.chinadaily.com.cn/rss/china_rss.xml", "en"),
 ("China Daily World", "http://www.chinadaily.com.cn/rss/world_rss.xml", "en"),
 ("Global Times", "https://www.globaltimes.cn/rss/outbrain.xml", "en"),
 ("CGTN", "https://www.cgtn.com/subscribe/rss/section/world.xml", "en"),
 ("SCMP", "https://www.scmp.com/rss/91/feed", "en"),
 ("SCMP China", "https://www.scmp.com/rss/4/feed", "en"),
 ("Caixin Global", "https://www.caixinglobal.com/rss/", "en"),
 ("Sina News", "https://rss.sina.com.cn/news/marquee/ddt.xml", "zh"),
 ("Zaobao TQ", "https://www.zaobao.com/realtime/china/rss.xml", "zh"),
 ("Guancha", "https://www.guancha.cn/headline/rss.xml", "zh"),
 ("Yicai Global", "https://www.yicaiglobal.com/rss/news", "en"),
 ("Sixth Tone", "https://www.sixthtone.com/rss", "en"),
],
"ru": [
 ("RIA Novosti", "https://ria.ru/export/rss2/archive/index.xml", "ru"),
 ("TASS (EN)", "https://tass.com/rss/v2.xml", "en"),
 ("TASS", "https://tass.ru/rss/v2.xml", "ru"),
 ("RT (EN)", "https://www.rt.com/rss/", "en"),
 ("Kommersant", "https://www.kommersant.ru/RSS/news.xml", "ru"),
 ("Lenta.ru", "https://lenta.ru/rss/news", "ru"),
 ("Interfax", "https://www.interfax.ru/rss.asp", "ru"),
 ("Gazeta.ru", "https://www.gazeta.ru/export/rss/lenta.xml", "ru"),
 ("Izvestia", "https://iz.ru/xml/rss/all.xml", "ru"),
 ("RBC", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "ru"),
 ("Meduza (EN)", "https://meduza.io/rss/en/all", "en"),
 ("Moscow Times (EN)", "https://www.themoscowtimes.com/rss/news", "en"),
 ("Vedomosti", "https://www.vedomosti.ru/rss/news", "ru"),
],
"jp": [
 ("NHK", "https://www3.nhk.or.jp/rss/news/cat0.xml", "ja"),
 ("NHK World (EN)", "https://www3.nhk.or.jp/nhkworld/en/news/rss/all.xml", "en"),
 ("Asahi", "https://www.asahi.com/rss/asahi/newsheadlines.rdf", "ja"),
 ("Mainichi", "https://mainichi.jp/rss/etc/mainichi-flash.rss", "ja"),
 ("Yomiuri", "https://www.yomiuri.co.jp/rss/yol/latestnews", "ja"),
 ("Japan Times", "https://www.japantimes.co.jp/feed/", "en"),
 ("Kyodo News (EN)", "https://english.kyodonews.net/rss/news.xml", "en"),
 ("Sankei", "https://www.sankei.com/rss/news/flash.xml", "ja"),
 ("ITmedia", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml", "ja"),
 ("Nikkei Asia (EN)", "https://asia.nikkei.com/rss/feed/nar", "en"),
 ("Japan Today (EN)", "https://japantoday.com/feed", "en"),
 ("NHK Shakai", "https://www3.nhk.or.jp/rss/news/cat1.xml", "ja"),
],
"br": [
 ("G1 Globo", "https://g1.globo.com/rss/g1/", "pt"),
 ("Folha de S.Paulo", "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "pt"),
 ("Estadao", "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/ultimas/?outputType=xml", "pt"),
 ("UOL", "https://rss.uol.com.br/feed/noticias.xml", "pt"),
 ("BBC Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml", "pt"),
 ("CNN Brasil", "https://www.cnnbrasil.com.br/feed/", "pt"),
 ("Agencia Brasil", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml", "pt"),
 ("Poder360", "https://www.poder360.com.br/feed/", "pt"),
 ("Exame", "https://exame.com/feed/", "pt"),
 ("Gazeta do Povo", "https://www.gazetadopovo.com.br/feed/rss/ultimas-noticias.xml", "pt"),
 ("Brazil Reports (EN)", "https://brazilreports.com/feed/", "en"),
 ("R7", "https://noticias.r7.com/feed.xml", "pt"),
],
"za": [
 ("News24", "https://feeds.24.com/articles/news24/TopStories/rss", "en"),
 ("Mail & Guardian", "https://mg.co.za/feed/", "en"),
 ("IOL", "https://www.iol.co.za/cmlink/1.640", "en"),
 ("TimesLIVE", "https://www.timeslive.co.za/rss/", "en"),
 ("Daily Maverick", "https://www.dailymaverick.co.za/dmrss/", "en"),
 ("SABC News", "https://www.sabcnews.com/sabcnews/feed/", "en"),
 ("BusinessTech", "https://businesstech.co.za/news/feed/", "en"),
 ("EWN", "https://ewn.co.za/RSS%20Feeds/Latest%20News", "en"),
 ("The Citizen", "https://www.citizen.co.za/feed/", "en"),
 ("BusinessLIVE", "https://www.businesslive.co.za/rss/?publication=bd", "en"),
 ("SowetanLIVE", "https://www.sowetanlive.co.za/rss/", "en"),
 ("The South African", "https://www.thesouthafrican.com/feed/", "en"),
],
}


def thu(arg):
    quoc, ten, url, lang = arg
    try:
        rq = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
        with urllib.request.urlopen(rq, timeout=20) as r:
            raw = r.read(400000)
            code = r.status
    except Exception as exc:
        return dict(quoc=quoc, ten=ten, url=url, lang=lang, ok=False,
                    loi=f"{type(exc).__name__}: {str(exc)[:60]}")
    txt = raw.decode("utf-8", "replace")
    if "<rss" not in txt[:2000] and "<feed" not in txt[:2000] and "<rdf" not in txt[:2000].lower():
        return dict(quoc=quoc, ten=ten, url=url, lang=lang, ok=False,
                    loi=f"khong phai RSS (HTTP {code})")
    items = re.findall(r"<item[ >]|<entry[ >]", txt)
    ngay = ""
    m = re.search(r"<(?:pubDate|published|updated|dc:date)>(.*?)</", txt, re.S)
    tuoi_gio = None
    if m:
        ngay = m.group(1).strip()[:40]
        for parse in (lambda s: parsedate_to_datetime(s),
                      lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))):
            try:
                d = parse(ngay)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                tuoi_gio = round((datetime.now(timezone.utc) - d).total_seconds() / 3600, 1)
                break
            except Exception:
                continue
    return dict(quoc=quoc, ten=ten, url=url, lang=lang, ok=len(items) >= 3,
                so_bai=len(items), ngay=ngay, tuoi_gio=tuoi_gio,
                loi="" if len(items) >= 3 else f"chi {len(items)} bai")


viec = [(q, t, u, l) for q, ds in UNG_VIEN.items() for (t, u, l) in ds]
with ThreadPoolExecutor(max_workers=16) as pool:
    kq = list(pool.map(thu, viec))

song = [k for k in kq if k["ok"]]
chet = [k for k in kq if not k["ok"]]
print(f"SONG {len(song)}/{len(kq)}\n")
for q in UNG_VIEN:
    ds = [k for k in song if k["quoc"] == q]
    print(f"--- {q.upper()} ({len(ds)} song) ---")
    for k in ds:
        print(f"  OK  {k['ten']:<24} {k['so_bai']:>3} bai  moi nhat {k['tuoi_gio']}h  [{k['lang']}]")
    for k in [x for x in chet if x["quoc"] == q]:
        print(f"  --  {k['ten']:<24} {k['loi']}")
json.dump(kq, open(sys.argv[1] if len(sys.argv) > 1 else "kq_feed.json", "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
