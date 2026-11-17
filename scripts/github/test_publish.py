"""Regression checks against a reviewed edition, always in temporary folders."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from collect import parse_ranking
from publish import publish, digest

def test(state):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / 'site'
        root.mkdir()
        copy = Path(temp) / 'state'
        shutil.copytree(state, copy)
        assert publish(copy, root, check=True)['checked']
        assert list(root.iterdir()) == [], '--check must have no publication side effects'
        publish(copy, root)
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        publish(copy, root)
        assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}, 'Retry must preserve original publication'
        analysis = copy / 'analysis.json'
        changed = json.loads(analysis.read_text())
        changed['items'][0], changed['items'][1] = changed['items'][1], changed['items'][0]
        analysis.write_text(json.dumps(changed))
        try:
            publish(copy, root, check=True)
            raise AssertionError('Changed analysis must invalidate review')
        except ValueError as e:
            assert 'changed after review' in str(e)
        review = copy / 'review.json'
        value = json.loads(review.read_text()); value['analysisSha256'] = digest(analysis); review.write_text(json.dumps(value))
        try:
            publish(copy, root, check=True)
            raise AssertionError('A reordered ranking must fail even with a new review hash')
        except ValueError as e:
            assert 'Ranking/order mismatch' in str(e)
        assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    try:
        parse_ranking('<html>Rate limit exceeded</html>')
        raise AssertionError('A failed collection must never become an empty publication')
    except ValueError:
        pass
    print('GitHub publisher: check is read-only, retry is immutable, tampering/order/collection failures rejected')

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--state', type=Path, required=True)
    test(p.parse_args().state)
