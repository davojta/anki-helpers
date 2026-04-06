# AnkiConnect API Reference

All requests are `POST http://localhost:8765` with JSON body `{"action": "...", "version": 6, "params": {...}}`.
Response: `{"result": <data>, "error": null}`.

## Key Data Schemas

### CardInfo (from `cardsInfo`)

```json
{
  "cardId": 1498938915662,
  "note": 1502298033753,
  "deckName": "Default",
  "modelName": "Basic",
  "ord": 1,
  "type": 0,
  "queue": 0,
  "due": 1,
  "interval": 16,
  "reps": 1,
  "lapses": 0,
  "left": 6,
  "mod": 1629454092,
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
| `type` | int | 0=new, 1=learning, 2=review, 3=relearning |
| `queue` | int | -3=user buried, -2=sched buried, -1=suspended, 0=new, 1=learning, 2=review, 3=filtered |
| `due` | int | Due position (new cards) or day number (review cards, relative to collection creation) |
| `interval` | int | Current interval in days (negative = seconds for learning) |
| `reps` | int | Total review count |
| `lapses` | int | Total lapse count |
| `left` | int | Steps remaining today |
| `mod` | int | Last modification timestamp (Unix epoch) |

### NoteInfo (from `notesInfo`)

```json
{
  "noteId": 1502298033753,
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
| `modelName` | str | Note type name |
| `tags` | [str] | Note tags |
| `fields` | obj | Field name → {value, order} |
| `mod` | int | Modification timestamp (Unix epoch) |
| `cards` | [int] | Card IDs belonging to this note |

## Key API Actions

### Card & Note Queries

| Action | Params | Returns | Notes |
|--------|--------|---------|-------|
| `findNotes` | `query: str` | `[int]` | Note IDs matching search |
| `findCards` | `query: str` | `[int]` | Card IDs matching search |
| `notesInfo` | `notes: [int]` | `[NoteInfo]` | Full note data |
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

**`cardReviews` 9-tuple**: `(reviewTime_ms, cardID, usn, buttonPressed, newInterval, previousInterval, newFactor, reviewDuration_ms, reviewType)`

- buttonPressed: 1=Again, 2=Hard, 3=Good, 4=Easy
- reviewType: 0=learning, 1=review, 2=relearning, 3=filtered

### Batch / Misc

| Action | Params | Returns |
|--------|--------|---------|
| `multi` | `actions: [{action, params}]` | `[results]` — multiple actions in one HTTP request |
| `sync` | — | `null` — triggers Anki sync |
| `requestPermission` | — | `{permission, requireApiKey?, version?}` |

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
| `note:basic` | Note type |
| `card:1` | Card template number |

### Card State

| Syntax | Meaning |
|--------|---------|
| `is:due` | Due cards |
| `is:new` | New cards |
| `is:learn` | Learning cards |
| `is:review` | Review cards |
| `is:suspended` | Suspended cards |

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

| Syntax | Meaning |
|--------|---------|
| `prop:ivl>=10` | Interval comparison |
| `prop:due=1` | Due tomorrow |
| `prop:due=-1` | Due yesterday |
| `prop:reps<10` | Review count |
| `prop:lapses>3` | Lapse count |
| `prop:ease!=2.5` | Ease factor comparison |

### Recent Events

| Syntax | Meaning |
|--------|---------|
| `added:1` | Cards added in last N days |
| `edited:1` | Notes edited in last N days (Anki 2.1.28+) |
| `rated:1` | Cards answered today |
| `rated:7:1` | Cards answered Again in last 7 days |
| `rated:7:3` | Cards answered Good in last 7 days |
| `prop:rated=0` | Cards answered today |
| `prop:rated=-7` | Cards answered 7 days ago |
| `introduced:1` | Cards first answered today (Anki 2.1.45+) |

### Object IDs

| Syntax | Meaning |
|--------|---------|
| `nid:123` | Note by ID |
| `cid:123,456` | Cards by IDs |

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

The per-day queries (steps 8-37) each set a `dueQuery` value on the note indicating how many days until due. This value is used for sorting in `list-red-flags`.

**Problem**: 30 API calls just to compute `dueQuery` values that are already available as the `due` field in `cardsInfo`.

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
note_ids = invoke("findNotes", query="edited:1")  # notes edited in last 1 day
```

Filters by **note** modification time. Available since Anki 2.1.28.

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
