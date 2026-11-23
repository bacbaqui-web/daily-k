"""Capture every displayed entry, including metrics and unspecified languages."""
from collect import parse_ranking

def article(n, language=True):
    return f'''<article><h2><a href="/owner/repo{n}">repo</a></h2>
    <a href="/owner/repo{n}/stargazers"><svg></svg>12,345</a>
    <a href="/owner/repo{n}/forks">678</a>
    {"<span itemprop='programmingLanguage'>Python</span>".replace("'", chr(34)) if language else ""}
    <span>1,234 stars today</span></article>'''

for count in [7, 16, 25, 31]:
    parsed = parse_ranking(''.join(article(n, n != count) for n in range(1, count+1)))
    assert len(parsed) == count
    assert parsed[-1]['rank'] == count and parsed[-1]['language'] is None
    assert parsed[0]['language'] == 'Python'
    assert (parsed[0]['starsToday'], parsed[0]['starsTotal'], parsed[0]['forks']) == (1234, 12345, 678)
for invalid in ['', article(1)+article(1), article(1).replace('/forks', '/missing'), '<article>broken</article>', article(1) + '<article>']:
    try:
        parse_ranking(invalid)
    except ValueError:
        continue
    raise AssertionError('Incomplete or duplicate capture must fail')
print('GitHub collector: variable counts, full metrics, missing language and invalid captures verified')
