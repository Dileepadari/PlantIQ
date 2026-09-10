# not_for_you.md

A personal working log. Not documentation, and nothing here is needed to use or
contribute to PlantIQ. Everything a newcomer actually needs is in
[README.md](./README.md) and [DEVDOC.md](./DEVDOC.md).

---

## Five other people's passwords

`src/Database.db` was tracked. `.gitignore` even said why:

> Local instance state. Database.db is committed on purpose: it carries the plant
> threshold profiles the app is useless without.

The first half of that is true. The plant profiles are reference data and the app
genuinely does not work without them. The second half is the part that matters:
that file did not only carry the profiles.

Its `users` table held seven accounts. **Six of them had their passwords in clear
text**, next to the account holder's real name and real email address. Five of
those are not mine. They are the other people on the project team and one other
student.

Then I looked at the history. **Seven `Database.db` blobs are reachable, and every
one of them holds clear text.** The earliest is from October 2023. So this has
been public for close to two years.

The passwords are not written down here, but the shape of them is worth naming
because it makes this worse rather than better: each is a trivially guessable
transformation of the account holder's own name. That is exactly the construction
a person reuses on other sites.

### What I did

- Plant profiles extracted to `src/plantiq/data/plants.json`. Ninety lines, and a
  diff can read them.
- `db.seed_plants()` inserts any shipped species the database is missing, matched
  by name so it never duplicates a row and never overwrites a threshold somebody
  tuned. `init_db()` calls it on every start, so a checkout with no database file
  becomes a working install with no separate step.
- `src/Database.db` untracked. `*.db`, `*.sqlite` and `*.sqlite3` gitignored, and
  the old comment replaced with one that says what actually happened.
- CI fails if any of those extensions reappears in `git ls-files`. `.gitignore`
  does not stop `git add -f`, and a rule that only exists in a file nobody reads
  is not a rule.
- `tests/test_seed.py` asserts a fresh database has **zero** users.

### What is still outstanding, and is not mine to fix

**Four other people need to be told.** Their names, email addresses and passwords
have been in a public repository since October 2023. I can rotate my own. I cannot
rotate theirs, and they cannot decide what to do about reuse elsewhere until they
know.

**The history still has all seven blobs.** Untracking a file at HEAD does not
remove what is already pushed, and a purge means a rewrite and a force-push. That
is the repository owner's call.

## A credential the previous pass walked straight past

Commit `a5bda73`, five days before this one, is titled *"Move ThingSpeak keys and
the device token out of source into environment and an untracked secrets header"*.
It did exactly that. It also created `Arduino/secrets.example.h` containing:

```c
#define SECRET_WIFI_SSID        "your-wifi-ssid"
#define SECRET_WIFI_PASS        "your-wifi-password"
```

Two placeholders for credentials that were **still hardcoded twelve lines into
the sketch**, and stayed there:

```c
const char *ssid = "GALAXY KING";
const char *password = "DILEEPPRASANTHi";
```

A real home network and its real password. The placeholders for them were written
in the same commit that left them behind.

I think this is the most instructive thing in the repository. The previous pass
was not careless. It found the ThingSpeak keys, moved them properly, and wrote the
example header. It just searched for what it was looking for, and `ssid` is not
what an API-key sweep looks for.

So CI now greps the sketch for a long string literal assigned to any of `ssid`,
`password`, `apiKey`, `mqttPass`, `mqttUserName` or `ClientID`. Not because the
next person will be careless, but because they will be looking for something else.

## The plant with no VOC alerting

`Rose.VOC_min` was the string `" "`. A single space.

`plants.thresholds_for()` runs each bound through `_to_float`, which returns
`None` for that, and a metric with either bound missing is skipped entirely. So
for anyone growing a Rose, the VOC sensor - the one the whole project is built
around, the early-warning signal that justifies the hardware - **was silently
doing nothing**, and the Analysis page showed `unknown` in a row of green.

That is not a crash and it is not a wrong answer. It is a missing answer that
looks like a normal one, which is why it survived two years.

It is `0` in the JSON now, and `test_every_plant_has_a_usable_voc_range` asserts
every bound of every shipped species is a number.

## Sixty-three lines of test that were really nine seconds of network

The first version of the suite passed and took nine seconds. That should have
been the tell.

`test_a_failed_fetch_returns_an_empty_offline_feed_rather_than_raising` set no
read key, called `fetch_readings`, and asserted `online is False`. It failed, with
`online` being `True`, because **the project's ThingSpeak channel is public** and
answers without a key. The test had been reaching over the internet to a real
service and I had written it believing the absent key was the failure condition.

Worse, it was not alone: the `signed_in` fixture loads the dashboard, and the
dashboard fetches readings. Most of the suite was quietly making live HTTP calls
and would have gone red on a runner with no egress, for reasons having nothing to
do with the code.

`conftest.py` now has an autouse fixture that replaces `requests.get` with a
raise. Nine seconds became under three, and the offline test tests the offline
path instead of testing that ThingSpeak is up.

## The login page was advertising one of the leaked accounts

`login.html` carried a "try it without signing up" box with a real account's email
and password in `<code>` tags. That account was row 7 of the committed database.

It is gone. Signup is four fields with no confirmation step, so the honest prompt
is to make an account rather than to hand out someone else's.

## The file called LICENSE was not a licence

In full, before this pass:

> Thanks for using the website, This website is built using Bootstrap and Morris
> charts, and taken inspiration from the Tim creator.
>
> Best regards
> Team Aakashavani
> @ Copyright 2023 IIIT Hyderabad

A thank-you note from a Bootstrap dashboard template, in the file whose name
tells every reader and every tool what they are allowed to do with the code. The
repository has been public for two years with no licence at all, which legally
means all rights reserved, while looking from the file listing like it had one.

It is MIT now, naming all four authors. The Bootstrap and Morris attribution it
was carrying is also out of date: the 2026 UI rewrite dropped both, and there is
no third-party CSS or JS left in the tree to attribute.

## Four people's email addresses are on the About page

`about.html` has `mailto:` links to four `@students.iiit.ac.in` addresses. They
are institutional, they are already in the git history as commit author
addresses, and the team put them there themselves on their own project page.

So I have left them exactly as built. Flagging it rather than changing it,
because publishing three other people's contact details is their decision and
not mine, and because it is the kind of thing that gets scraped.

## Small things

- **Settings rejects an out-of-range chart window; signup clamps it.** Both are
  defensible, they are just not the same, and neither was tested. Both are tested
  now, including the difference, so at least the inconsistency is deliberate.
- **`PLANTIQ_TS_BASE_URL` is new.** The feed host was hardcoded in two f-strings.
  Making it configurable is what let the README screenshots be taken against a
  local stand-in rather than against a real channel whose data stopped in
  November 2023, and it costs one config line.
- **The device token defaults to empty and an empty token rejects everything.**
  That was already true and it is right; there is now a test that says so,
  because the failure mode of getting it backwards is an open write endpoint on
  the public internet.
- **ruff's line length is 120, not 100.** Only the `METRICS` table needs it, and
  that table reads far better column-aligned than wrapped.
