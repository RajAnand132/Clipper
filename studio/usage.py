"""A record of what the AI was used for: one row per call, with the tokens it took.

Nothing is charged for and nothing is limited here. The AI key belongs to whoever runs this server, and their AI
service bills them directly; this is only so they (and each user) can see where the tokens went."""
import threading
import time
from collections import defaultdict

import sqlalchemy as sa

from . import ai, config, ctx, db

_where = threading.local()
_brief: dict = {}    # user -> (when, summary). Dropped the moment they make another AI call.


def set_context(creator=None, where=None):
    """Which creator and video the AI calls on this thread are for, until changed."""
    _where.creator, _where.where = creator, where


def record(tokens_in: int, tokens_out: int, purpose: str, where: str | None = None):
    uid = ctx.uid_or_none()
    if not uid:
        return
    with db.engine.begin() as c:
        c.execute(db.usage.insert().values(user_id=uid, t=time.time(), tokens_in=max(0, int(tokens_in)),
                                           tokens_out=max(0, int(tokens_out)), purpose=purpose[:60],
                                           creator=getattr(_where, "creator", None),
                                           place=(where or getattr(_where, "where", None) or "")[:200]))
    _brief.pop(uid, None)
    ctx.bump(uid)


def studio_call(model, prompt, schema, purpose: str, where: str | None = None, **kw):
    """An AI call made by the AI Studio (story ideas, scripts, characters, titles…), recorded like the clip finder's
    calls: it shows in the sidebar's "today" count and on the AI usage page, with its purpose and the series.
    Returns what ai.call returns."""
    for attempt in range(3):
        try:
            out, sent, wrote = ai.call(model, prompt, schema, **kw)
            break
        except ai.Unreadable as e:     # it answered (the tokens count), but the answer could not be used
            record(e.sent, e.wrote, purpose, where)
            raise
        except Exception as e:  # noqa: BLE001
            # "high demand" (503) or a short per-minute limit passes in seconds: wait a little and ask again.
            # A daily quota does not pass: the caller moves on to the next model straight away.
            busy = "HTTP 503" in str(e) or "HTTP 500" in str(e) or ("HTTP 429" in str(e) and "per day" not in str(e).lower()
                                                                     and "quota" not in str(e).lower())
            if busy and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue
            ai.note_problem(e)         # a quota or a wrong key shows in the sidebar, as for clips
            raise
    record(sent, wrote, purpose, where)
    ai.clear_problem()
    return out, sent, wrote


def forget(uid: str):
    _brief.pop(uid, None)


def forget_all():
    """The AI settings changed: every page should say so on its next look."""
    _brief.clear()


def _day(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def _tokens():
    return db.usage.c.tokens_in + db.usage.c.tokens_out


def brief() -> dict:
    """The few numbers every page shows. Counted at most every ten seconds per user."""
    uid, now = ctx.uid(), time.time()
    got = _brief.get(uid)
    if got and now - got[0] < 10:
        return dict(got[1])
    midnight = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
    u = db.usage.c
    with db.engine.connect() as c:
        today = c.execute(sa.select(sa.func.count(), sa.func.coalesce(sa.func.sum(_tokens()), 0)).where(
            u.user_id == uid, u.t >= midnight)).first()
    out = {"ready": ai.ready(), "provider": ai.label(), "model": (ai.models() or [""])[0],
           "today_calls": int(today[0]), "today_tokens": int(today[1]),
           "problem": ai.problem["text"] if ai.problem["text"] and now - ai.problem["at"] < 6 * 3600 else ""}
    _brief[uid] = (now, out)
    return dict(out)


def summary(creator_names: dict) -> dict:
    """Everything the AI usage page shows, for the signed-in user."""
    uid, now = ctx.uid(), time.time()
    u = db.usage.c
    with db.engine.connect() as c:
        totals = c.execute(sa.select(sa.func.count(), sa.func.coalesce(sa.func.sum(_tokens()), 0)).where(u.user_id == uid)).first()
        by_purpose = [[r[0], int(r[1] or 0), r[2]] for r in c.execute(
            sa.select(u.purpose, sa.func.sum(_tokens()), sa.func.count()).where(u.user_id == uid)
            .group_by(u.purpose).order_by(sa.func.sum(_tokens()).desc()))]
        by_creator = defaultdict(lambda: [0, 0])
        for r in c.execute(sa.select(u.creator, sa.func.sum(_tokens()), sa.func.count()).where(u.user_id == uid).group_by(u.creator)):
            key = creator_names.get(r[0], "No creator") if r[0] else "No creator"
            by_creator[key][0] += int(r[1] or 0)
            by_creator[key][1] += r[2]
        days = [_day(now - 86400 * i) for i in range(29, -1, -1)]
        daily = {d: [0, 0] for d in days}
        for r in c.execute(sa.select(u.t, u.tokens_in, u.tokens_out).where(u.user_id == uid, u.t >= now - 31 * 86400)):
            if _day(r[0]) in daily:
                daily[_day(r[0])][0] += int(r[1]) + int(r[2])
                daily[_day(r[0])][1] += 1
        recent = [{"t": r._mapping["t"], "tokens": int(r.tokens_in) + int(r.tokens_out), "purpose": r.purpose, "where": r.place,
                   "creator_name": creator_names.get(r.creator, "") if r.creator else ""}
                  for r in c.execute(sa.select(db.usage).where(u.user_id == uid).order_by(u.t.desc()).limit(60))]
    return {**brief(), "calls_total": int(totals[0]), "tokens_total": int(totals[1]),
            "daily": [{"day": d, "tokens": daily[d][0], "calls": daily[d][1]} for d in days],
            "by_purpose": by_purpose,
            "by_creator": sorted(([k, v[0], v[1]] for k, v in by_creator.items()), key=lambda x: -x[1]),
            "recent": recent}
