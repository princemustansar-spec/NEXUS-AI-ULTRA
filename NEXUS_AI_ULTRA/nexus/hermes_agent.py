"""Hermes main agent; existing NEXUS router and approval runner remain authoritative."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

from .hermes_worker import BUILD, LIMIT

READ_ONLY = {'system_info', 'processes', 'windows', 'list_files', 'search_files',
             'maintenance_report', 'whatsapp_status', 'daily_briefing', 'news_briefing'}


class HermesAgent:
    def __init__(self, base, data, providers, queue_tool, stopped):
        self.base, self.data = Path(base), Path(data)
        self.providers, self.queue_tool, self.stopped = providers, queue_tool, stopped
        self.process = None
        self.stderr_task = None
        self.lock = asyncio.Lock()

    def config(self):
        path = self.base / 'hermes_runtime.json'
        if not path.is_file():
            raise ValueError('Hermes main agent is not configured. Run the NEXUS Hermes installer.')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if value.get('build') != BUILD:
            raise ValueError('Hermes runtime build is not the tested version.')
        for key in ('python', 'root', 'runtime_home'):
            if not isinstance(value.get(key), str) or not Path(value[key]).is_absolute():
                raise ValueError('Invalid local Hermes runtime path')
        if not Path(value['python']).is_file() or not (Path(value['root']) / 'run_agent.py').is_file():
            raise ValueError('Existing Hermes installation is unavailable; no alternative agent was started.')
        return value

    async def _drain_errors(self, stream):
        while await stream.read(8192):
            pass  # Hermes logs can contain private context; do not publish/store them.

    async def close(self):
        process, self.process = self.process, None
        if process and process.returncode is None:
            try:process.terminate()
            except ProcessLookupError:pass
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()
        if self.stderr_task:
            await asyncio.gather(self.stderr_task, return_exceptions=True)
            self.stderr_task = None

    async def _read(self):
        line = await asyncio.wait_for(self.process.stdout.readline(), 150)
        if not line or len(line) > LIMIT:
            raise ValueError('Hermes stopped or returned an oversized frame; actions were not retried.')
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError('Invalid Hermes response')
        return value

    async def _send(self, value):
        line = (json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n').encode()
        if len(line) > LIMIT:
            raise ValueError('Hermes request exceeds the context transport limit')
        self.process.stdin.write(line)
        await self.process.stdin.drain()

    async def _start(self):
        if self.process and self.process.returncode is None:
            return
        await self.close()
        config = self.config()
        # Allow OS/runtime plumbing, not provider secrets or arbitrary Python startup hooks.
        allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP', 'TMP',
                   'HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'LANG', 'LC_ALL'}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        self.process = await asyncio.create_subprocess_exec(config['python'], '-I', '-u',
            str(self.base / 'nexus' / 'hermes_worker.py'), '--root', config['root'],
            '--runtime-home', config['runtime_home'], '--profile', str(self.data / 'hermes-profile'),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env, cwd=self.base, limit=LIMIT + 1,
            **({'creationflags': 0x08000000} if sys.platform == 'win32' else {}))
        self.stderr_task = asyncio.create_task(self._drain_errors(self.process.stderr))
        ready = await self._read()
        if ready.get('type') != 'ready' or ready.get('build') != BUILD:
            raise ValueError('Hermes compatibility probe failed; task not started.')

    def _journal(self, task_id, ledger):
        folder = self.data / 'hermes-tasks'
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination = folder / (task_id + '.json')
        temporary = destination.with_suffix('.tmp')
        # Action fingerprints and receipts stay local; no provider credentials.
        temporary.write_text(json.dumps(ledger, ensure_ascii=True, default=str), encoding='utf-8')
        temporary.replace(destination)

    async def _tool(self, frame, allowed, task_id, ledger):
        name, args = frame.get('name'), frame.get('args')
        if name not in allowed or not isinstance(args, dict):
            return dict(error='Unknown or invalid NEXUS tool')
        parameters = allowed[name]['function']['parameters']
        if set(args) != set(parameters['properties']) or any(not isinstance(v, str) for v in args.values()):
            return dict(error='Tool arguments do not match the existing NEXUS schema')
        if self.stopped():
            raise ValueError('Emergency Stop active')
        fingerprint = hashlib.sha256(json.dumps([name, args], sort_keys=True).encode()).hexdigest()
        if name not in READ_ONLY and fingerprint in ledger:
            return ledger[fingerprint]['receipt']
        if name not in READ_ONLY:
            ledger[fingerprint] = dict(name=name, receipt={'status': 'unknown',
                'error': 'Action started; do not automatically repeat. Check the existing receipt.'})
            self._journal(task_id, ledger)
        try:
            receipt = await self.queue_tool(name, args)
        except Exception as exc:
            receipt = dict(error=str(exc), retry_automatically=False)
        if name not in READ_ONLY:
            ledger[fingerprint]['receipt'] = receipt
            self._journal(task_id, ledger)
        return receipt

    async def run(self, messages, schemas, allow_paid=False, planned=None):
        async with self.lock:
            task_id, ledger, last, model_calls = secrets.token_hex(16), {}, None, 0
            allowed = {s['function']['name']: s for s in schemas}
            try:
                await self._start()
                await self._send(dict(type='run', task_id=task_id, messages=messages, tools=schemas, planned=planned))
                async with asyncio.timeout(300):
                    while True:
                        if self.stopped():
                            raise ValueError('Emergency Stop active')
                        frame = await self._read()
                        kind = frame.get('type')
                        if kind == 'done':
                            text = frame.get('text')
                            if not isinstance(text, str) or not text.strip() or last is None:
                                raise ValueError('Hermes returned no completed response')
                            return dict(text=text, provider=last[1], model=last[2], agent='Hermes', task_id=task_id)
                        if kind == 'failed':
                            raise ValueError(frame.get('error', 'Hermes failed'))
                        if kind == 'model':
                            model_calls += 1
                            if model_calls > 5:
                                raise ValueError('Task stopped after five Hermes planning steps; actions not replayed.')
                            incoming = frame.get('messages')
                            if not isinstance(incoming, list) or not incoming:
                                raise ValueError('Invalid Hermes model context')
                            # Only the original NEXUS schemas, never Hermes built-ins, reach providers.
                            last = await self.providers.request(incoming, schemas, allow_paid,
                                                                fallback_accounts=True)
                            result = last[0]
                            if len(result.get('tool_calls', [])) > 8:
                                raise ValueError('Provider requested too many tools')
                        elif kind == 'tool':
                            result = await self._tool(frame, allowed, task_id, ledger)
                        else:
                            raise ValueError('Unexpected Hermes protocol frame')
                        await self._send(dict(type='reply', id=frame.get('id'), result=result))
            except BaseException as exc:
                # Never restart/replay a failed task. A fresh explicit user turn is required.
                await asyncio.shield(self.close())
                if isinstance(exc, (TimeoutError, BrokenPipeError, ConnectionError)):
                    raise ValueError('Hermes task interrupted or timed out; completed actions were not replayed.') from None
                raise
