"""Optional ChatGPT plan provider for NEXUS AI ULTRA. No access to ChatGPT history.

Official OSS Sign in with ChatGPT dynamic-client OAuth with PKCE and OIDC.
Credentials are Windows-DPAPI encrypted and never included in API responses.
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs

import httpx


class PooledHTTP:
    """Thread-safe keep-alive transport; bearer credentials are passed per request."""
    def __init__(self):self.client=None;self.lock=threading.Lock()
    def get_client(self):
        with self.lock:
            if self.client is None or self.client.is_closed:
                self.client=httpx.Client(follow_redirects=False,limits=httpx.Limits(max_connections=4,max_keepalive_connections=2,keepalive_expiry=60))
            return self.client
    def __getattr__(self,name):
        def call(*args,**kwargs):
            if isinstance(kwargs.get('timeout'),(int,float)):kwargs['timeout']=httpx.Timeout(kwargs['timeout'],connect=5)
            return getattr(self.get_client(),name)(*args,**kwargs)
        return call
    def close(self):
        with self.lock:
            if self.client:self.client.close();self.client=None


requests=PooledHTTP()

AUTH = "https://auth.openai.com"
API = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
ROOT = Path(os.getenv("NEXUS_DATA_DIR", Path.home() / ".nexus_ai_ultra")) / "accounts" / "chatgpt"
HOST_PATH = ROOT / "host.json"
CREDS_PATH = ROOT / "session.dpapi"
_LOCK = threading.RLock()
_LOGIN = {"pending": False, "error": ""}


def _protect(data):
    from .account_secrets import protect
    return protect(data)


def _unprotect(data):
    from .account_secrets import unprotect
    return unprotect(data)


def _save_session(value):
    ROOT.mkdir(parents=True, exist_ok=True)
    encrypted = _protect(json.dumps(value, separators=(",", ":")).encode("utf-8"))
    tmp = CREDS_PATH.with_suffix(".tmp")
    tmp.write_bytes(encrypted)
    os.replace(tmp, CREDS_PATH)


def _load_session():
    if not CREDS_PATH.is_file():
        return None
    return json.loads(_unprotect(CREDS_PATH.read_bytes()).decode("utf-8"))


def _host_id():
    ROOT.mkdir(parents=True, exist_ok=True)
    if HOST_PATH.exists():
        value = json.loads(HOST_PATH.read_text(encoding="utf-8")).get("ext_agent_host_id")
        if isinstance(value, str) and value.startswith("urn:uuid:"):
            return value
        raise RuntimeError("Stored ChatGPT host ID invalid")
    value = "urn:uuid:" + str(uuid.uuid4())
    HOST_PATH.write_text(json.dumps({"ext_agent_host_id": value}), encoding="utf-8")
    return value


def _b64url(blob):
    return base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def _http_error(resp):
    return RuntimeError("ChatGPT HTTP %d. Check connection permissions, plan limits, or sign in again." % resp.status_code)


def status():
    with _LOCK:
        try:session = _load_session()
        except Exception:return {"connected":False,"pending":False,"error":"Saved ChatGPT connection could not be unlocked. Sign in again."}
        connected = bool(session and "chatgpt.tokens.use.direct" in session.get("scopes", []))
        return {"ok": True, "connected": connected, "pending": _LOGIN["pending"],
                "error": _LOGIN["error"][:140],
                "account": session.get("email", "") if connected else "",
                "model": session.get("model", "") if connected else ""}


def _verify_id_token(token, client_id, nonce):
    import jwt
    from jwt import PyJWKClient
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256":
        raise RuntimeError("Unexpected ID token algorithm")
    jwks = PyJWKClient(AUTH + "/.well-known/jwks.json", timeout=10)
    key = jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=["RS256"], issuer=AUTH,
                        audience=client_id, options={"require": ["sub", "iss", "aud", "exp", "iat"]}, leeway=5)
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise RuntimeError("ID token nonce verification failed")
    if not claims.get("sub"):
        raise RuntimeError("Missing ID token subject")
    return claims


def _login_worker():
    server = None
    try:
        with _LOCK:
            old = _load_session()
            host_id = _host_id()
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        class Callback(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return
            def do_GET(self):
                path = urlsplit(self.path)
                if path.path != "/auth/callback":
                    self.send_response(404); self.end_headers(); return
                params = parse_qs(path.query)
                if not secrets.compare_digest(params.get("state", [""])[0], state):
                    self.send_response(400); self.end_headers(); return
                self.server.received = {key: v[0] for key, v in params.items() if v}
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b"<html><body><h3>ChatGPT sign-in received.</h3><p>Return to NEXUS to check status.</p></body></html>")
        server = HTTPServer(("127.0.0.1", 0), Callback)
        server.timeout = 1
        server.received = None
        redirect = "http://127.0.0.1:%d/auth/callback" % server.server_port
        issued = old.get("client_id") if old else None
        params = {"client_id": issued or "dynamic_agent_client", "ext_agent_host_id": host_id,
                  "response_type": "code", "redirect_uri": redirect, "scope": SCOPES,
                  "resource": API, "state": state, "nonce": nonce,
                  "code_challenge_method": "S256", "code_challenge": challenge}
        if not issued:
            params["agent_name_hint"] = "NEXUS AI ULTRA"
        if old and old.get("id_token"):
            params["id_token_hint"] = old["id_token"]
        url = AUTH + "/api/accounts/authorize?" + urlencode(params)
        if not webbrowser.open(url):
            raise RuntimeError("Could not open system browser")
        end = time.monotonic() + 180
        while time.monotonic() < end and server.received is None:
            server.handle_request()
        callback = server.received
        if not callback:
            raise RuntimeError("Browser sign-in timed out")
        if not secrets.compare_digest(callback.get("state", ""), state):
            raise RuntimeError("OAuth state did not match")
        if callback.get("error"):
            raise RuntimeError("ChatGPT sign-in was denied")
        code = callback.get("code")
        client_id = callback.get("client_id") or issued
        if not code or not client_id or client_id == "dynamic_agent_client":
            raise RuntimeError("OAuth registration code or issued client ID missing")
        if issued and client_id != issued:
            raise RuntimeError("OAuth client ID changed unexpectedly")
        token_resp = requests.post(AUTH + "/api/accounts/oauth/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "code_verifier": verifier, "redirect_uri": redirect, "resource": API}, timeout=30)
        if not token_resp.is_success:
            raise _http_error(token_resp)
        tokens = token_resp.json()
        claims = _verify_id_token(tokens["id_token"], client_id, nonce)
        if old and old.get("sub") != claims["sub"]:
            raise RuntimeError("Signed-in ChatGPT identity differs from existing registration")
        scopes = tokens.get("scope", "").split()
        if "chatgpt.tokens.use.direct" not in scopes:
            raise RuntimeError("Signed in without ChatGPT plan usage permission")
        session = {"client_id": client_id, "host_id": host_id, "sub": claims["sub"],
                   "email": claims.get("email", ""), "id_token": tokens["id_token"],
                   "access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token", ""),
                   "scopes": scopes, "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
                   "model": old.get("model", "") if old else ""}
        with _LOCK:
            _save_session(session)
    except Exception as error:
        with _LOCK:
            _LOGIN["error"] = str(error)[:150] if isinstance(error, RuntimeError) else "ChatGPT sign-in failed ("+type(error).__name__+"). Retry or check your connection."
    finally:
        if server is not None:
            server.server_close()
        with _LOCK:
            _LOGIN["pending"] = False


def start_login():
    import jwt
    if os.name != "nt":raise RuntimeError("ChatGPT desktop sign-in requires Windows secure credential storage.")
    with _LOCK:
        if _LOGIN["pending"]:
            return {"ok": False, "error": "Sign-in already running"}
        _LOGIN["pending"] = True
        _LOGIN["error"] = ""
        threading.Thread(target=_login_worker, daemon=True).start()
    return {"ok": True, "message": "Browser sign-in starting; review ChatGPT permission there"}


def _refresh_if_needed():
    with _LOCK:
        session = _load_session()
        if not session or "chatgpt.tokens.use.direct" not in session.get("scopes", []):
            raise RuntimeError("ChatGPT account not connected")
        if session["expires_at"] > time.time() + 90:
            return session
        if not session.get("refresh_token"):
            raise RuntimeError("ChatGPT session expired; sign in again")
        resp = requests.post(AUTH + "/api/accounts/oauth/token", data={
            "grant_type": "refresh_token", "client_id": session["client_id"],
            "refresh_token": session["refresh_token"], "resource": API}, timeout=30)
        if not resp.is_success:
            raise _http_error(resp)
        data = resp.json()
        session["access_token"] = data["access_token"]
        session["refresh_token"] = data.get("refresh_token", session["refresh_token"])
        session["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        session["scopes"] = data.get("scope", " ".join(session["scopes"])).split()
        if "chatgpt.tokens.use.direct" not in session["scopes"]:
            raise RuntimeError("ChatGPT permission revoked")
        _save_session(session)
        return session


def models():
    session = _refresh_if_needed()
    resp = requests.get(API + "/models", headers={"Authorization": "Bearer " + session["access_token"]}, timeout=20)
    if not resp.is_success:
        raise _http_error(resp)
    choices = [x for x in resp.json().get("models", []) if x.get("visibility") == "list" and x.get("slug")]
    return [{"slug": x["slug"], "name": x.get("display_name") or x["slug"]} for x in choices]


def select_model(model):
    choices = models()
    if model not in {x["slug"] for x in choices}:
        return {"ok": False, "error": "Model not in signed-in ChatGPT account catalog"}
    with _LOCK:
        session = _load_session()
        session["model"] = model
        _save_session(session)
    return {"ok": True, "model": model}


def public_models():
    try:
        return {"ok": True, "models": models()}
    except Exception as error:
        return {"ok": False, "error": str(error)[:150], "models": []}


def _response_input(messages):
    result = []
    for msg in messages:
        role = msg.get("role")
        if role in ("user", "assistant", "system", "developer"):
            content = msg.get("content")
            if isinstance(content, str) and content:
                result.append({"role": "developer" if role == "system" else role, "content": content})
            for call in msg.get("tool_calls") or []:
                fn = call.get("function") or {}
                args = fn.get("arguments", "{}")
                if isinstance(args, dict):
                    args = json.dumps(args, ensure_ascii=False)
                result.append({"type": "function_call", "call_id": str(call.get("id") or ""),
                               "name": str(fn.get("name") or ""), "arguments": args})
        elif role == "tool":
            result.append({"type": "function_call_output", "call_id": str(msg.get("tool_call_id", "")),
                           "output": str(msg.get("content", ""))})
    return result


def _tools_for_responses(tools):
    out = []
    for t in tools or []:
        if t.get("type") != "function":
            continue
        fn = t["function"]
        out.append({"type": "function", "name": fn["name"],
                    "description": fn.get("description", ""), "parameters": fn.get("parameters") or {"type":"object","properties":{}}})
    return out


def _sse_completed(stream):
    """Collect streamed visible output as well as the terminal Responses item list.

    A Responses completion may omit output text from its final output array.
    Delta events must be processed rather than discarded.
    """
    from collections import defaultdict

    response = None
    text_parts = defaultdict(list)
    text_done = {}
    tool_items = {}
    tool_arg_parts = defaultdict(list)
    for raw in stream.iter_lines():
        if not raw:
            continue
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        if not raw.startswith("data: "):
            continue
        data = raw[6:]
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except (TypeError, ValueError):
            continue
        kind = event.get("type")
        index = event.get("output_index", 0)
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                text_parts[index].append(delta)
        elif kind == "response.output_text.done":
            done = event.get("text")
            if isinstance(done, str):
                text_done[index] = done
        elif kind in ("response.output_item.added", "response.output_item.done"):
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                tool_items[index] = item
        elif kind == "response.function_call_arguments.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                tool_arg_parts[index].append(delta)
        elif kind in ("response.failed", "response.incomplete", "error"):
            detail = event.get("response") or {}
            err = detail.get("error") if isinstance(detail, dict) else None
            err = err or event.get("error") or {}
            code = err.get("code") or "unknown" if isinstance(err, dict) else "unknown"
            raise RuntimeError("ChatGPT response failed: " + str(code)[:100])
        elif kind == "response.completed":
            response = event.get("response")
            break

    if not isinstance(response, dict):
        raise RuntimeError("ChatGPT stream ended before response.completed")

    output = response.get("output") or []
    has_visible = any(
        isinstance(item, dict) and (
            item.get("type") == "function_call"
            or (item.get("type") == "message" and any(
                isinstance(part, dict) and part.get("type") == "output_text"
                and part.get("text")
                for part in (item.get("content") or [])
            ))
        ) for item in output
    )
    if not has_visible:
        synthesized = []
        all_text = []
        for index in sorted(set(text_parts) | set(text_done)):
            value = text_done.get(index)
            if value is None:
                value = "".join(text_parts[index])
            if value:
                all_text.append(value)
        if all_text:
            synthesized.append({"type": "message", "content": [
                {"type": "output_text", "text": "\n".join(all_text)}
            ]})
        for index in sorted(set(tool_items) | set(tool_arg_parts)):
            item = tool_items.get(index) or {}
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments") or "".join(tool_arg_parts[index])
            if call_id and name:
                synthesized.append({"type": "function_call", "call_id": call_id,
                                    "name": name, "arguments": arguments or "{}"})
        if synthesized:
            response["output"] = list(output) + synthesized

    # Some completions return a partial output array; preserve both streamed text and tool calls.
    output=response.get('output') or []
    if (text_parts or text_done) and not any(i.get('type')=='message' and any(p.get('text') for p in i.get('content',[])) for i in output):
        text='\n'.join(text_done.get(i,''.join(text_parts[i])) for i in sorted(set(text_parts)|set(text_done)))
        if text:output.append({'type':'message','content':[{'type':'output_text','text':text}]})
    existing={i.get('call_id') for i in output if i.get('type')=='function_call'}
    for index,item in tool_items.items():
        if item.get('call_id') and item['call_id'] not in existing:
            output.append({**item,'arguments':item.get('arguments') or ''.join(tool_arg_parts[index]) or '{}'})
    response['output']=output
    return response

def _chat_result(response):
    texts, calls = [], []
    for item in response.get("output") or []:
        if item.get("type") == "function_call":
            calls.append({"id": item["call_id"], "type": "function",
                          "function": {"name": item["name"], "arguments": item.get("arguments", "{}")}})
        if item.get("type") == "message":
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
    if not texts and not calls:
        raise RuntimeError("ChatGPT response contained no text or function calls")
    return {"choices": [{"message": {"role": "assistant", "content": "\n".join(texts), "tool_calls": calls}}]}


def request_chatgpt(messages, tools=None):
    session = _refresh_if_needed()
    model = session.get("model")
    if not model:
        available = models()
        if not available:
            raise RuntimeError("No ChatGPT models available; check permissions")
        model = available[0]["slug"]
        with _LOCK:
            session=_load_session();session["model"]=model;_save_session(session)
    body = {"model": model, "input": _response_input(messages), "store": False, "stream": True}
    if tools:
        body["input"].insert(0, {"type": "additional_tools", "role": "developer",
                                 "tools": _tools_for_responses(tools)})
    with requests.stream("POST", API + "/responses", headers={"Authorization": "Bearer " + session["access_token"]},
                       json=body, timeout=35) as stream:
        if not stream.is_success:
            raise _http_error(stream)
        response = _sse_completed(stream)
    return _chat_result(response)


def disconnect():
    with _LOCK:
        if _LOGIN["pending"]:
            return {"ok": False, "error": "Sign-in in progress"}
        session = _load_session()
        if not session:
            return {"ok": True}
        if session.get("refresh_token"):
            try:
                discovery = requests.get(AUTH + "/.well-known/openid-configuration", timeout=10)
                discovery.raise_for_status()
                endpoint = discovery.json().get("revocation_endpoint", "")
                if not endpoint.startswith(AUTH + "/"):
                    raise RuntimeError("Unknown revocation endpoint")
                requests.post(endpoint, data={"token": session["refresh_token"],
                    "token_type_hint": "refresh_token", "client_id": session["client_id"]}, timeout=10)
            except Exception:
                # The user should disconnect via ChatGPT settings if remote revocation was unconfirmed.
                pass
        CREDS_PATH.unlink(missing_ok=True)
    return {"ok": True, "note": "Local credentials cleared. Check ChatGPT Settings for remote access."}

