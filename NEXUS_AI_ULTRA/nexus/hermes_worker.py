"""Version-locked Hermes embedding. JSON pipes are its only model/tool transport.

Runs in the EXISTING Hermes Python, never in NEXUS's Python environment.
No installed Hermes source, personal profile or provider configuration is edited.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

BUILD = 'caafe5389ae585ef77387a962aee05b1bcf17029'
LIMIT = 4_000_000


def read_frame(stream):
    line = stream.readline(LIMIT + 1)
    if not line or len(line) > LIMIT or not line.endswith('\n'):
        raise ValueError('Hermes pipe closed or oversized frame')
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError('Invalid Hermes frame')
    return value


def checkout_build(root):
    git = root / '.git'
    head = (git / 'HEAD').read_text(encoding='ascii').strip()
    if head.startswith('ref: '):
        ref = head[5:]
        if not ref.startswith('refs/') or '..' in ref.split('/'):
            raise ValueError('Unsupported Hermes Git reference')
        if (git / ref).is_file():
            head = (git / ref).read_text(encoding='ascii').strip()
        else:
            head = next(line.split()[0] for line in (git / 'packed-refs').read_text().splitlines()
                        if line.endswith(' ' + ref))
    if head != BUILD:
        raise ValueError('Hermes build differs from tested caafe5389ae5; installation unchanged')
    return head


class Pipe:
    def __init__(self, source, target):
        self.source, self.target = source, target
        self.lock = threading.Lock()
        self.serial = 0

    def send(self, value):
        line = json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n'
        if len(line.encode()) > LIMIT:
            raise ValueError('Hermes frame too large')
        self.target.write(line)
        self.target.flush()

    def call(self, kind, **value):
        with self.lock:
            self.serial += 1
            self.send(dict(type=kind, id=self.serial, **value))
            response = read_frame(self.source)
            if response.get('id') != self.serial or response.get('type') != 'reply':
                raise ValueError('Hermes pipe reply mismatch')
            if response.get('error'):
                raise RuntimeError(response['error'])
            return response['result']


def prepare(root, runtime_home, profile):
    checkout_build(root)
    plumbing = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP',
                'HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'LANG', 'LC_ALL',
                'NEXUS_HERMES_TEST_TRACE'}
    for key in list(os.environ):
        if key.upper() not in plumbing:
            del os.environ[key]
    sys.path.insert(0, str(root))
    # PM's read-only composition reuses committed dependencies. Never run pm install/update.
    os.environ['HERMES_HOME'] = str(runtime_home)
    from pm.environments import activation_environment
    activation = activation_environment(root)
    for key, value in activation.items():
        os.environ[key] = value
    for entry in reversed(activation.get('PYTHONPATH', '').split(os.pathsep)):
        if entry and entry not in sys.path:
            sys.path.insert(0, entry)
    os.environ['HERMES_HOME'] = str(profile)
    # Bind before any config/provider/plugin import. This exact build provides this
    # managed-worker seam; a version change requires another compatibility test.
    from agent.safe_worker_policy import _bind_safe_worker_policy
    _bind_safe_worker_policy(safe_mode=True, ignore_user_config=True, config={
        # Virtual route accounting only; NEXUS keeps each provider's actual limits
        # (including its existing Ollama 4096-token setting). No model is loaded here.
        'model': {'streaming': False, 'context_length': 65536},
        'compression': {'enabled': False}, 'memory': {'enabled': False},
        'display': {'streaming': False}, 'agent': {'max_iterations': 5},
        'fallback_models': [], 'toolsets': ['nexus'],
        'tools': {'tool_search': {'enabled': 'off'}},
    })
    # NEXUS owns transport. This is defense in depth, not a claim of OS sandboxing.
    def no_independent_transport(event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'subprocess.Popen', 'os.system'):
            raise PermissionError('NEXUS owns model routing and approved actions')
    sys.addaudithook(no_independent_transport)
    import run_agent
    from openai.types.chat import ChatCompletion
    from tools.registry import registry
    from toolsets import TOOLSETS
    return run_agent.AIAgent, ChatCompletion, registry, TOOLSETS


def make_agent(runtime, pipe, schemas):
    base, completion, registry, toolsets = runtime

    class Client:
        api_key = 'nexus-pipe-no-provider-key'
        base_url = 'http://127.0.0.1/nexus-pipe/v1'
        _custom_headers = {}
        max_retries = 0

        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            if kwargs.get('stream'):
                raise ValueError('Unexpected independent Hermes streaming request')
            result = pipe.call('model', messages=kwargs['messages'], tools=kwargs.get('tools', []))
            return completion(id='nexus-pipe', created=int(time.time()), object='chat.completion',
                              model='nexus-router', choices=[dict(index=0, message=result,
                              finish_reason='tool_calls' if result.get('tool_calls') else 'stop')],
                              usage=dict(prompt_tokens=0, completion_tokens=0, total_tokens=0))

        def close(self):
            return None

        def is_closed(self):
            return False

        def with_options(self, **kwargs):
            return self

    client = Client()

    class NexusHermes(base):
        def _create_openai_client(self, *args, **kwargs):
            return client

        def _build_system_prompt(self, system_message=None):
            # Retain NEXUS identity/memory/instructions, not Hermes's stock persona.
            self._cached_system_prompt_static = system_message or ''
            return system_message or ''

    names = []
    for schema in schemas:
        function = schema['function']
        name = function['name']
        def handler(args, _name=name, **kwargs):
            return json.dumps(pipe.call('tool', name=_name, args=args), default=str)
        # search_files also exists in Hermes. This process must use NEXUS's guarded
        # implementation, never the native filesystem handler with the same name.
        registry.register(name=name, toolset='nexus', schema=function, handler=handler, override=True)
        names.append(name)
    toolsets['nexus'] = dict(name='nexus', description='Existing NEXUS approved tools', tools=names)
    agent = NexusHermes(model='nexus-router', provider='custom', api_mode='chat_completions',
                        base_url=client.base_url, api_key=client.api_key, max_iterations=5,
                        enabled_toolsets=['nexus'], quiet_mode=True, skip_context_files=True,
                        skip_memory=True, skip_background_review=True, fallback_model={},
                        save_trajectories=False, load_soul_identity=False, platform='nexus',
                        run_budget_seconds=240, max_tokens=2048)
    actual = {t['function']['name'] for t in agent.tools}
    if actual != set(names):
        raise ValueError('Hermes tool surface differs: missing=' + repr(sorted(set(names)-actual))
                         + ', extra=' + repr(sorted(actual-set(names))))
    agent._disable_streaming = agent._disable_streaming_seed = True
    return agent


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--runtime-home', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--schemas', type=Path)
    options = parser.parse_args()
    wire = Pipe(sys.stdin, sys.stdout)
    sys.stdout = sys.stderr  # third-party output must never corrupt the protocol
    options.profile.mkdir(parents=True, exist_ok=True)
    try:
        runtime = prepare(options.root.resolve(), options.runtime_home.resolve(), options.profile.resolve())
        if options.probe:
            schemas = json.loads(options.schemas.read_text(encoding='utf-8-sig')) if options.schemas else []
            agent = make_agent(runtime, wire, schemas)
            wire.send(dict(type='ready', build=BUILD, agent='Hermes AIAgent', tools=len(agent.tools)))
            return
        wire.send(dict(type='ready', build=BUILD))
        while True:
            frame = read_frame(wire.source)
            if frame.get('type') != 'run':
                raise ValueError('Invalid Hermes task')
            messages = frame['messages']
            agent = make_agent(runtime, wire, frame['tools'])
            def prelude():
                # Exact legacy commands still execute in the real Hermes turn loop,
                # through its registered NEXUS handlers and the ordinary approvals.
                name, args = frame['planned']
                yield '', name, args
            result = agent.run_conversation(messages[-1]['content'],
                    system_message=messages[0]['content'], conversation_history=messages[1:-1],
                    task_id=frame['task_id'], prelude=prelude() if frame.get('planned') else None)
            if result.get('failed') or result.get('interrupted') or result.get('error'):
                wire.send(dict(type='failed', error='Hermes task did not complete; inspect NEXUS Activity'))
            else:
                wire.send(dict(type='done', text=result.get('final_response', '')))
            agent.close()
    except (Exception, SystemExit) as exc:
        # Do not return profile data, model prompts, environment values or API keys.
        wire.send(dict(type='failed', error='Hermes worker: ' + type(exc).__name__))
        if os.environ.get('NEXUS_HERMES_TEST_TRACE') == '1':
            import traceback
            traceback.print_exc()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
