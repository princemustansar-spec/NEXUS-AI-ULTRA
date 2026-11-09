"""Opt-in GitHub OAuth Device Flow, public search, and read-only repository metadata."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "Ov23liqOcMrEw8RRyMtA"
API = "https://api.github.com"
AUTH = "https://github.com"
_session = {"device_code": None, "expires": 0, "interval": 5, "last_poll": 0, "token": None, "user": None}

def _request(url, data=None, token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "NEXUS-AI-ULTRA"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read(1_000_000))
    except urllib.error.HTTPError as exc:
        raise ValueError("GitHub request failed (HTTP %s)" % exc.code) from None
    except urllib.error.URLError:
        raise ValueError("Cannot reach GitHub. Check internet connection.") from None

def start():
    result = _request(AUTH + "/login/device/code", {"client_id": CLIENT_ID, "scope": ""})
    code = result.get("device_code")
    if not code:
        raise ValueError("GitHub did not return a device code.")
    _session.update(device_code=code, expires=time.monotonic()+min(int(result.get("expires_in",900)),900),
                    interval=max(5,int(result.get("interval",5))),last_poll=0,token=None,user=None)
    url = result.get("verification_uri", "https://github.com/login/device")
    if not url.startswith("https://github.com/"):
        raise ValueError("Unexpected GitHub authorization URL.")
    webbrowser.open(url)
    return {"verification_uri":url,"user_code":result.get("user_code"),"expires_in":result.get("expires_in",900)}

def check():
    if _session["token"]:
        return {"connected":True,"user":_session["user"]}
    if not _session["device_code"] or time.monotonic() >= _session["expires"]:
        return {"connected":False,"status":"expired"}
    now = time.monotonic()
    if now-_session["last_poll"] < _session["interval"]:
        return {"connected":False,"status":"pending","retry_after":_session["interval"]}
    _session["last_poll"] = now
    result = _request(AUTH + "/login/oauth/access_token", {"client_id":CLIENT_ID,
            "device_code":_session["device_code"],"grant_type":"urn:ietf:params:oauth:grant-type:device_code"})
    if result.get("error"):
        err = result["error"]
        if err == "slow_down":
            _session["interval"] += 5
        if err in ("authorization_pending","slow_down"):
            return {"connected":False,"status":"pending","retry_after":_session["interval"]}
        _session["device_code"] = None
        return {"connected":False,"status":err}
    token = result.get("access_token")
    if not token:
        raise ValueError("GitHub did not return an access token.")
    user = _request(API+"/user",token=token).get("login")
    _session.update(token=token,user=user,device_code=None)
    return {"connected":True,"user":user}

def status():
    return {"connected":bool(_session["token"]),"user":_session["user"],
            "pending":bool(_session["device_code"] and time.monotonic()<_session["expires"])}

def disconnect():
    _session.update(device_code=None,expires=0,interval=5,last_poll=0,token=None,user=None)
    return {"connected":False}

def search(query):
    query = str(query).strip()
    if not query or len(query)>160:
        raise ValueError("Enter a GitHub repository search (1–160 characters).")
    params = urllib.parse.urlencode({"q":query,"per_page":10})
    # Public repository search intentionally never attaches an OAuth token.
    data = _request(API+"/search/repositories?"+params)
    return {"results":[{"name":x.get("full_name"),"description":x.get("description"),
             "url":x.get("html_url"),"stars":x.get("stargazers_count")}
             for x in data.get("items",[]) if str(x.get("html_url","")).startswith("https://github.com/")]}
