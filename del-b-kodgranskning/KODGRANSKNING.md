# Del B: kodgranskning av git-janitor

Granskat på grenen `scan-and-delete`, där koden finns (main har bara CLAUDE.md och Del A).

Varje prompt kördes som en egen agent med ren kontext, så att granskningarna inte påverkade varandra. Sedan läste jag själv koden mot varje fynd och testade de viktigaste genom att köra dem. Därefter gick jag en andra runda med varje agent inom samma område: jag lade fram det jag hittat som motbevis och bad dem granska mina fixar. Radnumren gäller koden före mina ändringar.

## Prompterna

```text
Granska kodbasen mot de arkitekturprinciper jag definierat i CLAUDE.md. Var bryter koden mot principerna? Var är den i linje med dem? Ge konkreta filreferenser.
```

```text
Gå igenom kodbasen och leta efter: hårdkodade hemligheter eller uppgifter, saknad inputvalidering, injection-risker (SQL, kommando, path traversal), känsliga data i loggar, och osäkra standardvärden. Lista varje fynd med filnamn och radnummer.
```

```text
Identifiera: funktioner som gör mer än en sak, otydlig namngivning (variabler, funktioner, klasser), saknad felhantering för externa anrop, och kod som är svår att läsa utan kommentarer. Lista de fem allvarligaste problemen.
```

Till varje prompt lade jag till att agenten bara fick läsa och inte ändra något, att varje påstående måste ha fil och rad som den faktiskt läst, och att den skulle säga hur säker den är.

## 1. Arkitektur

### I linje med CLAUDE.md

- `analysis.py` är ren. Den tar dataclasses in och ger dataclasses ut, och tiden skickas in som `now`.
- All I/O går via `git.py` och `fs.py`. `scan.py` och `clean.py` saknas i layouten i CLAUDE.md, men de orkestrerar bara och kör inga processer själva.
- `subprocess.run` får en argumentlista, `encoding="utf-8"` och en explicit kontroll av returkoden.
- Porcelain används: `worktree list --porcelain`, `status --porcelain=v2`, `--format`.
- Dry run är default, `--force` gäller per mapp, borttagning sker med `git worktree remove` och huvudträdet skyddas på tre ställen.
- Squash räknas bara som merge när det finns en patch-id-träff. Ålder räcker aldrig.

### Bryter mot

| Fynd | Var | Bedömning |
|---|---|---|
| En låst worktree vars mapp är borta blev ZOMBIE. `git worktree prune` hoppar över låsta poster, men verktyget skrev ändå "removed". Orsaken var alltså fel. | `analysis.py:22-25`, `clean.py:27-30` | Bekräftat. **Åtgärdat.** |
| `branch_diff_patch_id` och `target_commit_patch_ids` kör två git-kommandon var, trots "one git call per question". | `git.py:144-156` | Bekräftat. Kvar. Det är en pipeline (`diff` till `patch-id`), så det är rimligt men bryter mot regeln. |
| `last_commit_time` sväljer alla `GitError` och tolkar dem som "ingen commit". | `git.py:96-102` | Bekräftat, låg risk. Kvar. |
| `stash list --format=%gs` parsas som fritext ("WIP on ", "On "). | `git.py:119-131` | Bekräftat. Kvar. |
| En `--target` som inte finns tas bort tyst, och orsaken säger "use --target" fast användaren redan angett det. | `scan.py:74-78` | Bekräftat. Kvar. |
| `--json` saknas. | `cli.py` | Lucka, inte fel. Kvar. |
| `Path.resolve()` utanför `fs.py`. | `clean.py`, `scan.py`, `cli.py` | Strikt tolkning. Struket, och agenten höll med i andra rundan. |

## 2. Säkerhet

| Fynd | Var | Bedömning |
|---|---|---|
| Git körs i varje repo under roten, och repots egen `.git/config` kan få git att starta program. `core.fsmonitor` körs vid `git status`, `diff.*.textconv` vid `diff` och `log -p`, och `log.showSignature` + `gpg.program` redan vid `log -1`. Att skanna en uppackad zip räcker. | `git.py:92`, `git.py:98`, `git.py:145`, `git.py:152` | Alla tre bekräftade genom körning. **Åtgärdat.** |
| `filter.<namn>.clean` körs också vid `git status`. | `git.py:92` | Bekräftat genom körning. Kvar. Filter går inte att stänga av utan att veta vad de heter. |
| Scanningen följer Windows-junctions ut ur roten. `is_dir(follow_symlinks=False)` stoppar symlänkar men inte junctions. | `fs.py:35` | Bekräftat genom körning. Kvar. `is_junction()` finns först i Python 3.12. |
| Inget hindrar att en worktree utanför roten tas bort. Sökvägarna kommer från huvudrepots `worktree list`. | `clean.py:11-15` | Bekräftat. Kvar. git tar ändå bara bort mappar som är riktiga worktrees. |
| `is_in_use_by_another_program` döper om mappen för att testa den. Misslyckas namnbytet tillbaka blir mappen kvar som `x.janitor-<pid>`. | `fs.py:57-63` | Bekräftat. Kvar. |
| Branch- och mappnamn skrivs ut som Rich-markup. Ett namn med `[/]` kan krascha utskriften. | `cli.py:111`, `cli.py:128-134` | Bekräftat, bara visuellt. Kvar. |
| `--target` skickas till git utan `--end-of-options`. | `git.py:140`, `git.py:145` | Teoretiskt. `rev-parse --verify` stoppar värden som `--output=...` först. Kvar. |
| CI: actions låsta på major-tagg och inget `permissions:`-block. | `ci.yml` | Låg. Kvar. |
| Hårdkodade hemligheter, känsliga data i loggar, osäkra defaults | | Inget hittat. |

