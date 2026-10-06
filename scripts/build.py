"""Clocked build: downloads fresh nflverse data and writes index.html.

Run from the repo root:  python3 scripts/build.py
Env vars:
  SITE_URL   link used in share posts (default https://playclocked.com)
  CACHE_DIR  where raw data is downloaded (default data/)

Data sources (all public, from nflverse, built on Pro Football Reference):
  draft_picks.csv   career totals, Pro Bowls, All-Pro, HOF, college, draft slot
  players.csv       ESPN ids + headshot links
  roster_YYYY.csv   who is on a roster this season; team history before 1999
  stats_player_week_YYYY.csv  game logs 1999+: teams actually played for,
                    and career top-up for games newer than the PFR snapshot
  games.csv         schedule + scores for the Last Week mode
"""
import base64, json, os, sys, urllib.request
from collections import Counter
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get('CACHE_DIR', os.path.join(ROOT, 'data'))
SITE_URL = os.environ.get('SITE_URL', 'https://playclocked.com')
os.makedirs(CACHE, exist_ok=True)
REL = 'https://github.com/nflverse/nflverse-data/releases/download/'
RAW = 'https://raw.githubusercontent.com/'

def fetch(url, name, refresh=False):
    p = os.path.join(CACHE, name)
    if refresh or not os.path.exists(p):
        print('  downloading', name)
        urllib.request.urlretrieve(url, p)
    return p

def log(*a): print(*a, flush=True)

# ---------- 1. download ----------
log('1/6 downloading data')
games = pd.read_csv(fetch(RAW + 'nflverse/nfldata/master/data/games.csv', 'games.csv', True))
played = games[games.home_score.notna() & (games.game_type == 'REG')]
SEASON = int(played.season.max())
d = pd.read_csv(fetch(REL + 'draft_picks/draft_picks.csv', 'draft_picks.csv', True))
pl = pd.read_csv(fetch(REL + 'players/players.csv', 'players.csv', True), low_memory=False)
colors = pd.read_csv(fetch(RAW + 'nflverse/nflverse-pbp/master/teams_colors_logos.csv', 'colors.csv', True)).set_index('team_abbr')
rost = []
for y in range(1980, 1999):
    rost.append(pd.read_csv(fetch(f'{REL}rosters/roster_{y}.csv', f'roster_{y}.csv'), low_memory=False,
                            usecols=['season', 'team', 'status', 'gsis_id', 'esb_id']))
r_old = pd.concat(rost)
r_now = pd.read_csv(fetch(f'{REL}rosters/roster_{SEASON}.csv', f'roster_{SEASON}.csv', True), low_memory=False)
SCOLS = ['player_id', 'player_display_name', 'position', 'position_group', 'headshot_url', 'season', 'week', 'season_type',
         'game_id', 'team', 'opponent_team', 'completions', 'attempts', 'passing_yards', 'passing_tds', 'passing_interceptions',
         'carries', 'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards', 'receiving_tds',
         'def_tackles_solo', 'def_tackle_assists', 'def_sacks', 'def_interceptions', 'def_pass_defended', 'def_fumbles_forced']
logs = []
for y in range(1999, SEASON + 1):
    f = fetch(f'{REL}stats_player/stats_player_week_{y}.csv', f'stats_week_{y}.csv', refresh=(y >= SEASON - 1))
    logs.append(pd.read_csv(f, low_memory=False, usecols=lambda c: c in SCOLS))
ps_all = pd.concat(logs)
ps = ps_all[ps_all.season_type == 'REG']
WEEK = int(ps[ps.season == SEASON].week.max()) if (ps.season == SEASON).any() else 0
log(f'   season {SEASON}, game logs through week {WEEK}')

