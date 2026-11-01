#!/usr/bin/env python3
"""Builds assets/stats/telemetry.svg and assets/stats/languages.svg from GitHub data.

Runs inside GitHub Actions (GITHUB_TOKEN is provided automatically).
Run locally with DEMO=1 to render sample data, or PLACEHOLDER=1 for the empty state.
"""
import datetime as dt
import json
import os
import urllib.request

USER = os.environ.get('GH_USER', 'kunalkushwaha-tech')
TOKEN = os.environ.get('GITHUB_TOKEN', '')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get('OUT_DIR', os.path.join(ROOT, 'assets', 'stats'))

BG = '#09090b'; PANEL = '#18181b'; LINE = '#27272a'; TXT = '#f4f4f5'
MUT = '#a1a1aa'; SOFT = '#d4d4d8'; DIM = '#71717a'; GOLD = '#c5a059'

CSS = """
.m{font-family:'JetBrains Mono','Fira Code',SFMono-Regular,Consolas,'Courier New',monospace}
.tag{font-size:10px;letter-spacing:2px;fill:#71717a}
.t{font-size:12px;fill:#a1a1aa}
.s{font-size:12px;fill:#d4d4d8}
.val{font-size:14px;font-weight:700;fill:#c5a059}
.big{font-size:30px;font-weight:700;fill:#c5a059}
.gold{fill:#c5a059}
"""

