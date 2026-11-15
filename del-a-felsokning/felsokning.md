# Hemuppgift 3, Del A: felsökning

## Problemet

En bugg som blev kvar från Del B: "ö" i sökvägar blir trasigt och visas som ett frågetecken i en ruta när jag kör `git janitor scan` på Windows. Mitt användarnamn är MartinHellström, så det syns ofta. I Del B skrev jag att det var git:s stderr som avkodades fel, men det hade jag aldrig kollat.

Jag återskapade det först med en worktree vars huvudrepo jag flyttat, i en mapp som heter `höst`:

```text
h�st/app-flyttad | master | keep | - | main working tree
h�st/app-x       | app-x  | keep | - | git failed: fatal: not a git repository: C:/Users/MartinHellstr�m/...
```

## Kontexten jag gav agenten

En ny agent med ren kontext, som bara fick läsa. Jag gav den:

- vad som hände och var jag såg det först (Reason-kolumnen när git misslyckas)
- när det kom: efter att git-fel började visas som en KEEP-rad i Del B
- att `subprocess.run` kör med `encoding="utf-8", errors="surrogateescape"` och att tabellen ritas med Rich
- miljön: Windows 10, git 2.38.1, Python 3.11, `locale.getpreferredencoding()` = cp1252, Git Bash
- utdatan ovan

Min egen teori om stderr skrev jag inte med, så att den inte skulle styra svaret.

## Agentens hypoteser

1. **stdout skrivs som cp1252 men terminalen läser UTF-8.** När stdout inte är en riktig Windows-konsol använder Python ANSI-teckentabellen. "ö" blir byten `0xF6`, som inte är giltig UTF-8. Agenten pekade på att Path-kolumnen också är trasig och den kommer inte från git, och att Rich ritar `|` i stället för `│`, vilket Rich gör när kodningen inte är UTF-8.
2. **git skriver stderr i en annan kodning än UTF-8.** Alltså min teori från Del B.
3. **Miljön ställer in fel kodning**, t.ex. `PYTHONIOENCODING` eller terminalens teckenuppsättning.

## Vilken jag valde och varför

Hypotes 1. Jag hade redan tittat på råbytena från git innan jag frågade, och där stod `f\xc3\xb6rsvunnen`, alltså korrekt UTF-8. Python fick rätt sträng. Det fällde hypotes 2. Hypotes 3 fällde jag med `env` (inget satt) och `printf 'h\xc3\xb6st'`, som visades rätt i terminalen.

Jag gick inte på hypotes 1 för att den stod först, utan för att de andra två gick att fälla på en minut.

## Vad som faktiskt var fel

Hypotes 1 stämde. `sys.stdout.encoding` är `cp1252` när utdatan går genom en pipe, vilket den gör i Git Bash, i appens terminal och när man pipar vidare i PowerShell. Med `PYTHONUTF8=1` blev allt rätt, även ramarna. I ett vanligt konsolfönster syns felet inte, där skriver Python redan UTF-8.

Fixen är att callbacken i `cli.py` byter stdout och stderr till UTF-8 innan något skrivs ut, samma kodning som git själv använder. Regressionstestet kör CLI:t som en egen process med pipad stdout och en mapp som heter `höst`. Det blev rött utan fixen. 60 tester gröna, ruff och mypy rena.

## Vad agenten fick rätt och vad den missade

**Rätt:**
- Rätt hypotes först, och den såg ledtråden i Path-kolumnen som jag själv inte hade tänkt på.
- Alla verifieringssteg gick att köra som de stod.
- I steg 2 listade den alla ställen som skriver ut, inklusive `typer.echo` till stderr. En fix bara i Rich hade alltså inte räckt.

**Missade eller fel:**
- Den sa att PowerShell oftast avkodar med cp850 och att en UTF-8-fix bara byter en sorts trasigt mot en annan. Hos mig är PowerShell 7 inställt på UTF-8, och där var det trasigt före fixen och rätt efter.
- Den nämnde inte att `reconfigure(encoding=...)` sätter `errors` till `strict` om man inte anger det. Ett tecken som inte går att koda hade då kraschat utskriften.
- Den sa inget om att ett test med `CliRunner` aldrig kan hitta buggen, eftersom runnern alltid kör UTF-8. Testet måste köra en riktig process.
- Mitt första test i appens PowerShell visade rätt tecken, eftersom `PYTHONIOENCODING=utf-8` var satt där. Hypotes 3 var alltså inte helt fel, den förklarade varför buggen bara syntes ibland.

**Fynd på vägen, inte åtgärdade:**
- En worktree vars huvudrepo har flyttats visas på två rader.
- `git janitor scan | head` ger en traceback när pipen stängs. Det fanns redan före fixen.

Det viktigaste jag tar med mig: min egen förklaring från Del B var fel, och det var den jag hade skrivit ner som sanning. Agenten var användbar mest för att den gav tre saker att fälla i stället för en att tro på.