# ---------- 2. find which week PFR's career totals run through ----------
log('2/6 matching PFR totals to game logs')
cur = ps[ps.season == SEASON]
prior = ps[ps.season < SEASON].groupby('player_id')[['rushing_yards', 'receiving_yards', 'passing_yards']].sum()
act_d = d[(d.to >= SEASON) & d.gsis_id.isin(prior.index)].set_index('gsis_id')
best, best_w = -1, 0
for w in range(0, WEEK + 1):
    upto = cur[cur.week <= w].groupby('player_id')[['rushing_yards', 'receiving_yards', 'passing_yards']].sum()
    tot = prior.add(upto, fill_value=0).reindex(act_d.index).fillna(0)
    m = sum(((act_d['rush_yards'].fillna(0) - tot.rushing_yards).abs() < 1) &
            ((act_d['rec_yards'].fillna(0) - tot.receiving_yards).abs() < 1) &
            ((act_d['pass_yards'].fillna(0) - tot.passing_yards).abs() < 1))
    if m > best: best, best_w = m, w
PFR_WEEK = best_w
log(f'   PFR totals match game logs through week {PFR_WEEK} ({best}/{len(act_d)} players exact)')
if len(act_d) and best / len(act_d) < 0.9:
    sys.exit('STOP: PFR totals and game logs disagree for >10% of players. Not publishing possibly wrong stats.')

# ---------- 3. helpers ----------
def team(c, y):
    if c in ('ARI', 'ARZ', 'PHO', 'STL', 'SL') and (c not in ('STL', 'SL') or y <= 1987):
        return 'St. Louis Cardinals' if y <= 1987 else 'Phoenix Cardinals' if y <= 1993 else 'Arizona Cardinals'
    if c in ('STL', 'SL', 'RAM', 'LA', 'LAR'): return 'St. Louis Rams' if 1995 <= y <= 2015 else 'Los Angeles Rams'
    if c in ('RAI', 'OAK', 'LV', 'LVR'): return 'Los Angeles Raiders' if 1982 <= y <= 1994 else 'Las Vegas Raiders' if y >= 2020 else 'Oakland Raiders'
    if c in ('BAL', 'BLT'): return 'Baltimore Colts' if y <= 1983 else 'Baltimore Ravens'
    if c in ('CLE', 'CLV'): return 'Cleveland Browns'
    if c in ('HOU', 'HST'): return 'Houston Oilers' if y <= 1996 else 'Houston Texans'
    if c == 'TEN': return 'Tennessee Oilers' if y <= 1998 else 'Tennessee Titans'
    if c == 'IND': return 'Indianapolis Colts'
    if c in ('SD', 'SDG', 'LAC'): return 'San Diego Chargers' if y <= 2016 else 'Los Angeles Chargers'
    return {'ATL': 'Atlanta Falcons', 'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears', 'CIN': 'Cincinnati Bengals',
            'DAL': 'Dallas Cowboys', 'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers', 'GNB': 'Green Bay Packers',
            'JAX': 'Jacksonville Jaguars', 'KC': 'Kansas City Chiefs', 'KAN': 'Kansas City Chiefs', 'MIA': 'Miami Dolphins',
            'MIN': 'Minnesota Vikings', 'NE': 'New England Patriots', 'NWE': 'New England Patriots', 'NO': 'New Orleans Saints',
            'NOR': 'New Orleans Saints', 'NYG': 'New York Giants', 'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles',
            'PIT': 'Pittsburgh Steelers', 'SEA': 'Seattle Seahawks', 'SF': 'San Francisco 49ers', 'SFO': 'San Francisco 49ers',
            'TB': 'Tampa Bay Buccaneers', 'TAM': 'Tampa Bay Buccaneers', 'WAS': 'Washington'}[c]