QUERY = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    repositories(first:100, ownerAffiliations:[OWNER], isFork:false, privacy:PUBLIC){
      totalCount
      nodes{
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}){
          edges{ size node{ name color } }
        }
      }
    }
    contributionsCollection{
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}
"""


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def fetch():
    body = json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode()
    req = urllib.request.Request(
        'https://api.github.com/graphql', data=body,
        headers={'Authorization': 'bearer ' + TOKEN, 'Content-Type': 'application/json',
                 'User-Agent': 'profile-telemetry'})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get('errors'):
        raise SystemExit(json.dumps(payload['errors']))
    return payload['data']['user']


def crunch(u):
    cc = u['contributionsCollection']
    cal = cc['contributionCalendar']
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    days = sorted((d['date'], d['contributionCount'])
                  for w in cal['weeks'] for d in w['contributionDays'])
    days = [(d, c) for d, c in days if d <= today]
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:  # today may not have activity yet
        i -= 1
    current = 0
    while i >= 0 and days[i][1] > 0:
        current += 1
        i -= 1
    weekly = [sum(d['contributionCount'] for d in w['contributionDays']) for w in cal['weeks']][-52:]
    repos = u['repositories']['nodes']
    langs = {}
    for r in repos:
        for e in r['languages']['edges']:
            n = e['node']['name']
            langs.setdefault(n, [0, e['node']['color'] or '#71717a'])
            langs[n][0] += e['size']
    total = sum(v[0] for v in langs.values()) or 1
    top = sorted(((n, v[0] / total * 100, v[1]) for n, v in langs.items()),
                 key=lambda x: -x[1])[:8]
    return {
        'rows': [
            ('Commits (last 12 months)', cc['totalCommitContributions']),
            ('Pull requests', cc['totalPullRequestContributions']),
            ('Issues opened', cc['totalIssueContributions']),
            ('Public repositories', u['repositories']['totalCount']),
            ('Stars earned', sum(r['stargazerCount'] for r in repos)),
            ('Followers', u['followers']['totalCount']),
        ],
        'total': cal['totalContributions'], 'current': current, 'longest': longest,
        'weekly': weekly, 'langs': top,
    }


def doc(w, h, label, body):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-label="%s">\n'
        '<defs><pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="1" fill="#ffffff" opacity=".025"/></pattern></defs>\n'
        '<style>%s</style>\n'
        '<rect width="%d" height="%d" rx="12" fill="%s"/><rect width="%d" height="%d" rx="12" fill="url(#scan)"/>\n%s\n'
        '<rect x=".5" y=".5" width="%d" height="%d" rx="12" fill="none" stroke="%s"/>\n</svg>\n'
        % (w, h, w, h, esc(label), CSS, w, h, BG, w, h, body, w - 1, h - 1, LINE))


def corners(x, y, w, h, s=9):
    d = ('M%s %sV%sH%s M%s %sH%sV%s M%s %sV%sH%s M%s %sH%sV%s'
         % (x, y + s, y, x + s, x + w - s, y, x + w, y + s,
            x + w, y + h - s, y + h, x + w - s, x + s, y + h, x, y + h - s))
    return '<path d="%s" fill="none" stroke="%s" stroke-width="1.5" opacity=".85"/>' % (d, GOLD)


def card(x, y, w, h):
    return ('<rect x="%s" y="%s" width="%s" height="%s" rx="8" fill="%s" stroke="%s"/>%s'
            % (x, y, w, h, PANEL, LINE, corners(x, y, w, h)))


def txt(x, y, s, cls, anchor=None):
    a = ' text-anchor="%s"' % anchor if anchor else ''
    return '<text x="%s" y="%s" class="m %s"%s>%s</text>' % (x, y, cls, a, esc(s))


def fmt(v):
    return '—' if v is None else '{:,}'.format(v)


def telemetry_svg(d):
    rows = d['rows'] if d else [(l, None) for l in (
        'Commits (last 12 months)', 'Pull requests', 'Issues opened',
        'Public repositories', 'Stars earned', 'Followers')]
    b = txt(14, 30, 'SURVEILLANCE TELEMETRY  //  ' + USER.upper(), 'tag gold')
    b += card(14, 46, 480, 206)
    b += txt(34, 76, 'COMMIT TELEMETRY', 'tag gold')
    for j, (label, val) in enumerate(rows):
        y = 108 + j * 26
        b += txt(34, y, label, 't')
        b += txt(474, y, fmt(val), 'val', 'end')
    b += card(506, 46, 480, 206)
    b += txt(526, 76, 'ACTIVITY STREAK', 'tag gold')
    stats = [('CONTRIBUTIONS', d['total'] if d else None),
             ('CURRENT STREAK', d['current'] if d else None),
             ('LONGEST STREAK', d['longest'] if d else None)]
    for k, (label, val) in enumerate(stats):
        x = 526 + k * 150
        b += txt(x, 118, fmt(val), 'big')
        b += txt(x, 138, label, 'tag')
    b += txt(526, 170, 'WEEKLY ACTIVITY (LAST 52 WEEKS)', 'tag')
    weekly = d['weekly'] if d else [0] * 52
    mx = max(weekly) or 1
    for i, v in enumerate(weekly):
        hgt = max(2, round(v / mx * 44)) if v else 2
        op = '1' if v else '.25'
        b += ('<rect x="%.1f" y="%d" width="7" height="%d" rx="1.5" fill="%s" opacity="%s"/>'
              % (526 + i * 8.5, 238 - hgt, hgt, GOLD, op))
    return doc(1000, 266, 'GitHub telemetry for ' + USER, b)


def languages_svg(d):
    b = txt(14, 30, 'LANGUAGE DISTRIBUTION  //  PUBLIC REPOSITORIES', 'tag gold')
    b += card(14, 46, 972, 170)
    langs = d['langs'] if d else []
    if not langs:
        b += txt(34, 110, 'Awaiting first update. The Actions workflow fills this in.', 's')
        return doc(1000, 232, 'Language distribution', b)
    x = 34.0
    width = 932.0
    for n, pct, color in langs:
        w = max(2.0, width * pct / 100.0)
        b += '<rect x="%.1f" y="76" width="%.1f" height="14" fill="%s" opacity=".9"/>' % (x, w, color)
        x += w
    b += '<rect x="34" y="76" width="932" height="14" rx="4" fill="none" stroke="%s"/>' % LINE
    for i, (n, pct, color) in enumerate(langs):
        col, row = i % 4, i // 4
        cx = 34 + col * 236
        cy = 126 + row * 34
        b += '<circle cx="%d" cy="%d" r="5" fill="%s"/>' % (cx + 5, cy - 4, color)
        b += txt(cx + 18, cy, n, 's')
        b += txt(cx + 210, cy, '%.1f%%' % pct, 't', 'end')
    return doc(1000, 232, 'Language distribution across public repositories', b)


DEMO = {
    'rows': [('Commits (last 12 months)', 412), ('Pull requests', 9), ('Issues opened', 3),
             ('Public repositories', 14), ('Stars earned', 7), ('Followers', 21)],
    'total': 530, 'current': 6, 'longest': 19,
    'weekly': [0, 2, 5, 9, 0, 3, 14, 22, 8, 0, 1, 4, 6, 12, 18, 7, 0, 0, 3, 9, 15, 11, 5, 2, 0, 8, 13, 19, 6, 4,
               0, 1, 7, 10, 16, 21, 9, 3, 0, 2, 6, 12, 8, 5, 1, 0, 4, 9, 14, 17, 10, 6],
    'langs': [('Python', 46.2, '#3572A5'), ('HTML', 18.4, '#e34c26'), ('JavaScript', 12.1, '#f1e05a'),
              ('C', 8.3, '#555555'), ('TypeScript', 6.0, '#3178c6'), ('Shell', 4.0, '#89e051'),
              ('CSS', 3.2, '#563d7c'), ('C++', 1.8, '#f34b7d')],
}


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.environ.get('PLACEHOLDER'):
        data = None
    elif os.environ.get('DEMO'):
        data = DEMO
    else:
        data = crunch(fetch())
    with open(os.path.join(OUT, 'telemetry.svg'), 'w', encoding='utf-8') as f:
        f.write(telemetry_svg(data))
    with open(os.path.join(OUT, 'languages.svg'), 'w', encoding='utf-8') as f:
        f.write(languages_svg(data))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
