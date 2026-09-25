# CS2 Wallhack (external ESP + auto bhop)

External CS2 cheat: walks the game's entity list with `ReadProcessMemory`,
projects players through the view matrix, and draws boxes / names / health
on a click-through overlay. No injection. ESP is read-only; the auto bhop
can optionally write the pawn's jump button state (Memory mode).

## Build

1. Open `cs2-wallhack.sln` in Visual Studio 2022 or newer (any edition — the
   "Desktop development with C++" workload must be installed). The project
   auto-selects your installed platform toolset.
2. Select **x64** (CS2 is 64-bit; Win32 is not configured) and **Release**.
3. `Ctrl+Shift+B` to build, `F5` to run.

The console window shows status: attach confirmation, base address, and
whether it's waiting for `cs2.exe`.

## Use

1. Launch CS2 and join a map. Set video mode to **Fullscreen Windowed**
   (the overlay is a topmost layered window and may not show over exclusive
   fullscreen).
2. Run the cheat (it attaches to the running process).
3. `INSERT` opens the menu, `END` exits.

## Menu

Toggles: Wallhack, Aimbot, Triggerbot, Autowall, Revolver Trigger, Sniper
Crosshair, Radar, FOV Circle, Auto Bhop, Enemy Weapons (Tab), Recoil Control —
plus the sliders (Smoothness, Reaction, Trig Reaction, Trig Hitchance, Aimbot
FOV, RCS Smoothness).
Drag the header to move the panel.

A toggle whose feature can't act while another toggle is off draws dim —
gray label, faded check box — while staying clickable and remembered:
Revolver Trigger and the trigger conditions (Through Wall, Air Check, Scope
Check, Flash Check) need Triggerbot on, Auto Scope needs Aimbot or
Triggerbot, FOV Circle needs Aimbot, Box/Skeleton/Fill Glow/Outline Glow
need Wallhack, and Enemy Nades Only needs some grenade feature on.
Revolver Trigger in particular no longer fires while Triggerbot is off —
its full-hold shot runs through the triggerbot — while Autowall keeps its
own revolver shot either way.

Every GUI fades: the menu, each side card (aim, wallhack, box, C4, tracer,
sniper, thickness preview, colour picker) and the spectator list dissolve
in when they appear and out when they close (~150 ms crossfade over the
game, not a pop); the hit-log history text eases the same way.

**Enemy Weapons (Tab)** (Wallhack tab): with the toggle on, hold TAB and a
card appears on the right of the screen, beside the scoreboard — one row per
armed enemy: their name in enemy red, the full kit under it (guns, Zeus, C4,
grenades in that order; knives are left out, every slot has one). It
refreshes live while the key is down and disappears the moment you release
it.

**Autowall** (Trigger tab): hover either autowall row for its one-line
description in the footer. Autowall picks whatever the crosshair rests on —
wall or not — and aims at that target and triggers only while the estimated
shot damage clears the **Autowall Dmg** slider (101 = Kill). With the
aimbot/triggerbot off it acts alone; with them on it only handles the
targets their own ray cannot see.

### Recoil Control (RCS)

The seventh tab, one global setting for every weapon:

- **Recoil Control** toggle — while it is on, spraying (left button down,
  past the first shot, not scoped) reads the live aim punch from the local
  pawn's aim-punch services and injects the mouse movement that cancels twice
  every punch change, so the crosshair stays where you put it through a
  spray. The angle is converted with the aimbot's own px-per-mickey
  estimate, so it tracks any in-game sensitivity without reading the sens
  setting. Nothing runs while the menu is open, while scoped, or with the
  button up — the punch baseline keeps following the real value in the
  background, so turning a gate off can never fire a stale correction.
- **Smoothness** bar (1–10) — how much of the owed correction is released
  each frame: 1 = instant, 10 = slowest. It is lag, not loss: the rest of
  the correction stays owed and is applied on the following frames. **Safe
  mode pins it at 5** (forced on when safe mode is enabled, and the bar
  cannot be dragged away from 5 while safe mode is on).
