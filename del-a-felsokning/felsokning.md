# Hemuppgift 3, Del A: felsökning

## Problemet

En bugg som blev kvar från Del B: "ö" i sökvägar visas som ett frågetecken i en ruta när jag kör `git janitor scan` i Git Bash på Windows. I Del B skrev jag att git:s stderr avkodades fel, men det hade jag aldrig kollat. Jag återskapade det med en mapp som heter `höst` och ett huvudrepo som jag flyttat:

```text
h�st/app-x | app-x | keep | - | git failed: fatal: not a git repository: C:/Users/MartinHellstr�m/...
```

## Kontexten jag gav agenten

En ny agent som bara fick läsa. Jag skrev vad som hände, att jag först såg det i Reason-kolumnen efter att git-fel började visas som en KEEP-rad i Del B, att git körs med `encoding="utf-8", errors="surrogateescape"` och att tabellen ritas med Rich. Jag gav också miljön (Windows 10, git 2.38, Python 3.11, `locale.getpreferredencoding()` = cp1252, Git Bash) och utdatan. Min egen teori lämnade jag utanför. Sedan körde jag Steg 1-prompten ordagrant.

## Agentens hypoteser

1. **stdout skrivs som cp1252 men terminalen läser UTF-8.** När stdout går till en pipe och inte till en Windows-konsol väljer Python ANSI-teckentabellen, och "ö" blir byten `0xF6`. Agenten pekade på att Path-kolumnen också är trasig fast den inte kommer från git, och att Rich ritar `|` i stället för `│`. Verifiering: `sys.stdout.encoding`, råbytena i utdatan och en körning med `PYTHONUTF8=1`.
2. **git skriver stderr i en annan kodning än UTF-8.** Då blir "ö" ett surrogattecken redan i `GitError`. Verifiering: läs git:s stderr som bytes.
3. **Miljön ställer in fel kodning,** via `PYTHONIOENCODING` eller terminalens teckenuppsättning. Verifiering: `env` och `printf 'h\xc3\xb6st'` i terminalen.

## Vilken jag valde och varför

Hypotes 1, men inte för att den stod först. Jag körde verifieringen för de andra två och fällde dem. Git:s stderr innehöll `h\xc3\xb6st`, alltså korrekt UTF-8. Inga variabler var satta i Git Bash, och terminalen visade `printf`-testet rätt. Kvar blev hypotes 1.

I Steg 2 frågade jag vilka filer och funktioner jag skulle undersöka. Agenten pekade på callbacken `main` i `cli.py`, som är det enda som körs före alla kommandon, och listade alla ställen som skriver ut. Det gällde både Rich-tabellen och `typer.echo` till stderr. En fix bara i Rich hade alltså inte räckt.

## Vad som faktiskt var fel

Hypotes 1 stämde. `sys.stdout.encoding` var `cp1252` i Git Bash. Med `PYTHONUTF8=1` blev både "ö" och ramarna rätt. Buggen har troligen funnits från början. Den syntes först i Del B, eftersom det var första gången en sökväg utanför den skannade mappen hamnade i tabellen.

Fixen: callbacken byter stdout och stderr till UTF-8, samma kodning som git använder. Regressionstestet kör CLI:t som en egen process med pipad stdout och mappen `höst`. Utan fixen blir det rött på Windows. På Linux och macOS är det grönt ändå. 60 tester gröna, ruff och mypy rena.

## Vad agenten fick rätt och vad den missade

**Rätt:** rätt hypotes först, och ledtråden i Path-kolumnen, som jag inte hade sett. Alla verifieringssteg gick att köra som de stod. I Steg 2 hittade den även stderr. Hypotes 3 förklarade dessutom varför buggen bara syntes ibland: appens PowerShell har `PYTHONIOENCODING=utf-8` satt, så där såg allt rätt ut.

**Missade:**
- `reconfigure(encoding=...)` sätter `errors` till `strict` om man inte anger det. git-text som avkodats med `surrogateescape` kan innehålla surrogattecken, och då hade utskriften kraschat. Jag satte `backslashreplace`.
- Den sa inget om att `CliRunner` som standard kör UTF-8 och därför aldrig kan hitta buggen. Testet måste köra en riktig process.
- Agenten varnade för att PowerShell med standardinställning avkodar pipad utdata som cp850, så där hjälper inte UTF-8. Det har den troligen rätt i. Jag kunde inte testa det, eftersom min PowerShell är omställd till UTF-8.

Det jag tar med mig är att min förklaring från Del B var fel, och att jag hade skrivit ner den som sanning. Agenten var mest till nytta för att den gav mig tre saker att fälla i stället för en att tro på.