## 3. Kodkvalitet

| Fynd | Var | Bedömning |
|---|---|---|
| En trasig mapp stoppade hela scanningen. En kvarlämnad worktree vars huvudrepo är flyttat ger `GitError`, och då avslutades allt med exit 1 utan tabell. Det är just de mapparna verktyget finns till för. | `scan.py:31`, `cli.py:70` | Bekräftat. **Åtgärdat.** |
| Saknas git på PATH, eller försvinner en mapp mitt i scanningen, blir det en Python-traceback. | `git.py:23` | Bekräftat. **Åtgärdat** i andra rundan. |
| `(folder / ".git").exists()` ligger utanför `try` och kan kasta `PermissionError`. | `fs.py:19` | Bekräftat i koden. Kvar. |
| `is_in_use_by_another_program` heter `is_` men döper om mappen, och återställningen är oskyddad. | `fs.py:57-63` | Bekräftat. Kvar, se nedan. |
| `commits_ahead` och `commits_not_in_target` ser ut att betyda samma sak. Det ena jämför på SHA och det andra på patch-id. | `models.py:29-30`, `analysis.py:48-51` | Bekräftat. Kvar. Bra kandidat för namnbyte. |

## Andra rundan

**Arkitektur.** Agenten granskade mina fixar och hittade två svagheter:
- En trasig mapp skyddades bara av ordningen i `analysis.py` och av en hårdkodad `folder_exists=True`. Nu kollas `git_failure` direkt efter `is_main`.
- Namnet `SKIP_COMMANDS_FROM_REPO_CONFIG` lovade mer än det höll. Det heter nu `TURN_OFF_FSMONITOR_AND_SIGNATURE_CHECKS`.

Agenten drog tillbaka fyndet om låsta zombies, eftersom det var fixat.

**Säkerhet.** Agenten pekade ut `log.showSignature` + `gpg.program`. Jag testade det, det stämde, och fixen täcker nu det också. Junction-fyndet var bara en misstanke i första rundan, men jag har nu bekräftat det genom körning.

**Kodkvalitet.** Två fynd:
- Jag visade agenten att dess förslag att ta bort rename-kontrollen inte håller på Windows. Den bytte då till `git worktree move` före `remove`. Det tar bort den oskyddade återställningen, men kontrollen ändrar då beteende, så jag har inte gjort det här.
- Båda agenterna såg att mitt `try` i `_load_repository` var för brett: ett fel i `stash list` dolde alla worktrees i repot. Nu gäller det första `try` bara `list_worktrees`, och vid övriga fel visas repots worktrees som KEEP.

## Vad jag åtgärdade

**Arkitektur: låst worktree med borttagen mapp.** `analysis.py` kollar nu `is_locked` före `folder_exists`. En låst worktree på en urkopplad USB-disk blir KEEP med orsaken "worktree is locked", och verktyget påstår inte längre att den tagits bort.

**Säkerhet: skannade repon får inte köra program via fsmonitor, textconv eller signaturkontroll.** Alla git-anrop går nu med `-c core.fsmonitor=false -c log.showSignature=false`, och `diff` och `log -p` har fått `--no-textconv`. Patch-id räknas därmed på den riktiga diffen och inte på textconv-utdata. Filter är inte täckta, se ovan.

**Kodkvalitet: en trasig mapp stoppar inte scanningen.** Ett `GitError` för en mapp eller en worktree blir nu en KEEP-rad med orsaken "git failed: <sista raden från git>". Resten av tabellen visas som vanligt. En saknad git eller en mapp som försvinner ger samma sak i stället för en traceback. Ett git-fel ger aldrig SAFE, inte ens med `--force`.

## Vad agenterna missade eller hade fel i

- Kvalitetsagenten föreslog att ta bort rename-kontrollen i `fs.py` och lita på att `git worktree remove` misslyckas. Det håller inte på Windows. Jag testade med en fil öppen i en temporär worktree: git gav rc 255, men `a.txt`, `b.txt` och `.git` var redan raderade. Kvar blev en trasig worktree. Det är därför kontrollen finns.
- Säkerhetsagenten föreslog `core.hooksPath`. Inget av de git-kommandon verktyget kör startar hooks, så det skulle inte göra någon skillnad. Det sa agenten själv i samma stycke.
- Ingen av agenterna såg att git:s stderr avkodas fel på Windows. "ö" i sökvägen blir trasigt i felmeddelandet. Det syntes först när jag körde verktyget på riktigt.
- Mitt eget första gpg-test blev grönt även utan fixen, så det testade ingenting. `gpg.program` körs direkt och inte via ett skal, så testet behövde ett körbart skript. Jag hittade det genom att backa fixen och köra testet igen.

## Verifiering

- Åtta nya tester: två enhetstester i `test_analysis.py` och sex integrationstester mot temporära repon i `test_git.py`. Jag backade varje fix tillfälligt och såg att testerna blev röda.
- `pytest`: 56 passerade (48 före).
- `ruff check`, `ruff format --check` och `mypy src` är rena.
- Körde CLI:t mot en temporär mapp med en frisk worktree, en låst worktree med borttagen mapp och en trasig mapp:

```text
Path      | Branch | Status | Last commit | Reason
app       | main   | keep   |           - | main working tree
app-fresh | fresh  | safe   |       today | already in origin/main
app-usb   | usb    | keep   |           - | worktree is locked
orphan    | -      | keep   |           - | git failed: fatal: not a git repository: ...
Dry run. 1 safe to remove, 0 zombies to prune. Add --delete to do it.
```

Före ändringen gav samma mapp bara `error: ...` och exit 1. Utan git på PATH blir alla rader KEEP med "git failed: [WinError 2] ..." i stället för en traceback.
