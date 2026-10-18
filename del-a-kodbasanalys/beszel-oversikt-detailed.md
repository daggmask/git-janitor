# Beszel - projektöversikt (detailed)

Genomgång av forken `daggmask/beszel_fork` (upstream `henrygd/beszel`), version 0.21.0, gjord 2026-10-16 på commit `e8970e46`.

## 1. Vad projektet är

Beszel är ett lättviktigt verktyg för serverövervakning. Det samlar in mätvärden från maskiner och containrar, sparar historik, visar grafer i ett webbgränssnitt och skickar larm.

Projektet är skrivet i Go med ett React-gränssnitt. Det är inget .NET-projekt. Den enda .NET-koden är en liten hjälpare för sensorer på Windows (`agent/lhm`).

Historiken omfattar cirka 1 800 commits, och den absoluta merparten kommer från upphovsmannen (henrygd / Henry Dollman).

## 2. Komponenter

| Del | Katalog | Teknik | Ansvar |
|---|---|---|---|
| Agent | `agent/` | Go | Körs på varje övervakad maskin och samlar in mätvärden. |
| Hub | `internal/hub/` | Go + PocketBase | Hämtar data från agenterna, lagrar den, kör larm, erbjuder ett API och serverar gränssnittet. |
| Webbgränssnitt | `internal/site/` | React 19, Vite, Tailwind, Radix/shadcn, Recharts, nanostores, Lingui | Dashboard, systemsidor, inställningar. Bäddas in i hubbens binär. |
| Delade typer | `internal/entities/`, `internal/common/` | Go | Datatyper och protokollkonstanter som både agent och hub använder. |
| Larm | `internal/alerts/` | Go + shoutrrr | Tröskellarm och notiser (Slack, Discord, e-post, webhooks med flera). |
| Historik | `internal/records/` | Go | Nedsampling och rensning av historiska poster. |
| Migreringar | `internal/migrations/` | Go | PocketBase-schema (snapshot från 0.20.0 plus inkrementella migreringar). |
| Ingångspunkter | `internal/cmd/hub`, `internal/cmd/agent` | Go + cobra | CLI för hubben och agenten. |
| Windows-sensorer | `agent/lhm/` | C# (.NET Framework 4.8) | Wrapper runt LibreHardwareMonitor som agenten bäddar in och startar. |

### Vad agenten samlar in

CPU, minne (inklusive swap och ZFS ARC), disk och disk-I/O, nätverk, load average, temperaturer, fläktar, GPU (Nvidia via NVML, AMD, Intel och Apple), batteri, Docker/Podman-containrar, S.M.A.R.T. (inklusive eMMC och mdraid), ZFS-pooler och dataset, systemd-tjänster, väntande paketuppdateringar, WiFi samt nätverksprober (ping, HTTP och TLS-certifikat).

Plattformsspecifik kod ligger i separata filer med suffix som `_linux.go`, `_windows.go`, `_darwin.go`, `_freebsd.go` och `_unsupported.go`, kombinerat med build-tags (till exempel `glibc` för NVML).

## 3. Så fungerar det

### 3.1 Anslutning mellan agent och hub

Det finns två transportvägar bakom samma gränssnitt, `Transport` i `internal/hub/transport/transport.go`:

1. **WebSocket (förstahandsval).** Agenten ansluter själv till hubben och skickar en token och ett fingeravtryck (`internal/hub/agent_connect.go`). Tokens kan vara per system eller "universal tokens" som används för automatisk registrering.
2. **SSH (reservväg).** Hubben ansluter till agentens inbyggda SSH-server och autentiserar sig med en ed25519-nyckel som den genererar själv första gången (`Hub.GetSSHKey`). Agenten släpper bara in hubbens publika nyckel.

På agentsidan håller `ConnectionManager` (`agent/connection_manager.go`) reda på tillståndet (Disconnected, WebSocketConnected eller SSHConnected) och försöker ansluta via WebSocket var tionde sekund.

Meddelandena kodas med CBOR. Hubben kan fortfarande läsa svar från äldre agenter (0.18 och tidigare) via `unmarshalLegacyResponse`.

### 3.2 Insamlingsloopen

- `SystemManager` startar en goroutine per system (`System.StartUpdater`, `internal/hub/systems/system.go`).
- Med en ticker anropas `update()` ungefär en gång i minuten. Ett slumpmässigt jitter förhindrar att alla agenter körs samtidigt efter en omstart.
- Utan WebSocket-anslutning väntar hubben 11 sekunder innan den går över till SSH, så att agenten hinner ringa upp själv.
- Systemdetaljer som inte ändras (OS, CPU-modell och liknande) hämtas bara en gång per anslutning.
- S.M.A.R.T.- och ZFS-data hämtas mer sällan (standard en timme) i separata goroutines som skyddas med `CompareAndSwap`.
- Om agenten är långsam pingar hubben anslutningen så att den lever vidare, men bara tills tiden `maxAgentSilence` har gått.

### 3.3 Lagring och nedsampling