LOGO = {'Arizona Cardinals': 'ARI', 'Phoenix Cardinals': 'ARI', 'St. Louis Cardinals': 'ARI', 'Atlanta Falcons': 'ATL',
        'Baltimore Ravens': 'BAL', 'Baltimore Colts': 'IND', 'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR',
        'Chicago Bears': 'CHI', 'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
        'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB', 'Houston Texans': 'HOU',
        'Houston Oilers': 'TEN', 'Tennessee Oilers': 'TEN', 'Tennessee Titans': 'TEN', 'Indianapolis Colts': 'IND',
        'Jacksonville Jaguars': 'JAX', 'Kansas City Chiefs': 'KC', 'Los Angeles Rams': 'LA', 'St. Louis Rams': 'LA',
        'Los Angeles Chargers': 'LAC', 'San Diego Chargers': 'LAC', 'Las Vegas Raiders': 'LV', 'Oakland Raiders': 'LV',
        'Los Angeles Raiders': 'LV', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN', 'New England Patriots': 'NE',
        'New Orleans Saints': 'NO', 'New York Giants': 'NYG', 'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI',
        'Pittsburgh Steelers': 'PIT', 'Seattle Seahawks': 'SEA', 'San Francisco 49ers': 'SF', 'Tampa Bay Buccaneers': 'TB',
        'Washington': 'WAS'}
SVGNAME = {'LA': 'lar'}
POS = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE', 'DE': 'DL', 'DT': 'DL', 'NT': 'DL', 'DL': 'DL', 'LB': 'LB',
       'OLB': 'LB', 'ILB': 'LB', 'MLB': 'LB', 'DB': 'DB', 'CB': 'DB', 'S': 'DB', 'SS': 'DB', 'FS': 'DB', 'SAF': 'DB'}

# ---------- 4. logos ----------
log('3/6 logos')
logos = {}
for k in sorted(set(LOGO.values())):
    custom = [os.path.join(ROOT, 'logos', k + ext) for ext in ('.svg', '.png')]
    custom = [c for c in custom if os.path.exists(c)]
    if custom:
        f = custom[0]
    else:
        f = os.path.join(ROOT, 'build', 'logos', SVGNAME.get(k, k.lower()) + '.svg')
    mime = 'image/png' if f.endswith('.png') else 'image/svg+xml'
    logos[k] = {'img': f'data:{mime};base64,' + base64.b64encode(open(f, 'rb').read()).decode(),
                'c1': colors.loc[k, 'team_color'], 'c2': colors.loc[k, 'team_color2']}

# ---------- 5. players ----------
log('4/6 players')
old = r_old[r_old.status.isin(['ACT', 'RES', 'PUP', 'INA'])][['season', 'team', 'gsis_id', 'esb_id']].assign(week=0)
new = ps.rename(columns={'player_id': 'gsis_id'}).assign(esb_id=None)[['season', 'team', 'gsis_id', 'esb_id', 'week']]
RR = pd.concat([old, new]); RR['key'] = RR.gsis_id
RR = pd.concat([RR, RR[RR.esb_id.notna()].assign(key=lambda z: z.esb_id)]).drop_duplicates(['key', 'season', 'week', 'team']).sort_values(['season', 'week'])
G = {k: v for k, v in RR.groupby('key')}

def teams(g):
    x = G.get(g); out = []
    if x is None: return out
    for row in x.itertuples():
        if pd.isna(row.team): continue
        t = team(row.team, row.season)
        if out and out[-1][0] == t: out[-1][2] = int(row.season)
        else: out.append([t, int(row.season), int(row.season)])
    return out

LATE_COLS = ['passing_yards', 'passing_tds', 'passing_interceptions', 'rushing_yards', 'rushing_tds', 'receptions',
             'receiving_yards', 'receiving_tds', 'def_sacks', 'def_interceptions']
late_df = ps[(ps.season == SEASON) & (ps.week > PFR_WEEK)]
late = late_df.groupby('player_id')[LATE_COLS].sum()
LATEG = late_df.groupby('player_id').size().to_dict()

