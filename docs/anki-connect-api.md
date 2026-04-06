# AnkiConnect API Reference

All requests are `POST http://localhost:8765` (bound to `127.0.0.1`, configurable via `ANKICONNECT_BIND_ADDRESS`) with JSON body `{"action": "...", "version": 6, "params": {...}}`. Only `action` is required — `version` defaults to 4 if omitted, `params` defaults to `{}`.

Response is always HTTP 200: `{"result": <data>, "error": null}` (or `{"result": null, "error": "..."}` on failure). Errors are in the JSON body, not the HTTP status code (except 403 for blocked origins).

## Key Data Schemas

### CardInfo (from `cardsInfo`)

```json
{
  "cardId": 1498938915662,
  "note": 1502298033753,
  "deckName": "Default",
  "modelName": "Basic",
  "ord": 1,
  "fieldOrder": 1,
  "type": 0,
  "queue": 0,
  "due": 1,
  "interval": 16,
  "factor": 2500,
  "reps": 1,
  "lapses": 0,
  "left": 6,
  "mod": 1629454092,
  "flags": 0,
  "nextReviews": ["..."],
  "fields": {
    "Front": {"value": "...", "order": 0},
    "Back": {"value": "...", "order": 1}
  },
  "question": "front content",
  "answer": "back content",
  "css": "p {font-family:Arial;}"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `cardId` | int | Unique card ID |
| `note` | int | Parent note ID |
| `deckName` | str | Deck this card belongs to |
| `modelName` | str | Note type name |
| `ord` | int | Template ordinal (which card template) |
| `fieldOrder` | int | Same as `ord` (duplicated) |
| `type` | int | 0=new, 1=learning, 2=review, 3=relearning |
| `queue` | int | -3=user buried, -2=sched buried, -1=suspended, 0=new, 1=learning, 2=review, 3=filtered |
| `due` | int | Raw due value — meaning depends on queue (see table below) |
| `interval` | int | Current interval in days (negative = seconds for learning) |
| `factor` | int | Ease factor in permille (2500 = 250%) |
| `reps` | int | Total review count |
| `lapses` | int | Total lapse count |
| `left` | int | Steps remaining today |
| `mod` | int | Last modification timestamp (Unix epoch seconds) |
| `flags` | int | Card flags bitmask (0-7) |
| `nextReviews` | [str] | Next review state descriptions from FSRS scheduler |

**`due` field meaning by queue:**

| Queue | `due` meaning |
|-------|---------------|
| New (0) | Position in the new card queue (ordinal) |
| Learn (1) | Unix timestamp (seconds) for when card is due |
| Review (2) | Days since collection creation date (absolute day number) |
| DayLearn (3) | Days since collection creation date |
| PreviewRepeat (4) | Unix timestamp (seconds) |

To convert a Review card's raw `due` to a relative date: `days_from_today = due - days_elapsed`.

### NoteInfo (from `notesInfo`)

Accepts either `notes: [int]` (note IDs) or `query: str` (search query), or both.

```json
{
  "noteId": 1502298033753,
  "profile": "User_1",
  "modelName": "Basic",
  "tags": ["tag", "another_tag"],
  "fields": {
    "Front": {"value": "front content", "order": 0},
    "Back": {"value": "back content", "order": 1}
  },
  "mod": 1718377864,
  "cards": [1498938915662]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `noteId` | int | Unique note ID |
| `profile` | str | Current Anki profile name |
| `modelName` | str | Note type name |
| `tags` | [str] | Note tags |
| `fields` | obj | Field name → {value, order} |
| `mod` | int | Modification timestamp (Unix epoch seconds) |
| `cards` | [int] | Card IDs belonging to this note |

## Key API Actions

### Card & Note Queries

| Action | Params | Returns | Notes |
|--------|--------|---------|-------|
| `findNotes` | `query: str` | `[int]` | Note IDs matching search |
| `findCards` | `query: str` | `[int]` | Card IDs matching search |
| `notesInfo` | `notes: [int]` or `query: str` | `[NoteInfo]` | Full note data; accepts `query` as alternative to `notes` |
| `cardsInfo` | `cards: [int]` | `[CardInfo]` | Full card data |
| `notesModTime` | `notes: [int]` | `[{noteId, mod}]` | Lightweight (~15x faster than notesInfo) |
| `cardsModTime` | `cards: [int]` | `[{cardId, mod}]` | Lightweight (~15x faster than cardsInfo) |
| `getIntervals` | `cards: [int]`, `complete?: bool` | `[int]` or `[[int]]` | Card intervals |
| `getEaseFactors` | `cards: [int]` | `[int]` | Ease factors (2500 = 250%) |
| `cardsToNotes` | `cards: [int]` | `[int]` | Unique note IDs from card IDs |

### Deck Queries

| Action | Params | Returns |
|--------|--------|---------|
| `deckNames` | — | `[str]` |
| `deckNamesAndIds` | — | `{name: id}` |
| `getDecks` | `cards: [int]` | `{deckName: [cardIds]}` |
| `getDeckStats` | `decks: [str]` | Stats per deck (new/learn/review/total counts) |

### Review History

| Action | Params | Returns |
|--------|--------|---------|
| `getNumCardsReviewedToday` | — | `int` |
| `getNumCardsReviewedByDay` | — | `[[dateStr, count]]` |
| `cardReviews` | `deck: str`, `startID: int` | 9-tuples (see below) |
| `getReviewsOfCards` | `cards: [str]` | `{cardId: [ReviewEntry]}` |
| `getLatestReviewID` | `deck: str` | Unix ms timestamp (0 if none) |
| `answerCards` | `answers: [{cardId, ease}]` | `[bool]` — programmatically answer cards (ease 1-4) |
| `setDueDate` | `cards: [int]`, `days: str` | `null` — set due date (e.g. `"0"`, `"!1"`, `"0-3"`) |

**`cardReviews` 9-tuple**: `(reviewTime_ms, cardID, usn, buttonPressed, newInterval, previousInterval, newFactor, reviewDuration_ms, reviewType)`

- buttonPressed: 1=Again, 2=Hard, 3=Good, 4=Easy
- reviewType: 0=learning, 1=review, 2=relearning, 3=filtered

### Batch / Misc

| Action | Params | Returns |
|--------|--------|---------|
| `multi` | `actions: [{action, params}]` | `[results]` — multiple actions in one HTTP request |
| `sync` | — | `null` — triggers Anki sync |
| `requestPermission` | — | `{permission, requireApiKey?, version?}` |
| `reloadCollection` | — | `null` — reload the collection from disk |

## Search Syntax (for `findNotes`, `findCards`)

### Basic

| Syntax | Meaning |
|--------|---------|
| `dog cat` | AND (both terms) |
| `dog or cat` | OR |
| `-cat` | NOT |
| `"exact phrase"` | Exact match |
| `d*g` | Wildcard |

### Field-specific

| Syntax | Meaning |
|--------|---------|
| `front:dog` | Exact match in field |
| `front:*dog*` | Contains |
| `front:` | Empty field |
| `tag:animal` | Tag (includes subtags) |
| `deck:french` | Deck (includes subdecks) |
| `deck:filtered` | Cards currently in a filtered deck |
| `note:basic` | Note type (by name) |
| `card:1` | Card template number |
| `nc:text` | Accent-insensitive (no-combining) text search |
| `sc:text` | Strip cloze markers before searching |
| `w:dog` | Word boundary search |

### Card State

| Syntax | Meaning |
|--------|---------|
| `is:due` | Due cards |
| `is:new` | New cards |
| `is:learn` | Learning cards (type 1, 3) |
| `is:review` | Review cards (type 2, 3) |
| `is:suspended` | Suspended cards (queue -1) |
| `is:buried` | Buried cards (queue -2 or -3) |
| `is:buried-manually` | User-buried cards (queue -3) |
| `is:buried-sibling` | Scheduler-buried cards (queue -2) |

All state keywords are case-sensitive (lowercase only).

### Flags

| Syntax | Meaning |
|--------|---------|
| `flag:0` | No flag |
| `flag:1` | Red |
| `flag:2` | Orange |
| `flag:3` | Green |
| `flag:4` | Blue |
| `flag:5` | Pink |
| `flag:6` | Turquoise |
| `flag:7` | Purple |

### Card Properties (`prop:`)

All support comparison operators: `=`, `!=`, `<`, `>`, `<=`, `>=`.

| Syntax | Type | Meaning |
|--------|------|---------|
| `prop:ivl>=10` | u32 | Interval in days |
| `prop:due=1` | i32 | Relative days from today (signed — negative = overdue) |
| `prop:reps<10` | u32 | Total review count |
| `prop:lapses>3` | u32 | Total lapse count |
| `prop:ease!=2.5` | f32 | Ease factor (as percentage, stored as permille internally) |
| `prop:pos<=100` | u32 | New card position (only matches new cards) |
| `prop:rated=0` | i32 | Days relative: 0=today, -1=yesterday, etc. |
| `prop:resched=0` | i32 | Days since manual reschedule |
| `prop:s>21` | f32 | FSRS stability in days |
| `prop:d>0.3` | f32 | FSRS difficulty (0-1 search range, stored as 1-10 internally) |
| `prop:r<0.9` | f32 | FSRS retrievability (0-1 fraction) |
| `prop:cdn:key>5` | f32 | Custom data number property |
| `prop:cds:key=val` | str | Custom data string property |

### Recent Events

| Syntax | Meaning |
|--------|---------|
| `added:1` | Cards added in last N days |
| `edited:1` | Notes edited in last N days (Anki 2.1.28+). Based on note `mod` timestamp, compared against previous scheduler day boundary |
| `rated:1` | Cards answered today |
| `rated:7:1` | Cards answered Again in last 7 days |
| `rated:7:3` | Cards answered Good in last 7 days |
| `introduced:1` | Cards first answered today (Anki 2.1.45+). Excludes manual reschedulings |
| `resched:1` | Cards manually rescheduled in last N days |

### Object IDs & Misc

| Syntax | Meaning |
|--------|---------|
| `nid:123` | Note by ID |
| `cid:123,456` | Cards by IDs |
| `did:123,456` | Deck by IDs (includes filtered deck cards) |
| `mid:123` | Notetype by ID |
| `dupe:ntid,text` | Find duplicate notes in notetype with same field text |
| `preset:name` | Cards in decks using named preset |
| `has-cd:key` | Cards with custom data key |

### Regex

| Syntax | Meaning |
|--------|---------|
| `re:\d{3}` | Regex search |
| `front:re:[a-c]1` | Regex in specific field |
| `tag:re:^parent$` | Exact tag match (Anki 2.1.50+) |

---

## How We Currently Query

### Red-flagged cards with due sorting

The current `find_cards_with_red_flag_sorted()` method in `anki_connect.py` makes **~35 API calls**:

```
1. findNotes("flag:1")              → note IDs with red flag
2. findCards("nid:<ids>")           → card IDs for those notes
3. cardsInfo(cards)                 → card-level data (deck, due, interval)
4. getIntervals(cards)              → intervals per card
5. notesInfo(notes)                 → note fields and tags
6. findNotes("flag:1 prop:due<0 prop:due>-7")  → overdue notes
7. findNotes("flag:1 prop:due<-6")             → very overdue notes
8-37. findNotes("flag:1 prop:due=N") for N=0..29 → per-day due counts
```

The per-day queries (steps 8-37) each set a `dueQuery` value on the note indicating how many days until due. This value is used for sorting in `list-red-flags`. However, the bucketing is coarse — overdue cards all get `dueQuery=-2`, losing fine-grained ordering.

**Problem**: 30 API calls just to compute `dueQuery` values that are already available as the `due` field in `cardsInfo`. The raw `due` field provides exact relative days (e.g., -224, -214, -211), giving much better sort fidelity than the bucketed approach (`dueQuery=-2` for all overdue cards).

**Validated**: `days_elapsed = 927` (collection creation). For review cards, `relative_days = raw_due - days_elapsed`. All 54 red-flagged cards confirmed overdue with negative relative days. Sort order differs between the two approaches because the current method buckets overdue cards together.

### Simplified approach (for sync)

The `sync` command uses a much simpler API sequence:

```
1. findNotes("")                    → all note IDs
2. notesInfo(note_ids)              → all note data (fields, tags, mod)
3. findCards("")                    → all card IDs
4. cardsInfo(card_ids)              → all card data (deck, due, interval, flag)
```

The `due` field from `cardsInfo` is stored directly as `due_query` — no per-day queries needed. This gives the same ordering in **4 API calls** instead of 35.

---

## Querying Recently Changed Cards

There is no `prop:mod` search operator — modification timestamp is not directly filterable via search syntax. But there are alternatives:

### Option A: `edited:N` search (note-level)

```python
note_ids = invoke("findNotes", query="edited:1")  # notes edited since previous scheduler day boundary
```

Filters by **note** modification time (`n.mod` column). The cutoff is `next_day_at - 86400 * N`, so `edited:1` means "notes modified since the start of the previous scheduler day" — not the last 24 wall-clock hours. Available since Anki 2.1.28. Minimum value is 1.

### Option B: `cardsModTime` / `notesModTime` (lightweight)

```python
# Get all card IDs first, then filter by mod time
card_ids = invoke("findCards", query="")
mod_times = invoke("cardsModTime", cards=card_ids)  # ~15x faster than cardsInfo
cutoff = int(time.time()) - 86400
recent = [m["cardId"] for m in mod_times if m["mod"] >= cutoff]
recent_info = invoke("cardsInfo", cards=recent)
```

### Option C: `notesInfo` with client-side filtering

```python
note_ids = invoke("findNotes", query="edited:1")
notes_info = invoke("notesInfo", notes=note_ids)
cutoff = int(time.time()) - 86400
recent = [n for n in notes_info if n["mod"] >= cutoff]
```

### Recommendation for incremental sync

Use `edited:N` to get recently modified notes, then client-side filter by `mod` epoch timestamp for precision:

```python
days_since = max(1, math.ceil((now - last_sync_epoch) / 86400) + 1)
note_ids = invoke("findNotes", query=f"edited:{days_since}")
notes_info = invoke("notesInfo", notes=note_ids)
recent = [n for n in notes_info if n["mod"] > last_sync_epoch]
```

This fetches only modified notes in a single `findNotes` + `notesInfo` call pair, then filters precisely client-side.

---

## Querying Recently Reviewed Cards

### Cards answered today

```python
card_ids = invoke("findCards", query="rated:1")
# or: prop:rated=0
```

### Review history per deck

```python
# Get all reviews since a timestamp (in milliseconds)
reviews = invoke("cardReviews", deck="Default", startID=1594194095740)
# Returns: [[reviewTime_ms, cardID, usn, buttonPressed, newInterval,
#            previousInterval, newFactor, reviewDuration_ms, reviewType], ...]
```

### Review stats

```python
count = invoke("getNumCardsReviewedToday")
daily = invoke("getNumCardsReviewedByDay")
# [["2021-02-28", 124], ["2021-02-27", 261]]
```

---

## Verification Results (2026-04-06)

Tested against live Anki instance with 8 decks, 54 red-flagged cards. Source code validated against `/home/dzianis/projects/dev/github/anki-connect` (plugin) and `/home/dzianis/projects/dev/github/anki` (Anki core).

### Schema Verification

**CardInfo — all 21 keys confirmed:**

```
answer, cardId, css, deckName, due, factor, fieldOrder, fields, flags,
interval, lapses, left, mod, modelName, nextReviews, note, ord, question,
queue, reps, type
```

Sample card from live data:

```
cardId=1517323757459  due=703  type=2  queue=2  interval=84
factor=2500  flags=1  reps=21  lapses=3  left=0
mod=1748881485  nextReviews=['<10m', '3.4mo', '1.3y', '2.8y']
modelName='Spoken deck-30feb'
deckName='[W/ audio] Finnish - English Core 900 (Spoken Language)'
```

**NoteInfo — all 7 keys confirmed:**

```
cards, fields, mod, modelName, noteId, profile, tags
```

`profile` = `'User 1'` (not `User_1` as documented — value depends on Anki profile name).

**`notesInfo` query param — confirmed.** Both `notesInfo(notes=[...])` and `notesInfo(query="flag:1")` return identical count (54).

### `due` Field Conversion

For this collection, `days_elapsed = 927` (determined by finding a card where `prop:due=0` and reading its raw `due` value).

Conversion: `relative_days = raw_due - days_elapsed`

| Raw `due` | Relative | Meaning |
|-----------|----------|---------|
| 703 | -224 | 224 days overdue |
| 713 | -214 | 214 days overdue |
| 927 | 0 | due today |
| 928 | 1 | due tomorrow |

**Verified with `prop:due` queries:**

| Query | Count | Interpretation |
|-------|-------|----------------|
| `flag:1 prop:due<0` | 51 | All overdue red-flagged cards |
| `flag:1 prop:due<=0` | 51 | Same (none due today) |
| `flag:1 prop:due=0` | 0 | No red-flagged cards due today |
| `flag:1 prop:due>-7` | 2 | Red-flagged cards due within next week |
| `flag:1 is:due` | 51 | Due = overdue in this set |
| `prop:due=0` (all cards) | 2 | 2 cards across all decks due today |

All overdue cards confirmed: raw `due` values (703-785) are all < 927 (`days_elapsed`), giving negative relative days. The `prop:due<0` result (51) matches exactly.

### Current vs Simplified Approach

**Current** (`find_cards_with_red_flag_sorted`, ~35 API calls):
- All 54 red-flagged cards returned
- Overdue cards bucketed: `dueQuery=-2` (very overdue) or `dueQuery=90` (default)
- 51 cards share `dueQuery=-2` — no sort granularity within overdue group
- Sorted by `dueQuery` ascending, then by card order

**Simplified** (`cardsInfo` only, 4 API calls):
- All 54 red-flagged cards returned
- Exact relative days: -225, -224, -222, -219, -218, -217, -216, ...
- 15+ distinct values in first 15 overdue cards — much better sort granularity
- Sorted by `raw_due` ascending (equivalent to `relative_days` ascending)

**Sort order differs** because the current approach loses information through bucketing. The simplified approach produces a more meaningful ordering.

### Lightweight Mod Time Endpoints

**`cardsModTime`** — confirmed returns `[{cardId, mod}]`. Example:
```
[{'cardId': 1517323757459, 'mod': 1748881485},
 {'cardId': 1517323757463, 'mod': 1751863438},
 {'cardId': 1517323757615, 'mod': 1754365868}]
```

**`notesModTime`** — confirmed returns `[{noteId, mod}]`. Example:
```
[{'noteId': 1517323756587, 'mod': 1528619043},
 {'noteId': 1517323756591, 'mod': 1737917053},
 {'noteId': 1517323756743, 'mod': 1751795092}]
```

### Search Operators Verified

| Operator | Result | Status |
|----------|--------|--------|
| `flag:1` | 54 cards | Works |
| `prop:due<0` | 51 cards | Works |
| `prop:due<=0` | 51 cards | Works |
| `prop:due=0` | 0 cards (flag:1), 2 cards (all) | Works |
| `prop:due=1` | 0 cards (flag:1), 1 card (all) | Works |
| `prop:due>-7` | 2 cards | Works |
| `prop:due<1` | 51 cards | Works |
| `is:due` | 51 cards | Works |
| `edited:1` | 0 notes | Works (no recent edits) |
| `edited:7` | 0 notes | Works |
| `edited:30` | 0 notes | Works |
| `rated:1` | 0 cards | Works (no reviews today) |
| `rated:7` | 0 cards | Works |
| `added:1` | 0 cards | Works |
| `introduced:1` | 0 cards | Works |
| `resched:1` | 0 cards | Works |

All operators returned valid results. Zero counts are expected — no recent review/edit activity in this collection.

### Deck Stats

```
Decks: 8 total
'[W/ audio] Finnish - English Core 900': new=0, learn=0, review=50, total=871
'Basic Vocabulary Eng-Fin':              new=0, learn=3, review=50, total=92
'Finnish Grammar':                       (not shown in top 3)
```

### Review History

```
Cards reviewed today: 0
Recent review days: [['2025-09-25', 1], ['2025-09-21', 7], ['2025-08-31', 19],
                      ['2025-08-27', 21], ['2025-08-25', 7]]
```

Last review activity was 2025-09-25, confirming `rated:1` = 0 is correct.

### `nextReviews` Field

Returns FSRS answer previews — 4 strings (one per answer button). Example:
```
['<10m', '3.4mo', '1.3y', '2.8y']
```
These are human-readable next intervals for Again/Hard/Good/Easy respectively. Uses Unicode bidi isolates around numbers.

### Source Code Validation

Validated against:

- **AnkiConnect plugin** (`/home/dzianis/projects/dev/github/anki-connect/__init__.py`):
  - HTTP protocol, request schema, response format — confirmed
  - All API actions exist as `@util.api()` decorated methods
  - `multi` action confirmed: iterates actions through the same handler
  - `cardsModTime` / `notesModTime` confirmed at lines 1582-1763

- **Anki core** (`/home/dzianis/projects/dev/github/anki/rslib/src/search/`):
  - All search operators implemented in `parser.rs` and `sqlwriter.rs`
  - `edited:N` → `n.mod > {cutoff}` (note-level, scheduler day boundary)
  - `prop:due` → `{due} {op} {input + days_elapsed}` (relative days)
  - `flag:N` → `(c.flags & 7) == {N}` (bitmask on flags byte)
  - FSRS properties use `extract_fsrs_variable` and `extract_fsrs_retrievability`
  - Case-sensitive state keywords confirmed in parser
