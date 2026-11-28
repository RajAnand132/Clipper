# Engineering Plan 13 — Several AI Keys (a key pool)

> **Plan ID**: `PLAN-13`
> **Status**: **Planned**: keys from separate projects and accounts (section 5b); waiting for "go"
> **Builds on**: the AI page (`studio/ai.py`), AI usage (`studio/usage.py`), the clip finder's model fallback (`studio/brain.py`)
> **Modules**: `studio/ai.py`, `studio/config.py`, `studio/usage.py`, `studio/brain.py`, `studio/server.py`, `web/index.html`
> **Estimated effort**: about 2 days.

---

## 1. How keys are used today (checked in the code)

- **One key only.** The AI page saves one provider, up to 5 models and **one key** in `data/ai.json`
  (`ai.save`). Without that file, `.env` gives one key (`PEAKCUT_AI_KEY` or `PEAKCUT_AI_KEY_FILE`). Right now
  the app uses Gemini, the models `gemini-2.5-flash` then `gemini-3.5-flash-lite`, and 1 key.
- **Every AI call uses that key**: `ai._gemini` sends it as `x-goog-api-key`. The same goes for scripts, ideas,
  characters, titles and briefs (AI Studio), clip picking and captions (`brain.py`), listening to audio
  (`ai.hear`) and looking at pictures (`ai.see`).
- **What happens on a limit (HTTP 429), on "busy" (503) and on a refused key (401/403):**

  | Error | AI Studio (`usage.studio_call`) | Clip finder (`brain.ask`) |
  |---|---|---|
  | **503** "busy" | Waits 4 s, then 8 s, then tries the next model. | Goes straight to the next model. |
  | **429** per minute | Waits and asks again, the same way as 503. | Waits as long as Google asks, then asks again. |
  | **429** per day | Goes straight to the next model. | Same. |
  | **403** key refused | Stops. The sidebar shows the problem. | Stops, and the admins are emailed. |

  When both models are used up for the day, everything AI stops until Google resets the quota (midnight
  Pacific time, which is 13:30 India time).
- **AI usage** records tokens and calls per purpose and per series, not per key.

## 2. Will 10–20 Gemini keys make it faster, or stop the 429s?

- **Faster per call: no.** One answer takes the same time whichever key asks for it. The Studio asks one
  question at a time, so there is nothing to spread out. Time is only saved where today the app **waits** after a
  429.
- **Fewer 429s: only if the keys belong to different Google Cloud projects.** Gemini limits (requests per
  minute, tokens per minute, requests per day) count **per project, not per key**. Ten keys made in one project
  share one quota, so they help **nothing**. Keys from different projects each have their own quota.
- **The rules.** Google's API terms say not to get around usage limits. Making many free projects or accounts
  just to multiply the free quota goes against that and can get the keys or the account blocked. Several keys are
  fine for honest reasons:
  - a **backup** when one key is refused or turned off;
  - separate projects for separate clients or channels (each paying or free for its own use);
  - a **paid key** with a free key in front of it, so the free quota is used first.
- **The real fix for 429s is billing (option A):** turning billing on for the project lifts the limits a lot
  (Tier 1). The cost is in AI usage (tokens), which the app already tracks.

## 3. What to build (the key pool)

1. **Several keys** for the chosen service, each with a name ("Main", "Backup", "Client X").
   - Saved in `ai.json` as `keys: [{id, name, key, added_at}]`. The old single `key` is read as the first one.
   - In `.env`: `PEAKCUT_AI_KEYS=key1,key2` (the old `PEAKCUT_AI_KEY` still works).
   - The key itself never reaches the page; only its last 4 characters, as today.
2. **Choosing a key for each call.** The first key that is fit for this model is used ("fill first"), so the
   order is the owner's choice: free key first, paid key last. Each key and model pair remembers its state:
   - **429 per minute**: rests for as long as Google asked (or 60 s). The **next key** is tried at once, no waiting.
   - **429 per day**: rests until the quota resets (13:30 India time). The next key is used.
   - **401/403**: marked "refused" until it is changed or tested again. The next key is used.
   - **503 busy**: the same as today. It isn't about the key, so the key is not changed.
   - The order is: the best model on every key first, then the cheaper model. The cheaper model is only used
     when all keys are resting for the better one.
2b. **Skip a key before it fails.** Each key counts its own calls per model, per minute and per day. If the owner
   enters a key's limits (or the app learns them from the first 429), a key close to its limit is passed over
   before Google refuses it. Fewer 429s even happen, and none are seen while another key has room.
2c. **No error shown while any key can answer.** The sidebar and the error messages report a problem only when
   every key is resting or refused. They then say when the first key is back ("AI back at 13:30").
3. **Same project? We can tell.** If two keys hit their daily limit within a minute of each other, the AI page
   says: "These keys seem to share one project's quota: they don't add more requests."
4. **AI page.** A list of keys showing:
   - name, last 4 characters, and state (Ready / Resting until 13:30 / Refused);
   - calls and tokens today for each key.

   It also has **Add key**, **Test**, **Move up/down** and **Remove** (asks first).
5. **AI usage page.** A "Key" column. Each call is recorded with the id of the key it used.
6. **Safety.**
   - Every key is hidden in error messages and logs. Today only the one key is hidden: `_fail` replaces
     `key()` with "<key>", and this has to cover all keys.
   - Admins are emailed only when **every** key is refused or used up for the day, not for each key.
7. **Tests** (`tests/test_ai_keys.py`, offline, with a fake service):
   - a 429 moves to the next key without waiting;
   - a daily limit rests the key until the reset;
   - a 403 marks the key refused;
   - the better model is tried on all keys before the cheaper one;
   - all keys are hidden in errors;
   - an old `ai.json` with one key still works;
   - the "same project" warning.

## 4. Not in this plan

- **Running AI calls in parallel** (asking about several scenes at once). It is possible later with real
  separate quotas, but it changes how scripts are written.
- **The production queue** (two episodes of the same series at once). It is a separate decision that is still
  open.

## 5. Phases

| Phase | What | Effort |
|---|---|---|
| **P1** | Key pool in `ai.py` (store, choose, rest, refused), all keys hidden in errors, `.env` list, tests | 1 day |
| **P2** | AI page list of keys (add, test, order, remove, state), key column on AI usage, the same-project warning | 1 day |

## 5b. The owner's choice (2026-11-28) and its risk

The owner will use keys from separate projects in separate Google accounts. With that set-up, the pool gives
N separate quotas, and calls move on to the next key at once. 429s stop being visible until every key is used up.

- **Risk.** Several free accounts used to stack free quota goes against Google's terms ("do not get around usage
  limits"). Google can link the accounts (same phone, card, device, address) and block all the keys together,
  and maybe the accounts. The app does nothing to hide that the keys are used together.
- **A safer mix with the same code.** Put one paid key (billing on) **last** in the list. Free keys are used first,
  and if they are blocked or used up, the paid key carries on and the AI never stops.
- **Still possible with any number of keys.**
  - "Busy" (503) is about Google's servers, not the key. The app waits briefly or moves to the next model.
  - A model can be retired for everyone.

## 6. Decisions for the owner

1. Build the key pool (D) as described: a backup key, and free before paid?
2. Or turn on billing for the current project (A) first, which ends most 429s without code? A and D work
   together.
3. "Fill first" (keys used in your order) or "take turns" (spread over keys)? Fill first is recommended:
   predictable, and it uses the free key before the paid one.