def num(v): return int(round(v)) if float(v).is_integer() else round(float(v), 1)
def stats(p):
    def S(f, lf):
        v = 0 if pd.isna(p[f]) else p[f]
        if p.gsis_id in late.index: v += late.loc[p.gsis_id, lf]
        return num(v)
    g = POS[p.position]
    if g == 'QB': return [['Pass Yds', S('pass_yards', 'passing_yards')], ['Pass TD', S('pass_tds', 'passing_tds')], ['INT', S('pass_ints', 'passing_interceptions')], ['Rush Yds', S('rush_yards', 'rushing_yards')]]
    if g == 'RB': return [['Rush Yds', S('rush_yards', 'rushing_yards')], ['Rush TD', S('rush_tds', 'rushing_tds')], ['Rec', S('receptions', 'receptions')], ['Rec Yds', S('rec_yards', 'receiving_yards')]]
    if g in ('WR', 'TE'): return [['Rec', S('receptions', 'receptions')], ['Rec Yds', S('rec_yards', 'receiving_yards')], ['Rec TD', S('rec_tds', 'receiving_tds')]]
    if g == 'DB': return [['INT', S('def_ints', 'def_interceptions')], ['Sacks', S('def_sacks', 'def_sacks')]]
    return [['Sacks', S('def_sacks', 'def_sacks')], ['INT', S('def_ints', 'def_interceptions')]]

actr = r_now[r_now.status.isin(['ACT', 'RES', 'INA'])]
ACTIVE = dict(zip(actr.gsis_id, actr.team)); HSNOW = dict(zip(actr.gsis_id, actr.headshot_url))
ESPN = {g: int(e) for g, e in zip(pl.gsis_id, pl.espn_id) if pd.notna(e)}
HS = {g: h for g, h in zip(pl.gsis_id, pl.headshot) if isinstance(h, str)}
lastgame = ps.groupby('player_id').season.max().to_dict()

dd = d[d.position.isin(POS) & d.gsis_id.notna()].drop_duplicates('gsis_id')
allp, act_ids, ret_ids = [], [], []
for _, p in dd.iterrows():
    tm = teams(p.gsis_id)
    if not tm: continue
    g = p.gsis_id; active = g in ACTIVE
    gp = (0 if pd.isna(p.games) else int(p.games)) + LATEG.get(g, 0)
    if gp < 16 and not active: continue
    if active:
        curt = team(ACTIVE[g], SEASON)
        if tm[-1][0] != curt: tm.append([curt, SEASON, SEASON])
        logo_team = curt
    else:
        span = Counter()
        for t in tm: span[t[0]] += t[2] - t[1] + 1
        logo_team = span.most_common(1)[0][0]
    hs = HSNOW.get(g) if active else HS.get(g)
    rec = dict(id=g, name=p.pfr_player_name, pos=p.position, pg=POS[p.position], active=active,
               yrs=[min(t[1] for t in tm), SEASON if active else max(t[2] for t in tm)], games=gp, college=p.college,
               draft=[int(p.season), int(p['round']), int(p.pick), team(p.team, p.season)], pb=int(p.probowls), ap=int(p.allpro),
               hof=bool(p.hof), stats=stats(p), teams=tm, logo=LOGO[logo_team], pfr=p.pfr_player_id, espn=ESPN.get(g),
               hs=hs if isinstance(hs, str) else None)
    allp.append(rec)
    if active and (p.probowls >= 1 or p.allpro >= 1): act_ids.append(g)
    if (not active) and rec['yrs'][1] <= SEASON - 2 and gp >= 40 and (p.probowls >= 1 or p.hof): ret_ids.append(g)
cnt = Counter(a['name'] for a in allp)
for a in allp:
    a['label'] = a['name'] + (f" ({a['pos']}, {a['yrs'][0]}-{'now' if a['active'] else a['yrs'][1]})" if cnt[a['name']] > 1 else '')
log(f'   {len(allp)} players, {len(act_ids)} active pool, {len(ret_ids)} retired pool')