- PocketBase lagrar allt i SQLite. Viktiga collections är `systems`, `system_stats`, `container_stats`, `network_monitor_stats`, `alerts`, `alerts_history`, `user_settings` och `universal_tokens`.
- Varje insamling ger en post av typen `1m`.
- Cron-jobbet `create longer records` (var tionde minut, `internal/records/records.go`) räknar fram medelvärden i stegen 1m till 10m, 10m till 20m, 20m till 120m och 120m till 480m. Det körs i en transaktion.
- Cron-jobbet `delete old records` (varje timme, `records_deletion.go`) rensar gamla poster per typ.
- Resultatet är att databasen hålls liten och att grafer över långa perioder går snabbt att läsa.

### 3.4 Larm

`internal/alerts/` innehåller larm per mått: status (up/down), CPU, minne, disk, temperatur, batteri, containrar, systemd, S.M.A.R.T., ZFS och nätverksprober. Där finns också tysta timmar, en larmhistorik och en cache för aktiva larm. Notiserna skickas via shoutrrr och webhooks.

### 3.5 Användare och behörighet

PocketBase sköter autentisering (lösenord, OAuth2/OIDC och OTP). Roller sätts när användare skapas (`internal/users`). Användare äger sina egna system, och administratörer kan dela system mellan användare.

### 3.6 Webbgränssnittet

- En single-page-app som byggs med Vite till `internal/site/dist` och bäddas in via `//go:embed all:dist`.
- Routing och state hanteras med nanostores. Data hämtas via PocketBase SDK med realtidsprenumerationer (`src/lib/systemsManager.ts`).
- Stora tabeller använder TanStack Table och virtualisering.
- Översättningar sköts med Lingui och Crowdin (runt 40 språk i `src/locales`).
- Biome används som linter och formatterare.

### 3.7 Bygge och release

- Makefile-målen är `build-agent`, `build-hub`, `build-web-ui`, `dev`, `test` och `lint`.
- På Windows kräver agenten `dotnet build` av `agent/lhm` och att `smartctl.exe` hämtas via `go generate` (verifieras med SHA256).
- GoReleaser bygger releaser för många OS och arkitekturer. Docker-images och Helm-charts byggs i GitHub Actions.

## 4. Storlek

| Mått | Värde |
|---|---|
| Go, produktionskod | ca 31 900 rader |
| Go, testkod | ca 39 000 rader |
| TypeScript/TSX | ca 23 800 rader |
| Största Go-filerna | `migrations/0_collections_snapshot_0_20_0.go` (2 315), `agent/smart.go` (1 232), `hub/systems/system.go` (1 135), `agent/docker.go` (1 052) |
| Största TSX-filerna | `monitor-dialog.tsx` (979), `network-monitors-table.tsx` (879), `smart-table.tsx` (866), `systems-table-columns.tsx` (831) |

## 5. Det som är bra

- **Tydlig uppdelning.** Agent, hub, transport, larm, historik och delade typer ligger i separata paket med tydliga gränser.
- **Transportabstraktion.** WebSocket och SSH används på samma sätt, och hubben byter väg automatiskt när något fallerar.
- **Mycket tester.** Det finns fler rader test än produktionskod. Testerna innehåller fixtures med riktig utdata (smartctl, ZFS, paketuppdateringar) och använder `testing/synctest` för tidsberoende logik.
- **Bakåtkompatibilitet.** Gamla agenter och hubbar fungerar fortfarande tack vare `migrateDeprecatedFields` och de äldre svarsformaten.
- **Driftsäkerhet.** Jitter, timeouts, återförsök, keepalive-pingar, transaktioner runt nedsamplingen och skydd mot parallella hämtningar.
- **Enkel driftsättning.** En binär innehåller både databas, API och gränssnitt. Agenten är liten och använder få resurser.
- **Nedsampling.** Lagringsbehovet växer långsamt även med många system.

## 6. Det som är mindre bra

### 6.1 CI kör inte testerna

Workflows i `.github/workflows` bygger releaser, images och Helm-charts och kör `govulncheck`. Men varken `go test` eller `golangci-lint` körs. Den stora testsviten skyddar alltså bara den som kör den lokalt.

**Förslag:** Lägg till ett workflow som kör `go test -tags='testing no_ui' ./...` på Linux (och gärna `golangci-lint run`) för varje PR.

### 6.2 Hubben kontrollerar inte agentens SSH host key

`internal/hub/systems/system_manager.go:415` använder `ssh.InsecureIgnoreHostKey()`. Agenten kontrollerar hubbens nyckel, men hubben kontrollerar inte agentens. Över SSH-vägen kan en man-in-the-middle därför ge hubben falsk data. WebSocket-vägen skyddas av fingeravtrycket.

**Förslag:** Spara agentens host key första gången hubben ansluter (trust on first use) och jämför vid senare anslutningar.

`InsecureSkipVerify` i agentens nätverksprober är avsiktligt. Det används för certifikatinspektion och för en opt-in-flagga per monitor, så det är inget problem.

