# VoicePortal — IVR Model & Reference Breakdown

*Research + proposed data model for the IVR/menu phase. Based on how SimpleVoiceCenter / SimpleVoiceBox actually work.*

---

## 1. How the reference products work

SimpleVoiceCenter and SimpleVoiceBox are the same product. It's a **voicemail-tree system**: one phone number leads a caller through a tree of "voice boxes" (extensions), each of which plays a greeting and optionally takes a message or forwards the call.

### Plans
| Plan | Number | Access |
|------|--------|--------|
| Standard (free) | Shared toll number | Caller enters an **access code** |
| Toll-free | 800 number | Access code, 6¢/min |
| Private ($9.95/mo) | Dedicated number | **No access code needed** |

The free/toll tiers **share a number** and separate customers by access code. The paid tier gives a **dedicated number** so callers skip the code. *This directly answers our open phone-number question — see §4.*

### The voice-box tree
- **Extension 0** holds the main greeting ("press 1 for X, press 2 for Y…").
- Each key press routes to a **sub-box**, and sub-boxes can nest unlimited levels deep.
- Every box is one of three **extension types**:
  - **Playback Only** — caller just listens (announcements, info lines, sermons).
  - **Playback & Record** — caller listens, then can leave a message (voicemail).
  - **Dial Out** — call is forwarded to a real phone (cell/landline).

### Two ways to administer — the same tree
This is the crux of what the boss is pointing at. The box tree can be edited from **either**:

**A) Touch-tone keypad (phone admin)**
Dial in → enter access code + `*` (or just `*` on a private number) → password + `#` → you're in admin mode. From there:

| Key | Function |
|-----|----------|
| `#` | Create new extension / stop recording |
| `*` | More options |
| `1` | Save recording |
| `4` | Replay greeting / message |
| `5` | Next message |
| `6` | Delete message |
| `7` | Listen to all messages across all boxes |
| `9` | Create extension / return to main menu |

**B) Web interface**
Upload/download greetings and audio, organize boxes, retrieve messages, toggle message-taking per box, email notifications with caller ID.

**Both surfaces read and write the same underlying box tree.** That's the key architectural requirement: one config, two editors.

---

## 2. The three interaction surfaces (the boss's framing)

1. **End caller** (phone, touch-tone) — navigates the menu tree, hears audio, optionally leaves a message or gets forwarded.
2. **Admin via keypad** — business owner calls in, authenticates with a PIN, edits their own tree over the phone.
3. **Admin via web** — the portal we're building: visual menu builder, audio upload, message retrieval.

Surfaces 2 and 3 are just two front-ends over the same data.

---

## 3. Proposed data model

The product is a **menu tree**, not a flat file list. Minimum models:

```
Account (the customer / business)
  └─ owns one or more PhoneNumbers (or shares one + an access code)
  └─ owns a tree of Menus

Menu  (= a "voice box" / extension)
  - account       (FK)
  - parent        (FK to Menu, null = root / extension 0)
  - key           (the digit pressed to reach it from the parent: 0–9, *, #)
  - name          (admin label, e.g. "Sunday Service")
  - type          (PLAYBACK_ONLY | PLAYBACK_AND_RECORD | DIAL_OUT)
  - greeting      (FK to AudioFile — the prompt played on entry)
  - dial_out_number (only for DIAL_OUT)
  - record_enabled  (toggle message-taking)

AudioFile  (already built)
  - the greeting/content stored on CarrierX, referenced by file_sid

Message  (new — for PLAYBACK_AND_RECORD boxes)
  - menu (FK)
  - caller_id
  - recording_file_sid (stored on CarrierX)
  - received_at
  - is_new
```

A caller's journey = walking this tree, key press by key press. Our existing `AudioFile` model slots in cleanly as the `greeting` on each `Menu`.

### What "more options" could mean (boss wants similar + more)
- Time-based routing (different menu after hours)
- Multiple greetings per box (rotate / scheduled)
- Web-based analytics (call counts per box, listen-through rate)
- Transcription of recorded messages (we already have Whisper in the other system)
- Conference-room box type (later phase)

---

## 4. The decision this forces

**Shared number + access code vs. dedicated number per customer** — the reference product offers *both* as pricing tiers, and so could we:

- **Free / basic tier** → shared CarrierX number, caller enters an account access code.
- **Paid tier** → dedicated CarrierX number, no code.

This means the data model needs to support **both from day one** (an `Account` has an optional `access_code` and an optional dedicated `PhoneNumber`). Framing it as a pricing lever (like the reference product does) resolves the open question instead of forcing an either/or.

---

## 5. Suggested build order

1. Lock the number model as a **pricing tier** (shared+code / dedicated) — unblocks everything.
2. Build the **`Menu` tree data model**.
3. Build the **web menu builder** (assign audio to keys, set box types).
4. Build the **CarrierX call-routing webhook** that walks the tree for a live caller.
5. Add **keypad admin** + **message recording/retrieval**.
6. Layer in the "more options" (scheduling, analytics, transcription).