# ---------- 6. last week ----------
log('5/6 last week')
reg = games[games.game_type == 'REG']
wk = reg.groupby(['season', 'week']).apply(lambda x: x.home_score.notna().mean(), include_groups=False)
done_weeks = wk[wk >= 0.5]
WS, WW = [int(v) for v in done_weeks.index.max()]
G2 = {row.game_id: row for row in reg[(reg.season == WS) & (reg.week == WW)].itertuples()}
wkdf = ps_all[(ps_all.season == WS) & (ps_all.week == WW) & (ps_all.season_type == 'REG')]
season_logs = ps[ps.season == WS]
pl_i = pl.drop_duplicates('gsis_id').set_index('gsis_id'); d_i = d.drop_duplicates('gsis_id').set_index('gsis_id')
rn_i = r_now.drop_duplicates('gsis_id').set_index('gsis_id')
f = lambda v: 0 if pd.isna(v) else v
lines = []
for p in wkdf.itertuples():
    gm = G2.get(p.game_id)
    if gm is None or pd.isna(gm.home_score): continue
    pos, pg = p.position, (p.position_group if isinstance(p.position_group, str) else '')
    py, ptd, pin = f(p.passing_yards), f(p.passing_tds), f(p.passing_interceptions)
    ry, rtd, car = f(p.rushing_yards), f(p.rushing_tds), f(p.carries)
    rc, tg, rcy, rctd = f(p.receptions), f(p.targets), f(p.receiving_yards), f(p.receiving_tds)
    sk, di, tk = f(p.def_sacks), f(p.def_interceptions), f(p.def_tackles_solo) + f(p.def_tackle_assists)
    L = []; why = 0
    if pos == 'QB' and (py >= 250 or ptd >= 3):
        L = [f"{int(f(p.completions))}/{int(f(p.attempts))}", f"{int(py)} pass yds", f"{int(ptd)} TD", f"{int(pin)} INT"] + ([f"{int(ry)} rush yds"] if ry >= 20 or rtd else []) + ([f"{int(rtd)} rush TD"] if rtd else []); why = py + ptd * 40
    elif pos in ('RB', 'FB') and (ry >= 80 or rtd >= 2 or ry + rcy >= 120):
        L = [f"{int(car)} car", f"{int(ry)} rush yds", f"{int(rtd)} TD"] + ([f"{int(rc)} rec", f"{int(rcy)} rec yds"] if rc else []) + ([f"{int(rctd)} rec TD"] if rctd else []); why = ry + rcy + 60 * (rtd + rctd)
    elif pos in ('WR', 'TE') and (rcy >= 80 or rctd >= 2):
        L = [f"{int(rc)} rec", f"{int(rcy)} yds", f"{int(rctd)} TD", f"{int(tg)} targets"] + ([f"{int(ry)} rush yds"] if ry >= 15 else []); why = rcy + 60 * rctd
    elif pg in ('DL', 'LB', 'DB') and (sk >= 1.5 or di >= 1 or (sk >= 1 and tk >= 7)):
        L = [f"{tk:g} tackles", f"{sk:g} sacks"] + ([f"{int(di)} INT"] if di else []) + ([f"{int(f(p.def_pass_defended))} PD"] if f(p.def_pass_defended) else []) + ([f"{int(f(p.def_fumbles_forced))} FF"] if f(p.def_fumbles_forced) else []); why = sk * 50 + di * 70 + tk * 3
    if not L or p.team not in logos or p.opponent_team not in logos: continue
    home = p.team == gm.home_team
    us, them = (gm.home_score, gm.away_score) if home else (gm.away_score, gm.home_score)
    gid = p.player_id
    sl = season_logs[season_logs.player_id == gid]
    if pos == 'QB': st = [['Pass Yds', sl.passing_yards.sum()], ['Pass TD', sl.passing_tds.sum()], ['INT', sl.passing_interceptions.sum()]]
    elif pos in ('RB', 'FB'): st = [['Rush Yds', sl.rushing_yards.sum()], ['Rush TD', sl.rushing_tds.sum()], ['Rec Yds', sl.receiving_yards.sum()]]
    elif pos in ('WR', 'TE'): st = [['Rec', sl.receptions.sum()], ['Rec Yds', sl.receiving_yards.sum()], ['Rec TD', sl.receiving_tds.sum()]]
    else: st = [['Tackles', (sl.def_tackles_solo.fillna(0) + sl.def_tackle_assists.fillna(0)).sum()], ['Sacks', sl.def_sacks.sum()], ['INT', sl.def_interceptions.sum()]]
    st = [[a, num(b)] for a, b in st]
    info = pl_i.loc[gid] if gid in pl_i.index else None
    dr = d_i.loc[gid] if gid in d_i.index else None
    draft = [int(dr.season), int(dr['round']), int(dr.pick)] if dr is not None else None
    college = info.college_name if info is not None and isinstance(info.college_name, str) else (dr.college if dr is not None else '')
    rookie = int(info.rookie_season) if info is not None and pd.notna(info.rookie_season) else (draft[0] if draft else None)
    hs = rn_i.loc[gid].headshot_url if gid in rn_i.index else p.headshot_url
    lines.append(dict(id=gid, name=p.player_display_name, pos=pos, pg=POS.get(pos, pos), logo=p.team, team=p.team, opp=p.opponent_team,
                      home=bool(home), score=[int(us), int(them)], line=L, score_key=float(why), season=st, college=college,
                      draft=draft, rookie=rookie, hs=hs if isinstance(hs, str) else None,
                      espn=(int(info.espn_id) if info is not None and pd.notna(info.espn_id) else None)))
