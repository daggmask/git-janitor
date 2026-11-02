# Del A: implementation med plan

Grenen `scan-and-delete`, ovanpå Del B. Två punkter som står som kvar i Del B stängs här: den oskyddade återställningen i rename-kontrollen och namnen på merge-fälten. Arbetet följde uppgiftens flöde: först analys utan lösning, sedan en plan i planläge som jag granskade, och sist implementation ett steg i taget med tester efter varje steg.

## Vad identifierade agenten?

Analysen gällde läsbarhet, duplicerad logik och teknisk skuld:

**Duplicerad logik**
- Felet från git formaterades på tre ställen, på två olika sätt (`clean.py` och `scan.py`). Samma fel såg alltså olika ut i scan och i delete.
- `--force` avgjordes två gånger: en gång i `scan.py` för analysen och en gång till i `clean.py` för att välja `git worktree remove --force`.
- Ålder i dagar räknades både i `analysis.py` och i `cli.py`.

**Läsbarhet**
- `commits_ahead` och `commits_not_in_target` såg ut att betyda samma sak. Det ena räknar på SHA, det andra på patch-id, och skillnaden är det som bevisar en rebase-merge.
- `remove_safe_worktrees` prunar också zombies, vilket namnet inte säger.
- `is_in_use_by_another_program` ser ut som en fråga men döper om användarens mapp.

**Teknisk skuld**
- Namnbytet tillbaka i rename-kontrollen var oskyddat. Om det misslyckades kraschade hela delete-körningen, och mappen blev liggande under ett tillfälligt namn.
- Layouten i CLAUDE.md saknade `scan.py` och `clean.py`.

## Vad ville agenten göra som jag stoppade, och varför?

Jag godkände planen som den var, utan att stryka något.

Agenten lät själv tre saker ligga och skrev in det i planen:
- **`git worktree move` före remove.** Förslaget kom från Del B. Om remove misslyckas efter flytten ligger worktreen kvar under ett nytt namn, och det är sämre än i dag. Agenten skyddade i stället det befintliga namnbytet.
- **Dela upp `scan_worktrees`.** Fem steg är fortfarande läsbart, och uppdelningen skulle röra de parallella anropen.
- **Slå ihop de två åldersfunktionerna.** Vinsten är liten för två rader, och formaten skiljer sig ("3 days ago" mot "3d ago").

## Vad missade den?

- **Att rename-kontrollen inte gör något på Linux och macOS.** Där går det att döpa om en mapp även när filer i den är öppna, så kontrollen svarar alltid "fri". Det kom fram i Del B men kom inte med i analysen.
- **Att steg 4 ändrar vad delete skriver ut.** Planen sa att stegen före steg 6 inte ändrar beteendet, men i steg 4 står att delete nu visar sista raden från git i stället för hela stderr. Det står i planen, men inte i inledningen till den.
- **Att "ö" i sökvägar blir trasigt i git:s felmeddelanden.** Det hittades i Del B och är fortfarande inte åtgärdat.

## Är projektet körbart efter implementationen?

Ja.

**Stegen:**

| Steg | Ändring | Tester efter steget |
|---|---|---|
| 2 | `commits_ahead_of_target` och `commits_without_patch_in_target` | 56 gröna |
| 3 | `remove_safe_and_prune_zombies` | 56 gröna |
| 4 | `GitError.last_line` används på alla tre ställena | 56 gröna |
| 5 | `Verdict.is_forced`, så clean tar inte längre emot `forced_paths`. Två nya tester, ett för `last_line` och ett för `is_forced` | 58 gröna |
| 6 | `check_folder_free_by_renaming` returnerar en orsak och kraschar inte när namnbytet tillbaka misslyckas | 59 gröna |
| 7 | Layouten i CLAUDE.md | 59 gröna |

**Kontroller:**
- `ruff check`, `ruff format --check` och `mypy src` är rena efter varje steg.
- För steg 5 och 6 backade jag ändringen tillfälligt och såg att testet blev rött:
  - Steg 5: `test_force_is_per_folder` blev rött när clean struntade i `is_forced`.
  - Steg 6: det nya testet blev rött utan skyddet.

**Körning av CLI:t** mot en temporär mapp med en ren, en smutsig, en forcerad och en låst worktree:
- Dry run gav exakt samma tabell före och efter ändringarna (`diff` utan skillnad).
- Med `--delete` togs `app-fresh` och `app-forced` bort, medan `app-dirty` och den låsta `app-usb` låg kvar, både som mappar och i `git worktree list`.

```text
app-dirty  | dirty  | keep   |       today | uncommitted changes in 1 file
app-forced | forced | safe   |       today | forced with --force
app-fresh  | fresh  | safe   |       today | already in origin/main
app-usb    | usb    | keep   |       today | worktree is locked
removed app-forced
removed app-fresh
```