- **Held Weapon** row — the weapon the local player currently holds, read
  through the same detection the aimbot uses (the weapon chain now also
  updates when only RCS is on).
- Saved with the config as `rcs=` and `rcssm=`; a 1 Hz `[rcs]` line lands
  in the log while it is actively compensating.

### Weapon classes (AimHack)

The AimHack tab carries a dropdown on the right of its header with
`GLOBAL, Pistols, Smgs, Snipers, Rifles, Shotguns`. It picks which class the
Smoothness / Reaction / Aimbot FOV sliders edit, and the aimbot runs the
settings of the weapon class actually in hand (the FOV circle follows them
too). **GLOBAL** is the fallback: every class that has not been set up — and
every weapon outside the five classes (knife, grenades, LMGs, taser) — runs
on it, and an untouched class tracks its sliders live. Moving a slider on a
class copies the GLOBAL values over and detaches it; the dimmed dropdown
label and the footer hint say when a class still runs on GLOBAL. Triggerbot
settings, hitbox and the aimbot switch stay global. Classes are saved with
the config (`wepN=` lines); a class missing from a config falls back to
GLOBAL.

**Sniper Settings** (Trigger tab): a full-row button that opens a side card
holding the two sniper switches.

- **Scope Check** — while a sniper is in hand, the aimbot and the triggerbot
  act only on a **scoped** weapon: unscoped, the aimbot idles and the trigger
  stays quiet. The card edits **GLOBAL** (the default for everything) by
  default, and the **Snipers** class's own override when the weapon dropdown
  sits on the Snipers tab — the caption in the card names which one it is
  writing. Saved as `scope=` / `scopesniper=`.
- **Autoscope** — while a sniper is in hand and unscoped, a visible enemy
  entering the aimbot FOV circle injects a right-click to zoom in, so the
  scope check has its scope the instant a fight starts. It presses only from
  the unscoped state (CS2 cycles zoom 0 → 1 → 2 → 0, so the scope can never
  be walked back off), leaves the zoom while the player holds the right
  button alone, needs the aimbot or triggerbot on (something has to use the
  zoom), and waits out the zoom animation after each press. Saved as
  `autoscope=`.

### Auto Bhop

Edge-triggered bunny hop: while **Space** is held, the air→ground transition
fires exactly one jump tick and the jump releases again while airborne.

- **Jump Mode** (row under the toggle): **Input** sends a Space key
  release+press pulse with `SendInput` (single atomic pair, fired on the
  touchdown tick) and a speculative **pre-jump** — this hop's touchdown
  predicted from the previous hop's measured air time (takeoff stamps the
  clock, the last air duration gives the touchdown) so the press lands
  inside the landing command's window (possible zero-ground-tick jump; a
  wrong prediction costs nothing — the landing pulse is still the fallback).
  **Memory** sets `IN_JUMP` in the pawn's
  `m_nButtons` for one tick with `WriteProcessMemory` (needs the cheat run
  as administrator).
- **Bhop Status** shows `Attached/Not attached | On/Off` and the last
  status or auto-disable reason.
- The worker runs on its own thread with its own process handle, resolves
  `dwEntityList`, `dwLocalPlayerPawn`, `dwLocalPlayerController`,
  `m_bPawnIsAlive`, `m_hPlayerPawn`, `m_fFlags`, `m_pMovementServices`
  and `m_nButtons` by pattern-scanning `client.dll` (schema-name scan for
  the netvars), and cross-checks every candidate against the live process.
  While the controller reports the player **dead or in the menu** the
  worker just waits (`waiting: ...` / `dead / not spawned` status) instead
  of validating — a dead player's pawn global holds a stale freed object.
  Only a spawned pawn is validated: an implausible pawn, stale pointer or
  failed write auto-disables the feature and reports why on the status row.

Teammates are off by default — set `kShowTeammates = true` in `main.cpp`
to include them.

### Hit Log

Hits you actually dealt (hp-drop attribution — only while the victim is
under your crosshair or aim-locked with a recent shot, so team/nade/fall
damage never counts) show up in two places:

- **Feed** — the animated lines under the radar: `Hit pv in the head for
  42 damage.` Newest at the bottom, fades after **Log Time** (Misc slider,
  1–10 s, saved as `hitlog=`).
- **History** (the same popping text, kept) — with **Hit Log** on (Misc
  button, saved as `hitgui=`) the last 50 hits are listed directly under
  the live feed rows as plain text: `12:03 pv head 42` with the time in
  gray, damage in green and kills tagged `(kill)` in red, newest first.
  No card — it is the same feed column, and it only appears once there is
  something to show.

### Grenades

A whole fifth tab (**Grenades**, pin icon) for everything thrown: it tracks
every HE / flash / smoke / molotov / decoy — and burning fire — through the
entity list, then models what happens next. All numbers on this tab are
**estimates**: the models and their constants are below, and the tab's footer
says the same.

- **Grenade ESP** — a colored marker per grenade with its type, the time
  until it pops, and who threw it (team included, so you know if it is
  yours). HE markers are red, flashes yellow, smoke blue, molotovs orange.
- **Path & Landing** — the flight trail (solid = already flown, dashed =
  predicted), a white cross where it will land with a time-to-impact, and
  for HE the blast-radius circle it will damage at. The landing floor is
  estimated as the lowest feet near the arc (yours if nobody else is), so
  it also works over ledges and stairs.
- **Damage Estimate** — for HE: `~` damage you would take and the worst
  enemy would take at the predicted landing point (99 raw at the center,
  linear to zero at 350 u, times the 0.575 kevlar share). Standing in fire
  shows `you ~40 dps`. After a detonation the marker lingers 5 seconds
  showing what it actually got: `you -38  pv -71`.
- **Flash Helper** — while a flash is in the air, your own predicted blind
  percentage; when it pops, the worst enemy's percentage (angle bands:
  full white to 53°, fading past 72° / 101°, scaled down with distance and
  zero at 2300 u). Enemies currently flashed are tagged **FLASHED** over
  their head from the pawn's own flash timer, and the card header counts
  them.
- **Enemy Nades Only** — hides everything your own team threw (markers and
  results alike).
- **Draw Distance** slider (10–250 m) — how far out markers still render.

Everything lives in a small card in the free bottom-right corner (the radar
keeps the top): one line per grenade in the air, then the fading result
lines after detonations, or `no grenades in the air`. Offsets the helper
needs (`m_designerName`, `m_hThrower`, `m_angEyeAngles`,
`m_flFlashDuration`) schema-scan once on first use the way the C4 block
does; a missing one just turns its feature off rather than guessing. Saved
in configs as `gresp= grpath= grdmg= grflash= grenemy= grdist=`.

## Updating offsets

Offsets in `offsets.hpp` break on every CS2 update. They come from
[a2x/cs2-dumper](https://github.com/a2x/cs2-dumper):

- https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.hpp
- https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.hpp

Copy the changed `dw*` values (client.dll namespace) and netvar fields
(`m_*` inside the class namespaces) into `offsets.hpp`. The fields used:

| Field | Class |
|---|---|
| `dwEntityList`, `dwLocalPlayerPawn`, `dwViewMatrix` | client.dll offsets |
| `m_pGameSceneNode`, `m_iHealth`, `m_lifeState`, `m_iTeamNum` | `C_BaseEntity` |
| `m_vecAbsOrigin`, `m_bDormant` | `CGameSceneNode` |
| `m_vecViewOffset` | `C_BaseModelEntity` |
| `m_iszPlayerName`, `m_bIsLocalPlayerController` | `CBasePlayerController` |
| `m_hPlayerPawn`, `m_bPawnIsAlive` | `CCSPlayerController` |

Auto-bhop fields live in `bhop_offsets.hpp`: RIP-relative code signatures
for the `dw*` globals, schema-name specs for the netvar fields, and a
fallback table (seeded from the same dumper output — includes
`dwLocalPlayerController` and the controller state fields). The worker
tries the scan first and falls back to the table if the scan misses or a
candidate fails live validation — update the fallback values there after a
CS2 update if scanning ever comes up empty.
