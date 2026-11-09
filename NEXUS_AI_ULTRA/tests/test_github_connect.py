"""Focused offline checks for GitHub integration; no real OAuth requests."""
import unittest
from unittest.mock import patch
from nexus import github_connect as gh


class GitHubConnectTests(unittest.TestCase):
    def tearDown(self):
        gh.disconnect()

    def test_public_search_uses_no_token(self):
        def fake(url, data=None, token=None):
            self.assertIsNone(token)
            self.assertIn('/search/repositories?', url)
            return {'items':[{'full_name':'example/repo','html_url':'https://github.com/example/repo',
                              'description':'Demo','stargazers_count':3}]}
        with patch.object(gh, '_request', side_effect=fake):
            self.assertEqual(gh.search('python')['results'][0]['name'], 'example/repo')

    def test_empty_search_rejected(self):
        with self.assertRaises(ValueError):
            gh.search('   ')

    def test_device_flow_pending_then_connected(self):
        with patch.object(gh.webbrowser, 'open'):
            with patch.object(gh, '_request', return_value={'device_code':'dev','user_code':'ABCD',
                     'verification_uri':'https://github.com/login/device','expires_in':900,'interval':5}):
                self.assertEqual(gh.start()['user_code'],'ABCD')
        with patch.object(gh, '_request', side_effect=[
            {'error':'authorization_pending'},
            {'access_token':'fake-token'},
            {'login':'example'}
        ]):
            self.assertEqual(gh.check()['status'],'pending')
            gh._session['last_poll'] = 0
            self.assertEqual(gh.check()['user'],'example')
        self.assertTrue(gh.status()['connected'])
        gh.disconnect()
        self.assertFalse(gh.status()['connected'])

    def test_expired_session(self):
        gh._session.update(device_code='old',expires=0)
        self.assertEqual(gh.check()['status'],'expired')


if __name__ == '__main__':
    unittest.main()
