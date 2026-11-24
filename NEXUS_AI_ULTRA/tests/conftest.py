"""Explicit runtime fixture for API contracts that now enter the Hermes main agent.

No substitute planner: these tests require the real installed SDK. Lightweight
backend tests remain independent of Hermes. CI without the runtime reports a skip.
"""
import os
import pytest
from nexus.hermes_agent import HermesAgent
from nexus.hermes_worker import BUILD


@pytest.fixture
def configured_hermes(monkeypatch):
    values=[os.getenv(k) for k in ('HERMES_TEST_PYTHON','HERMES_TEST_ROOT','HERMES_TEST_HOME')]
    if not all(values):pytest.skip('Real Hermes runtime required for main-agent API acceptance')
    config=dict(zip(('python','root','runtime_home'),values),build=BUILD)
    monkeypatch.setattr(HermesAgent,'config',lambda self:config.copy())
    original=HermesAgent.run
    async def run(self,*args,**kwargs):
        try:return await original(self,*args,**kwargs)
        finally:await self.close()
    monkeypatch.setattr(HermesAgent,'run',run)