### 6.3 Stora filer och structar

Flera filer är på över 1 000 rader, och `Agent`-structen har ett trettiotal fält. Sex React-komponenter ligger på 700 till 980 rader. Koden är läsbar, men det blir svårare att granska och ändra i den.

### 6.4 Teknisk skuld från versionsövergångar

- TODO:s om att sluta fylla i fält som markerades som föråldrade i 0.18 och 0.19 (`agent/docker.go`, `internal/entities/system/system.go`).
- Paketet `entities/system` beskriver själv sin struktur som "confusing".
- `TODO: move to users package` i `hub.go`.

### 6.5 Hård koppling till PocketBase

Domänlogiken anropar `core.App` och skriver SQL direkt med `dbx` (till exempel `SELECT id FROM systems WHERE status='up'`). Det är enkelt och snabbt, men det går inte att byta ramverk utan omfattande ändringar, och logiken blir svårare att testa utan en fullständig testapp.

### 6.6 Frontend

- Få tester (några `.test.ts` i `src/lib` och `tests/`). Nästan all testning sker på Go-sidan.
- Ett 40-tal `: any`.
- `src/lib/time.ts` är tom.

### 6.7 Testerna förutsätter Linux

Sex agenttester fallerar på Windows av rent miljömässiga skäl (se avsnitt 7). Det är inget allvarligt problem, men det försvårar för den som utvecklar på Windows.

## 7. Testkörning på den här maskinen

### Installerat

| Verktyg | Version | Hur |
|---|---|---|
| Go | 1.27.0 via winget, 1.27.2 hämtas automatiskt (`GOTOOLCHAIN=auto`) | `winget install GoLang.Go` |
| Go-moduler | enligt `go.mod` | `go mod download` |
| .NET SDK | fanns redan (6 till 10) | - |

### Förberedande byggsteg

Följande krävs för att paketen ska kompilera. Alla resultat ignoreras av git.

| Steg | Varför |
|---|---|
| Tom `internal/site/dist/index.html` | `//go:embed all:dist` kräver katalogen. Makefilen gör likadant när gränssnittet inte byggs. |
| `dotnet build -c Release ./agent/lhm/beszel_lhm.csproj` | `sensors_windows.go` bäddar in `lhm/bin/Release/net48`. |
| `go generate -run fetchsmartctl ./agent` | `smart_windows.go` bäddar in `smartctl.exe` (hämtas från static.beszel.dev och verifieras med SHA256). |

### Resultat

Kommando: `go test -tags='testing no_ui' ./...` (samma som `make test`).

| Paket | Resultat |
|---|---|
| `internal/alerts` | ok (97 s) |
| `internal/hub` | ok |
| `internal/hub/systems` | ok |
| `internal/hub/config`, `heartbeat`, `transport`, `ws`, `expirymap` | ok |
| `internal/records` | ok |
| `internal/users`, `internal/tests`, `internal/ghupdate` | ok |
| `internal/entities/*` | ok |
| `internal/cmd/agent` | ok |
| `agent/battery`, `deltatracker`, `health`, `utils`, `wifi`, `zfs` | ok |
| `agent` | **6 tester fallerar** |

### De fallerande agenttesterna

| Test | Orsak | Bedömning |
|---|---|---|
| `TestReadHwmonFansLegacyParent` | `os.Symlink` misslyckas: "A required privilege is not held by the client" | Windows kräver administratörsrättigheter eller Developer Mode för symlänkar. |
| `TestSkipGpuSensorShadow` | samma symlänksfel | samma |
| `TestSkipGpuSensorShadowDeviceName` | samma symlänksfel | samma |
| `TestSkipGpuSensorShadowKeepsThermalZonesWithoutNonGpuHwmon` | samma symlänksfel | samma |
| `TestBuildFsStatRegistration` | förväntar sig `dm-1`, får `volume_1` / `sda` | Testet använder Linux-sökvägar (`/dev/vg1/volume_1`). Troligen omvandlar Windows sökvägarna så att den mockade symlänksupplösningen aldrig träffar. |
| `TestLegacyHubGetsSinglePayload` | "Condition never satisfied" i väntan på en Unix-socket (`net.Dial("unix", ...)`) | Testet startar agentens server på en Unix-socket, vilket inte fungerar på samma sätt på Windows. |

**Slutsats:** Ingen av felorsakerna pekar på en bugg i produktionskoden. Alla beror på att testerna förutsätter Linux. Det har inte bekräftats genom en körning på Linux.

**Nästa steg:** Kör sviten i WSL eller en Linux-container för en ren baslinje. Alternativt kan testerna ges `//go:build linux`, eller `t.Skip` när symlänkar inte stöds.

## 8. Snabbreferens

```bash
# kör alla Go-tester (Linux/WSL)
make test

# kör på Windows utan make
go test -tags='testing no_ui' ./...

# utvecklingsläge, hub + gränssnitt
make dev

# bygg gränssnittet
cd internal/site && bun install && bun run build
```