log(f'   {WS} week {WW}: {len(lines)} notable lines')

# ---------- 7. write page ----------
log('6/6 writing index.html')
keep = set(act_ids) | set(ret_ids)
A = [{k: p[k] for k in ['id', 'name', 'pos', 'pg', 'active', 'yrs', 'games', 'college', 'draft', 'pb', 'ap', 'hof', 'stats', 'teams', 'logo', 'pfr', 'espn', 'hs']} for p in allp if p['id'] in keep]
Lst = [[p['id'], p['label'], p['pg'], p['yrs'][0], p['pb'], p['logo'], 1 if p['active'] else 0] for p in allp]
have = {x[0] for x in Lst}
for x in lines:
    if x['id'] not in have:
        Lst.append([x['id'], x['name'], x['pg'], x['rookie'] or WS, 0, x['team'], 1]); have.add(x['id'])
DATA = {'A': A, 'L': Lst, 'act': act_ids, 'ret': ret_ids, 'logos': logos, 'week': WEEK, 'season': SEASON, 'W': {'week': WW, 'season': WS, 'lines': lines}}
tpl = open(os.path.join(ROOT, 'src', 'template.html'), encoding='utf-8').read()
html = tpl.replace('/*DATA*/null', json.dumps(DATA, separators=(',', ':'))).replace('__SITE_URL__', SITE_URL)
open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(html)
log(f'done: index.html ({len(html) // 1024} KB), stats through {SEASON} week {WEEK}')

# ---------- 8. creator studio (unlinked page: any player, any graphic) ----------
stpl = os.path.join(ROOT, 'src', 'studio.html')
if os.path.exists(stpl):
    SP = [{k: p[k] for k in ['name', 'label', 'pos', 'active', 'yrs', 'games', 'pb', 'ap', 'hof', 'stats', 'logo']} for p in allp]
    SDATA = {'P': SP, 'logos': logos, 'W': {'week': WW, 'season': WS, 'lines': [{k: x[k] for k in ['name', 'pos', 'team', 'opp', 'home', 'score', 'line', 'score_key']} for x in lines]}}
    shtml = open(stpl, encoding='utf-8').read().replace('/*DATA*/null', json.dumps(SDATA, separators=(',', ':'))).replace('__SITE_URL__', SITE_URL)
    open(os.path.join(ROOT, 'studio.html'), 'w', encoding='utf-8').write(shtml)
    log(f'done: studio.html ({len(shtml) // 1024} KB)')
