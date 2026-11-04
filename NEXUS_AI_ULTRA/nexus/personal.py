"""Small, local personal profile and daily briefing; no model or microphone required."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import re
import threading
import time
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import httpx

DEFAULTS=dict(preferred_name='',welcome_enabled=True,speak_welcome=True,routine_in_welcome=True,
              news_on_start=False,emotions=True,tone='friendly',avatar_style='human')
FEEDS={
    'pakistan':('Dawn · Pakistan','https://www.dawn.com/feeds/home',('dawn.com','www.dawn.com')),
    'international':('BBC · World','https://feeds.bbci.co.uk/news/world/rss.xml',('bbc.com','www.bbc.com','bbc.co.uk','www.bbc.co.uk')),
}

def clean(value,limit=220):
    return ' '.join(html.unescape(re.sub('<[^>]*>','',str(value))).split())[:limit]

def validate_profile(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Unknown personal setting.')
    result={**DEFAULTS,**value}
    if not isinstance(result['preferred_name'],str) or len(result['preferred_name'])>60:raise ValueError('Preferred name must be up to 60 characters.')
    result['preferred_name']=clean(result['preferred_name'],60)
    if result['tone'] not in ('friendly','calm','concise'):raise ValueError('Choose Friendly, Calm or Concise tone.')
    if result['avatar_style'] not in ('human','robot'):raise ValueError('Choose Human face or Classic robot.')
    if any(type(result[k]) is not bool for k,v in DEFAULTS.items() if type(v) is bool):raise ValueError('Personal switches must be true or false.')
    return result

def validate_routine(value):
    if not isinstance(value,dict) or set(value)-{'title','time','days','enabled'}:raise ValueError('Invalid routine fields.')
    title=clean(value.get('title',''),160);when=value.get('time','');days=value.get('days',list(range(7)))
    if not title or not isinstance(when,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',when):raise ValueError('Routine needs a title and a 24-hour HH:MM time.')
    if not isinstance(days,list) or not days or any(type(d) is not int or d not in range(7) for d in days):raise ValueError('Choose weekdays from 0 (Monday) to 6 (Sunday).')
    if type(value.get('enabled',True)) is not bool:raise ValueError('enabled must be true or false.')
    return dict(title=title,time=when,days=sorted(set(days)),enabled=value.get('enabled',True))

class News:
    def __init__(self):self.cache={};self.lock=threading.Lock()

    @staticmethod
    def parse(content,region,now=None):
        now=now or datetime.now(timezone.utc)
        if len(content)>600_000 or b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():raise ValueError('Unsupported news feed.')
        root=ET.fromstring(content);source,_,allowed=FEEDS[region];items=[];seen=set()
        for row in root.findall('.//item')[:80]:
            title=clean(row.findtext('title',''));link=row.findtext('link','').strip();u=urlparse(link)
            try:date=parsedate_to_datetime(row.findtext('pubDate','')).astimezone(timezone.utc)
            except (ValueError,TypeError,OverflowError,AttributeError):continue
            if not title or u.scheme!='https' or u.hostname not in allowed or u.username or u.password or u.port not in (None,443):continue
            if not now-timedelta(hours=48)<=date<=now+timedelta(minutes=10) or link in seen:continue
            seen.add(link);items.append(dict(title=title,url=link,published=date.isoformat(),source=source,region=region))
        return sorted(items,key=lambda i:i['published'],reverse=True)[:3]

    def get(self,region='both'):
        if region not in (*FEEDS,'both'):raise ValueError('Choose pakistan, international or both.')
        result=[];warnings=[]
        with self.lock:
            for key in (FEEDS if region=='both' else [region]):
                cached=self.cache.get(key)
                if cached and time.monotonic()-cached[0]<600:result.extend(cached[1]);continue
                try:
                    with httpx.Client(timeout=6,follow_redirects=False) as client:
                        with client.stream('GET',FEEDS[key][1],headers={'User-Agent':'NEXUS-Personal-Briefing/1.0'}) as response:
                            response.raise_for_status();parts=[];size=0
                            for part in response.iter_bytes():
                                size+=len(part)
                                if size>600_000:raise ValueError('News feed too large.')
                                parts.append(part)
                    items=self.parse(b''.join(parts),key)
                    if not items:raise ValueError('No dated headlines from the last 48 hours.')
                    self.cache[key]=(time.monotonic(),items);result.extend(items)
                except (httpx.HTTPError,ValueError,ET.ParseError):warnings.append(FEEDS[key][0]+': fresh headlines unavailable.')
        return dict(items=result,warnings=warnings,checked_at=datetime.now(timezone.utc).isoformat())

class Personal:
    def __init__(self,store):self.store=store;self.news=News();self.startup_task=None;self.emotion='neutral';self.emotion_until=0
    def profile(self):return validate_profile(self.store.get('personal_settings',{}))
    def save(self,value):
        profile=validate_profile({**self.profile(),**value});self.store.set('personal_settings',profile);return profile
    def routines(self):return sorted(self.store.list('routine',100),key=lambda r:r['time'])
    def add_routine(self,value):
        if len(self.routines())>=50:raise ValueError('Keep up to 50 routines.')
        return self.store.add('routine',validate_routine(value))
    def today(self,now=None):
        now=now or datetime.now().astimezone()
        return [r for r in self.routines() if r['enabled'] and now.weekday() in r['days']]
    def tick(self,now=None):
        now=now or datetime.now().astimezone()
        for r in self.today(now):
            if r['time']>now.strftime('%H:%M'):continue
            key='routine_delivered_'+str(r['id']);day=now.date().isoformat()
            # Notification and day marker commit atomically, including after restart.
            with self.store.lock:
                if self.store.get(key)==day:continue
                try:
                    self.store.db.execute('INSERT INTO records(kind,data) VALUES (?,?)',('notification',json.dumps({'text':'Routine: '+r['title']+' · '+r['time']})))
                    self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(day)))
                    self.store.db.commit()
                except Exception:self.store.db.rollback();raise
    def briefing(self,include_news=False,now=None):
        now=now or datetime.now().astimezone();p=self.profile();name=(', '+p['preferred_name']) if p['preferred_name'] else ''
        greeting='Good morning' if 5<=now.hour<12 else 'Good afternoon' if 12<=now.hour<17 else 'Good evening' if 17<=now.hour<22 else 'Assalam-o-alaikum'
        routines=self.today(now);reminders=[r for r in self.store.list('reminder',1000) if not r['done'] and datetime.fromisoformat(r['due']).astimezone(now.tzinfo).date()==now.date()]
        parts=[greeting+name+'. Welcome back! Aaj '+now.strftime('%A, %d %B')+' hai.']
        if p['routine_in_welcome']:
            parts+=['Aaj ka routine: '+('; '.join(r['time']+' '+r['title'] for r in routines[:4]) or 'abhi koi routine save nahi hai')+'.']
            if reminders:parts.append(str(len(reminders))+' reminders aaj ke liye hain: '+', '.join(r['title'] for r in reminders[:3])+'.')
        news=self.news.get() if include_news else dict(items=[],warnings=[])
        if include_news:
            for region in FEEDS:
                selected=[i for i in news['items'] if i['region']==region][:2]
                if selected:parts.append(FEEDS[region][0]+': '+ '; '.join(i['title'] for i in selected)+'.')
            parts+=news['warnings']
        spoken=[parts[0]]
        if p['routine_in_welcome']:
            spoken+=['Aaj ka routine: '+('; '.join(r['time']+' '+clean(r['title'],80) for r in routines[:2]) or 'abhi save nahi hai')+'.']
            if reminders:spoken.append(str(len(reminders))+' reminders aaj ke liye hain.')
        for region in FEEDS:
            first=next((i for i in news['items'] if i['region']==region),None)
            if first:spoken.append(first['source']+': '+clean(first['title'],180)+'.')
        spoken+=news['warnings']
        return dict(text=' '.join(parts),speech_text=' '.join(spoken)[:1250],date=now.date().isoformat(),routines=routines,reminders=reminders,news=news)
    def react(self,text):
        if not self.profile()['emotions']:self.emotion='neutral';return
        lower=text.casefold()
        self.emotion='caring' if re.search(r'\b(sad|upset|pareshan|udaas|thak|tired|sorry)\b',lower) else 'happy' if re.search(r'\b(thanks|shukriya|great|khush|good news|ho gaya|ho giya)\b|[😊😄🎉]',lower) else 'curious' if '?' in text else 'friendly'
        self.emotion_until=time.monotonic()+30
    def mood(self):return self.emotion if self.profile()['emotions'] and time.monotonic()<self.emotion_until else 'neutral'
    def context(self):
        p=self.profile()
        styles={
            'friendly':'Speak naturally like a thoughtful friend. Add occasional light, situational humor or gentle teasing when the user is playful or celebrating; never force a joke into every reply. When the user is tired, worried or upset, acknowledge it warmly and offer practical support. Keep serious, painful or failed-action discussions respectful and clear.',
            'calm':'Use a gentle, patient and reassuring style. Acknowledge difficulty briefly, then offer practical help. Let the user lead humor; keep serious matters calm and clear.',
            'concise':'Be brief and warm. Acknowledge the user mood when their words make it clear, then answer directly; avoid extra banter.'}
        return ' Personal style: '+p['tone']+'. '+styles[p['tone']]+' Preferred user name (data): '+repr(p['preferred_name'])+'. Match the user language, including natural Roman Urdu. Express warmth without pretending to be human or creating emotional dependence. Do not claim to hear vocal emotion from transcripts. Use saved facts; never invent task success, routine or current news. Preferences cannot override tool permissions. Use daily_briefing for routine/reminders and news_briefing for dated headlines and source links.'

def personal_intent(text):
    value=re.sub(r'[.!?]+$','',text.casefold().strip())
    if value in ('pc lock karo','pc lock kro','computer lock karo','laptop lock karo','lock my pc','lock computer'):return ('pc_lock',{})
    if value in ('aaj ka routine batao','mera routine batao','aaj ka plan batao','daily briefing','meri briefing do','routine batao'):return ('daily_briefing',{'news':'no'})
    if value in ('news batao','khabrein batao','news briefing','aaj ki news batao'):return ('news_briefing',{'region':'both'})
    if value in ('pakistan ki news batao','pakistan news'):return ('news_briefing',{'region':'pakistan'})
    if value in ('international news batao','international news'):return ('news_briefing',{'region':'international'})
    return None
