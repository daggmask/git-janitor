# Teknisk analys: Beszel (fork)

## Prompt

Steg 2, den genomtänkta prompten. Skickad så här i en ny session, utan följdfrågor:

```text
Teknisk analys av ett kodprojekt
Analysera det lokala GitHub-repot som om du vore en utvecklare som precis har börjat i teamet. Jag vill förstå hur projektet är uppbyggt, hur det fungerar och vilka delar som kan vara problematiska.
Börja med att gå igenom katalogstrukturen och läs sedan den relevanta koden, konfigurationen, beroendena, testerna och dokumentationen. Följ viktiga kodflöden mellan modulerna i stället för att bara dra slutsatser från filnamn eller README-filen.
Hänvisa till relevanta filer och funktioner när du förklarar hur något fungerar. Skilj mellan sådant du har kunnat bekräfta i koden och sådant du bara misstänker. Om du inte kan fastställa något ska du säga det. Om projektet är för stort för att undersöka helt, fokusera på de viktigaste delarna och ange vad du inte har granskat.
Ändra inga filer och kör inga destruktiva kommandon. Ta inte med hemligheter eller känsliga värden från konfigurationsfiler.
1. Arkitektur och struktur

* Vad gör projektet och vem är det till för?
* Vilken typ av applikation är det?
* Vilka är de viktigaste modulerna och katalogerna, och vad ansvarar de för?
* Hur går flödet genom applikationen från början till slut?
* Hur kommunicerar de olika delarna med varandra?
* Finns det tydliga arkitekturmönster? Visa var de syns i koden.

2. Externa beroenden
Identifiera de tre viktigaste externa beroendena.
För varje beroende, förklara vad det används till, var det förekommer i koden och hur viktigt det är för projektet. Bedöm också om det skulle vara enkelt eller svårt att ersätta.
Skilj mellan direkta beroenden och beroenden som kommer via andra paket. Ta även upp viktiga verktyg för utveckling och testning.
3. Integrationer mot externa system

* Vilka externa system använder projektet, exempelvis databaser, API:er, molntjänster eller meddelandeköer?
* Var finns koden för dessa integrationer?
* Hur sker kommunikationen och vilka bibliotek eller protokoll används?
* Hur hanteras autentisering, konfiguration och fel?
* Vilka integrationer är nödvändiga för att projektet ska fungera?

Kontrollera att integrationerna faktiskt används i koden och inte bara nämns i dokumentationen.
4. Affärslogik och centrala kodflöden

* Var finns projektets viktigaste logik?
* Vilka funktioner, klasser eller moduler hanterar centrala regler och beslut?
* Hur är logiken separerad från exempelvis datalagring, API:er och presentation?
* Beskriv ett eller två viktiga kodflöden steg för steg och hänvisa till filerna.
* Vilka delar går att ändra relativt enkelt, och vilka riskerar att påverka resten av systemet?

Om projektet inte har traditionell affärslogik, fokusera på dess centrala funktionalitet.
5. Teknisk skuld och problem
Leta efter konkreta problem, till exempel:

* Moduler som är starkt beroende av varandra eller har otydliga ansvarsområden.
* Duplicerad kod eller kod som är svår att testa.
* Bristande felhantering.
* Otillräckliga tester.
* Problem med konfiguration eller hantering av känslig information.
* Föråldrade eller riskfyllda beroenden.
* Bristfällig dokumentation eller en komplicerad utvecklingsmiljö.

För varje problem du hittar, beskriv vad som är fel, var det finns, vilka konsekvenser det kan få och hur det skulle kunna åtgärdas. Ange också hur säker du är på bedömningen.
Skilj mellan faktiska problem och möjliga risker. Ta inte upp något som ett problem enbart för att det skiljer sig från hur du själv skulle ha byggt systemet.
Sammanställning
Presentera analysen i följande ordning:

1. Projektöversikt: Vad projektet gör och vem det riktar sig till.
2. Arkitektur: Hur de viktigaste delarna hänger ihop.
3. Tekniska beroenden: De tre viktigaste beroendena och vad de används till.
4. Integrationer: Vilka externa system projektet kommunicerar med.
5. Affärslogik: Var den centrala logiken finns och hur den fungerar.
6. Tekniska problem: De viktigaste riskerna och möjliga förbättringarna.
7. Att lära sig först: Vad en ny utvecklare bör förstå innan den börjar ändra kod.
8. Osäkerheter: Vad som inte gick att fastställa och vad som behöver kontrolleras manuellt.

Håll analysen konkret och undvik allmänna beskrivningar som inte stöds av koden. Avsluta med de fem viktigaste sakerna att förstå innan du börjar arbeta med projektet.
```

---

Analysen bygger på en genomläsning av koden i `main` (senaste commit `e8970e46`, version `0.21.0` i [beszel.go](beszel.go)). Go och Bun finns inte installerade på maskinen där analysen gjordes, så **inga tester eller byggen har körts**. Allt nedan kommer från att läsa koden. Märkningen används så här:

- **Bekräftat**: jag har sett det i koden.
- **Misstanke**: rimlig slutsats men inte verifierad genom körning.
- **Okänt**: gick inte att fastställa.

Inga hemligheter eller värden från konfigurationsfiler återges.

---

## 1. Projektöversikt

Beszel är en lättviktig plattform för serverövervakning: CPU, minne, disk, nätverk, temperaturer, GPU, Docker/Podman-containrar, systemd-tjänster, S.M.A.R.T., ZFS, batteri, WiFi och nätverksmonitorer (ping/HTTP/TLS-certifikat). Den har historik, larm och notifieringar ([readme.md](readme.md)).

Målgruppen är hemmalabb-användare och mindre driftteam som vill ha något enklare och snålare än Prometheus/Grafana. MIT-licens, ett community-projekt med en huvudsaklig maintainer (henrygd). Detta repo är en fork. Jag har inte jämfört det mot upstream (**okänt** om det finns lokala avvikelser).

**Applikationstyp:** ett distribuerat system i två Go-binärer från samma modul (`github.com/henrygd/beszel`):

| Komponent | Ingång | Roll |
|---|---|---|
| **Hub** | [internal/cmd/hub/hub.go](internal/cmd/hub/hub.go) | Webbapp byggd på PocketBase (SQLite + REST + realtime + auth). Bäddar in ett React-SPA. Lagrar data, kör larm. |
| **Agent** | [internal/cmd/agent/agent.go](internal/cmd/agent/agent.go) | Körs på varje övervakad maskin, samlar mätvärden och svarar på förfrågningar från hubben. |
| **Webb-UI** | [internal/site/](internal/site/) | React 19 + Vite + Tailwind, inbäddat i hub-binären via `go:embed` ([internal/site/embed.go:9](internal/site/embed.go:9)). |

Kodmängd: cirka 71 000 rader Go (varav 131 testfiler mot 163 produktionsfiler) och cirka 24 000 rader TypeScript/TSX.

---

## 2. Arkitektur

### Katalogstruktur

| Katalog | Ansvar |
|---|---|
| [agent/](agent/) | All insamling på värden: CPU, disk, nät, sensorer, GPU (Nvidia NVML/nvtop, AMD, Intel, Apple), Docker, SMART, systemd, ZFS/btrfs, paketuppdateringar, nätverksmonitorer. Plus anslutningslogiken mot hubben. |
| [agent/lhm/](agent/lhm/) | Ett litet C#/.NET-program (LibreHardwareMonitor) för sensorer på Windows. |
| [internal/hub/](internal/hub/) | Hubbens kärna: uppstart, API-rutter, middleware, agentanslutning. |
| [internal/hub/systems/](internal/hub/systems/) | `SystemManager` och `System`: en goroutine per övervakat system som hämtar data och skriver poster. |
| [internal/hub/ws/](internal/hub/ws/), [internal/hub/transport/](internal/hub/transport/) | WebSocket-hantering, request/response-korrelation och en gemensam `Transport`-abstraktion för WS och SSH. |
| [internal/alerts/](internal/alerts/) | Larmregler, tysta timmar, larmhistorik, notifieringar via e-post och Shoutrrr. |
| [internal/records/](internal/records/) | Nedsampling av historik (1m till 10m, 20m, 120m, 480m) och borttagning av gammal data. |
| [internal/entities/](internal/entities/) | Delade datatyper (DTO:er) mellan agent och hub, med både JSON- och CBOR-taggar. |
| [internal/common/](internal/common/) | Wire-protokollet: actions, request/response-strukturer, SSH-krypton. |
| [internal/migrations/](internal/migrations/) | PocketBase-migreringar (ett snapshot för 0.20.0 plus inkrementella). |
| [internal/users/](internal/users/) | Rollhantering (admin/user/readonly) och skapande av första användaren. |
| [internal/ghupdate/](internal/ghupdate/) | Självuppdatering från GitHub releases. |
| [internal/site/](internal/site/) | Frontend. |
| [supplemental/](supplemental/) | Docker-, Helm-, Debian- och systemd-paketering, changelog. |

### Kommunikation mellan hub och agent (bekräftat)

Två transportvägar finns. Agenten föredrar WebSocket och faller tillbaka till SSH.

```
          WebSocket (agent ringer upp)                SSH (hubben ringer upp)
 Agent  ====== ringer upp =================  Hub  ===== ringer upp ==========  Agent
        GET /api/beszel/agent-connect             tcp :45876, ed25519-nyckel
        headers X-Token, X-Beszel                 agenten kollar mot KEY
        CBOR-meddelanden i båda riktningarna      CBOR över SSH-session
```

1. **WebSocket, agenten initierar.** [agent/client.go](agent/client.go) bygger URL:en `.../api/beszel/agent-connect` och skickar `X-Token` och `X-Beszel` (version). Hubben ([internal/hub/agent_connect.go:59](internal/hub/agent_connect.go:59)) slår upp token i tabellen `fingerprints` eller `universal_tokens` och uppgraderar till WS.
2. **Ömsesidig autentisering.** Hubben signerar agentens token med sin privata ed25519-nyckel (`GetSSHKey`, [internal/hub/hub.go:152](internal/hub/hub.go:152)) och skickar `CheckFingerprint`. Agenten verifierar signaturen mot den publika nyckeln i `KEY` ([agent/client.go:394](agent/client.go:394)), så att den vet att den pratar med rätt hub. Den svarar med sitt fingerprint (hostname plus CPU-modell plus sparat id). Hubben matchar eller sparar fingerprintet ([internal/hub/agent_connect.go:105](internal/hub/agent_connect.go:105)) och binder anslutningen till ett system.
3. **SSH, hubben initierar.** Agenten startar en SSH-server ([agent/server.go:48](agent/server.go:48)) som bara accepterar hubbens publika nyckel, inte tillåter PTY och har en idle timeout på 70 s. Hubben ringer upp när ingen WS-anslutning finns.
4. **Protokoll.** `HubRequest{Action, Data, Id}` och `AgentResponse` i [internal/common/common-ws.go](internal/common/common-ws.go), kodat med CBOR (`fxamacker/cbor`) med heltalsnycklar. Varje action är ett `iota`-värde.

### Flödet från början till slut

**Hub-uppstart:** `main` skapar PocketBase-appen, sedan `NewHub` och `StartHub` ([internal/hub/hub.go:79](internal/hub/hub.go:79)). I `OnServe`: synka `config.yml`, registrera middleware och API-rutter, registrera cron-jobb, starta webbservern och starta `SystemManager.Initialize` ([internal/hub/systems/system_manager.go:101](internal/hub/systems/system_manager.go:101)). Den läser alla icke-pausade system ur databasen och startar en updater-goroutine per system, utspritt i tid.

**Agent-uppstart:** `main` läser nycklar (flagga, `KEY` eller `KEY_FILE`), sedan `NewAgent` ([agent/agent.go:64](agent/agent.go:64)) som initierar alla delsystem (disk, nät, GPU, Docker, SMART, systemd med mera). Därefter `ConnectionManager.Start` ([agent/connection_manager.go:166](agent/connection_manager.go:166)), en tillståndsmaskin (`Disconnected`, `WebSocketConnected`, `SSHConnected`) som försöker WS var 10:e sekund och lyssnar på SSH under tiden.

**Datainsamlingscykeln** beskrivs steg för steg i avsnitt 5.

**UI:** SPA:t pratar direkt med PocketBases REST-API och realtime (SSE) via `pocketbase`-SDK:n ([internal/site/src/lib/api.ts](internal/site/src/lib/api.ts), [internal/site/src/lib/systemsManager.ts](internal/site/src/lib/systemsManager.ts)). Där PocketBase inte räcker används egna rutter under `/api/beszel/*`, till exempel containerloggar, SMART-refresh och universal token.

### Arkitekturmönster som syns i koden

| Mönster | Var |
|---|---|
| **Ramverk som applikationskärna.** Hubben *är* en PocketBase-app: `Hub` bäddar in `core.App` ([internal/hub/hub.go:28](internal/hub/hub.go:28)), och affärslogik hängs på PocketBase-hooks. | `OnRecordAfterUpdateSuccess("systems")` i [system_manager.go:136](internal/hub/systems/system_manager.go:136) |
| **Händelsedriven logik via DB-hooks.** Att spara `systems.status = up` triggar larmbedömningen. | [system_manager.go:208](internal/hub/systems/system_manager.go:208) |
| **Command/handler-registry** på agenten. | `HandlerRegistry` i [agent/handlers.go:47](agent/handlers.go:47) |
| **Strategy/adapter för transport.** | `Transport`-interfacet i [internal/hub/transport/transport.go](internal/hub/transport/transport.go) |
| **Interface för testbarhet.** `hubLike` i både `systems` och `alerts` gör att paketen inte beror på den konkreta `Hub`. | [system_manager.go:64](internal/hub/systems/system_manager.go:64) |
| **Plattformsspecifik kod via build tags och filsuffix.** | `*_linux.go`, `*_windows.go`, `*_unsupported.go`, taggarna `glibc`, `development`, `testing` |
| **Versionsgrindar för bakåtkompatibilitet.** | `MinVersion*` i [beszel.go](beszel.go), legacy-fält i `AgentResponse` |
| **Flernivå-cache på agenten**, nycklad på cache-intervall (60 s för hubbens poll, 1 s för realtime). | `systemDataCache`, `diskPrev`/`netIoStats` per intervall i [agent/agent.go](agent/agent.go) |

---

## 3. Tekniska beroenden

Direkta beroenden står i [go.mod](go.mod) och [internal/site/package.json](internal/site/package.json).

### De tre viktigaste

**1. PocketBase (`github.com/pocketbase/pocketbase v0.40.5`) - direkt**

- *Används till:* hela hub-backenden. Det är SQLite (via `modernc.org/sqlite`, ett indirekt beroende i ren Go), ORM/query builder (`pocketbase/dbx`), REST-API för alla collections, realtime-prenumerationer, auth (lösenord, OAuth2/OIDC, OTP/MFA), åtkomstregler, cron, mejl, backup till S3 samt adminpanelen under `/_/`.
- *Var:* överallt i `internal/hub`, `internal/alerts`, `internal/records`, `internal/users`, `internal/migrations`. Åtkomstkontrollen ligger i PocketBase-regler som sätts vid uppstart ([internal/hub/collections.go:17](internal/hub/collections.go:17)). Frontend använder `pocketbase` JS-SDK.
- *Hur viktigt:* kritiskt. Utan det finns ingen hub.
- *Ersättbarhet:* **mycket svårt.** Datamodell, auth, behörigheter, realtime och migreringar är PocketBase-specifika. Dessutom bryter PocketBase ofta API:t mellan 0.x-versioner, så uppgraderingar är det realistiska problemet snarare än ett byte.

**2. gopsutil (`github.com/shirou/gopsutil/v4`) - direkt**

- *Används till:* plattformsoberoende insamling av CPU, minne, disk, nätverk, sensorer, load, host-info på Linux, Windows, macOS och FreeBSD.
- *Var:* `agent/cpu*.go`, `agent/disk.go`, `agent/memory*.go`, `agent/network*.go`, `agent/sensors*.go`, `agent/system.go`.
- *Hur viktigt:* kärnan i agentens grundmått.
- *Ersättbarhet:* **svårt men möjligt.** Projektet har redan börjat läsa `/proc` och `/sys` direkt på flera ställen (`cpu_linux.go`, `memory_linux.go`, `network_counters_linux.go`, `fans_linux.go`), så det finns ett mönster att bygga vidare på. Det kostar mycket att täcka alla plattformar.

**3. CBOR + WebSocket + SSH (`fxamacker/cbor/v2`, `lxzan/gws`, `golang.org/x/crypto/ssh` + `gliderlabs/ssh`) - direkta**

Jag räknar dem som ett beroende eftersom de tillsammans utgör hub-agent-protokollet.

- *Används till:* serialisering av alla meddelanden (CBOR med heltalsnycklar för små payloads), WS-klient och WS-server (`gws`), SSH-server på agenten (`gliderlabs/ssh`), SSH-klient och signering i hubben (`x/crypto/ssh`).
- *Var:* [agent/client.go](agent/client.go), [agent/server.go](agent/server.go), [internal/hub/ws/](internal/hub/ws/), [internal/hub/transport/](internal/hub/transport/), [internal/common/](internal/common/).
- *Hur viktigt:* kritiskt. Alla mätvärden går genom det.
- *Ersättbarhet:* biblioteken var för sig är **måttligt lätta** att byta. Wire-formatet är **svårt** att ändra eftersom gamla agenter i fält måste fortsätta fungera.

### Andra betydande beroenden

- `nicholas-fedor/shoutrrr`: notifieringar till ett stort antal tjänster (Discord, Slack, Telegram, ntfy med flera). Används i [internal/alerts/alerts.go](internal/alerts/alerts.go). Det drar in indirekta beroenden som `paho.golang` (MQTT), `mellium.im/xmpp` och `mailyak`.
- `spf13/cobra` (hub-CLI, via PocketBase), `spf13/pflag` (agent-CLI).
- `ebitengine/purego`: laddar NVML (Nvidia) dynamiskt utan cgo, se [agent/gpu_nvml.go](agent/gpu_nvml.go).
- `mdlayher/netlink`, `genetlink`, `wifi`, `safchain/ethtool`: Linux-specifik nät- och WiFi-info.
- `coreos/go-systemd`: systemd-tjänster via D-Bus.
- `distribution/reference`, `opencontainers/go-digest`: Docker-bilduppdateringar mot registry.
- Frontend: React 19, `recharts` (alla grafer), `@tanstack/react-table` + `react-virtual`, `nanostores` (state och routing), Radix UI, Lingui (i18n, cirka 40 språk via Crowdin), `shiki` (syntaxfärgning av loggar), `valibot`.

**Direkta mot indirekta:** `go.mod` skiljer tydligt på dem med `// indirect`. Viktiga indirekta: `modernc.org/sqlite` (databasmotorn), `golang-jwt/jwt` (PocketBase-auth), `gorilla/websocket`, `godbus/dbus`, `go-ole`/`wmi` (Windows via gopsutil).

### Utvecklings- och testverktyg

- **Go-tester:** standard `testing` + `stretchr/testify`, PocketBase `tests.TestApp` (wrappas i [internal/tests/](internal/tests/)), och `testing/synctest` för tidsberoende tester (nämns i kommentar i [system.go](internal/hub/systems/system.go)). Build-taggen `testing` slår av bakgrundsjobb (SMART/ZFS) i tester ([systems_production.go](internal/hub/systems/systems_production.go)).
- **Testdata:** fixtures för SMART, ZFS och paketuppdateringar i [agent/test-data/](agent/test-data/).
- **Frontend:** Biome (lint/format), TypeScript, några få `bun test`-filer ([internal/site/tests/](internal/site/tests/) och `src/lib/*.test.ts`). Det finns inget `test`-skript i `package.json`.
- **Bygg:** [Makefile](Makefile) (`build`, `dev`, `test`, `lint` via `golangci-lint`), GoReleaser ([.goreleaser.yml](.goreleaser.yml)), Docker, Helm, .NET SDK för Windows-agenten.
- **CI:** se problem P1 nedan.

---

## 4. Integrationer

Alla nedan har jag sett anropas från produktionskod, inte bara i dokumentation.

| System | Kod | Protokoll/bibliotek | Auth och konfig | Nödvändig? |
|---|---|---|---|---|
| **SQLite** (via PocketBase) | hela hubben; datakatalog `beszel_data` | inbäddad, `modernc.org/sqlite` | ingen extern auth | **Ja** |
| **Hub till agent, WS** | [internal/hub/agent_connect.go](internal/hub/agent_connect.go), [agent/client.go](agent/client.go) | WebSocket + CBOR | token (`TOKEN`/`TOKEN_FILE`) + ed25519-signatur verifierad mot `KEY`; valfri `CA_CERT_FILE`, `HUB_HEADERS`, proxy | **Ja** (WS eller SSH) |
| **Hub till agent, SSH** | [internal/hub/transport/ssh.go](internal/hub/transport/ssh.go), [agent/server.go](agent/server.go) | SSH + CBOR | publik nyckel; `LISTEN`, `DISABLE_SSH` | **Ja** (WS eller SSH) |
| **Docker/Podman API** | [agent/docker.go](agent/docker.go) | HTTP över unix-socket eller TCP (`DOCKER_HOST`), timeout 2,1 s | socket-rättigheter | Nej, valfri |
| **Container registries** | [agent/docker_registry.go](agent/docker_registry.go), [agent/docker_image_updates.go](agent/docker_image_updates.go) | HTTPS, Docker Registry API | anonym/token | Nej |
| **smartctl** | [agent/smart.go](agent/smart.go) | `exec.Command`, JSON-utdata | kräver ofta root/capabilities | Nej |
| **GPU-verktyg** | `agent/gpu*.go` | NVML via `purego`, `nvidia-smi`, `rocm-smi`/sysfs, `intel_gpu_top`, `nvtop`, `powermetrics` | lokala rättigheter | Nej |
| **systemd/D-Bus, journald** | [agent/systemd.go](agent/systemd.go) | D-Bus (`go-systemd`), `journalctl` | lokal | Nej |
| **ZFS/btrfs, pakethanterare** | [agent/zfs/](agent/zfs/), [agent/btrfs/](agent/btrfs/), [agent/package_updates.go](agent/package_updates.go) | `zpool`/sysfs/ioctl, apt/dnf med flera via exec | lokal | Nej |
| **Nätverksmonitorer** | `agent/network_monitor_*.go` | ICMP/ping, TCP, HTTP(S), TLS-certifikat | ingen | Nej |
| **Notifieringstjänster** | [internal/alerts/alerts.go:214](internal/alerts/alerts.go:214), [notification_client.go](internal/alerts/notification_client.go) | Shoutrrr-URL:er (HTTP, SMTP, MQTT, XMPP med flera) + PocketBase-mejl | URL:er lagras i `user_settings` | Nej, men behövs för larm |
| **Heartbeat** (utgående push) | [internal/hub/heartbeat/heartbeat.go](internal/hub/heartbeat/heartbeat.go) | HTTP GET/POST | `HEARTBEAT_URL`, `HEARTBEAT_INTERVAL`, `HEARTBEAT_METHOD` | Nej |
| **GitHub releases** | [internal/ghupdate/ghupdate.go](internal/ghupdate/ghupdate.go) | HTTPS mot `api.github.com` eller spegeln `gh.beszel.dev` | ingen; kontrollsumma från release-API:t ([ghupdate.go:162](internal/ghupdate/ghupdate.go:162)) | Nej, bara vid `update` |
| **OAuth2/OIDC, SMTP, S3-backup** | PocketBase-inbyggt, konfigureras i PocketBase-admin | OAuth2, SMTP, S3 | i PocketBase-inställningar (DB) | Nej |
| **Reverse proxy / SSO** | [internal/hub/api.go:88](internal/hub/api.go:88) | trusted header (`TRUSTED_AUTH_HEADER`, `TRUSTED_PROXY_IPS`) eller `AUTO_LOGIN` | env | Nej |

**Konfiguration:** nästan allt styrs av miljövariabler. Agenten läser `BESZEL_AGENT_<NAMN>` före `<NAMN>` ([agent/utils/utils.go:17](agent/utils/utils.go:17)) och hubben `BESZEL_HUB_<NAMN>` ([internal/hub/utils/utils.go:11](internal/hub/utils/utils.go:11)). Hubben kan dessutom deklarativt synka system från `beszel_data/config.yml` ([internal/hub/config/config.go](internal/hub/config/config.go)).

**Felhantering:** Agentens anslutning återansluter automatiskt med fallback till SSH. Hubben markerar system som `down` vid fel (`setDown`) och WS-förfrågningar har timeouts (5 s standard, 30 s för `GetData`). Notifieringar loggas vid fel men görs inte om. Webhooks från icke-admin-användare skickas via en klient som blockerar interna IP-adresser ([notification_client.go:143](internal/alerts/notification_client.go:143)), ett genomtänkt skydd mot SSRF.

---

## 5. Affärslogik

Det finns ingen klassisk affärsdomän. Den centrala funktionaliteten är **insamling, lagring, nedsampling och larm**. Logiken ligger här:

| Område | Fil/funktion |
|---|---|
| Statusmaskin för system (pending/up/down/paused) och när larm körs | `onRecordAfterUpdateSuccess`, [system_manager.go:208](internal/hub/systems/system_manager.go:208) |
| Poll-cykel, fallback WS till SSH | `StartUpdater`, `update`, `fetchDataFromAgent` i [system.go](internal/hub/systems/system.go) (rad 106, 162, 786) |
| Persistens av mätpunkter | `createRecords`, [system.go:258](internal/hub/systems/system.go:258) |
| Tröskellarm med medelvärde över N minuter | `HandleSystemAlerts`, [alerts_system.go:38](internal/alerts/alerts_system.go:38) |
| Status-, container-, systemd-, SMART-, ZFS- och nätmonitorlarm | `internal/alerts/alerts_*.go` |
| Tysta timmar | `IsNotificationSilenced`, [alerts.go:147](internal/alerts/alerts.go:147) |
| Nedsampling och retention | `CreateLongerRecords`, [records.go:42](internal/records/records.go:42); `DeleteOldRecords` i [records_deletion.go](internal/records/records_deletion.go) |
| Behörighet (ägarskap, delning, readonly) | PocketBase-regler i [collections.go:54-69](internal/hub/collections.go:54) och `HasUser` i API-handlers |
| Agentregistrering och token-/fingerprint-matchning | [agent_connect.go](internal/hub/agent_connect.go) |
| Mätning på agenten (beräkning av deltan, rates, cache) | `gatherStats`, [agent/agent.go:191](agent/agent.go:191), plus `agent/*.go` |

**Separation:** Presentation (React) är tydligt separerad och pratar bara via HTTP och SSE. På hubben är däremot logik och datalagring tätt sammanvävda: `System.createRecords` skriver direkt med `core.App` i en transaktion, och larmen triggas som *bieffekt* av att system-posten sparas. Det finns inget separat domänlager. `entities` är rena datastrukturer.

### Flöde 1: en mätpunkt, från agent till larm (bekräftat)

1. `SystemManager.AddSystem` startar `System.StartUpdater` i en goroutine ([system_manager.go:282](internal/hub/systems/system_manager.go:282)).
2. En ticker på 60 s (plus jitter för WS) anropar `System.update()` ([system.go:162](internal/hub/systems/system.go:162)).
3. `fetchDataFromAgent` ([system.go:786](internal/hub/systems/system.go:786)) använder WS om den finns. Annars, eller vid annat fel än timeout, stängs WS och SSH används.
4. Hubben skickar `HubRequest{Action: GetData, Data: {CacheTimeMs: 60000, IncludeDetails}}` som CBOR.
5. Agenten: `OnMessage`, sedan `handleHubRequest`, sedan `HandlerRegistry.Handle` ([agent/handlers.go:80](agent/handlers.go:80)) som kräver att hubben är verifierad. Därefter `GetDataHandler`, sedan `Agent.gatherStats` ([agent/agent.go:191](agent/agent.go:191)). Den returnerar cachad data om sådan finns för intervallet, annars samlar den system, Docker, monitorer, systemd, paketuppdateringar och filsystem.
6. Svaret går tillbaka som `AgentResponse`. Hubben korrelerar via `Id` i `RequestManager` ([internal/hub/ws/request_manager.go](internal/hub/ws/request_manager.go)) och avkodar med `transport.UnmarshalResponse`, som hanterar både nytt och legacy-format.
7. `migrateDeprecatedFields` normaliserar data från äldre agenter.
8. `createRecords` ([system.go:258](internal/hub/systems/system.go:258)) skriver i **en transaktion** `system_stats` (typ `1m`), `containers` + `container_stats`, `systemd_services`, `system_details`, `network_monitor_stats` och ZFS-hälsa. Sist uppdateras `systems.status = up` och `info`.
9. Sparandet av `systems` triggar `onRecordAfterUpdateSuccess`, som kör `HandleSystemAlerts` och `HandleContainerAlerts`. Vid statusbyte körs även `HandleStatusAlerts`.
10. `HandleSystemAlerts` hämtar användarnas larm ur en cache och räknar fram medelvärden över `min` minuter från `system_stats`. Om tröskeln passeras anropas `SendAlert`, som respekterar tysta timmar och skickar mejl och/eller Shoutrrr.
11. Separat cron ([hub.go:137](internal/hub/hub.go:137)): var 10:e minut slås poster ihop till längre intervall, och varje timme raderas gamla poster (1m: 1 h, 10m: 12 h, 20m: 1 d, 120m: 7 d, 480m: 30 d).
12. UI:t får uppdateringen via PocketBase realtime på `systems` och ritar om.

### Flöde 2: en ny agent registrerar sig med universal token (bekräftat)

1. Agenten ansluter med `X-Token` = universal token ([agent_connect.go:59](internal/hub/agent_connect.go:59)).
2. Hubben hittar token i minnes-mappen eller i `universal_tokens`, och därmed `userId`.
3. Uppgradering till WS, sedan `verifyWsConn`: signera token, skicka `CheckFingerprint` med `NeedSysInfo=true`.
4. Agenten verifierar signaturen mot `KEY` och svarar med fingerprint, `SYSTEM_NAME`, hostname och port.
5. Om inget befintligt fingerprint matchar skapas ett nytt system (`createSystem`) och en ny `fingerprints`-post.
6. `AddWebSocketSystem` ([system_manager.go:348](internal/hub/systems/system_manager.go:348)) registrerar systemet och synkar nätverksmonitorer till agenten.

Ett vanligt (icke-universellt) token med ett befintligt fingerprint som inte matchar ger `fingerprint mismatch` och anslutningen stängs. Det är skyddet mot att en klonad agent tar över ett system.

### Vad är lätt eller riskabelt att ändra?

**Relativt lätt** (lokala ändringar med bra testtäckning):
- En ny insamlare på agenten, så länge den bara fyller i nya fält i `Stats` eller `Info`.
- Ny larmtyp i `internal/alerts` enligt befintliga `alerts_*.go`.
- UI-komponenter och grafer.
- Nya miljövariabler för agenten.

**Riskabelt** (påverkar mycket):
- **Wire-protokollet:** `WebSocketAction`-ordningen ([common-ws.go](internal/common/common-ws.go)), CBOR-nyckelnummer och JSON-kortnamn i `internal/entities/*`. De delas av gamla agenter i fält, av lagrad JSON i databasen och av frontend.
- **Statusmaskinen** i `onRecordAfterUpdateSuccess`. Larm, återställning och pausning är kopplade till exakta statusövergångar.
- **`createRecords`-transaktionen** och ordningen i den. Larmen förutsätter att system-posten sparas sist.
- **`collections.go`:** åtkomstregler. Ett fel här blir direkt ett behörighetsproblem.
- **PocketBase-uppgraderingar.**
- **`records.go`:** medelvärdesbildningen för alla fält. Nya fält i `Stats` måste läggas till där, annars försvinner de i längre intervall (se P5).

---

## 6. Tekniska problem och risker

Sorterat ungefär efter betydelse. **Faktiskt problem** betyder att det är synligt i koden. **Risk** betyder att det kan bli ett problem.

### P1. Inga automatiska tester i CI - faktiskt problem, hög säkerhet
- **Vad:** [.github/workflows/](.github/workflows/) innehåller `docker-images`, `release`, `helm-charts`, `update-helm-charts`, `inactivity-actions` och `vulncheck`. Inget av dem kör `go test`, `golangci-lint`, `tsc` eller frontend-tester. `release.yml` bygger UI:t (där `tsc -b` ingår) och släpper.
- **Konsekvens:** den stora testsviten (131 testfiler) skyddar bara om någon kör den lokalt. En PR eller release kan gå igenom med röda tester. Det gäller särskilt i en fork där upstreams rutiner inte följer med.
- **Åtgärd:** lägg till ett workflow på PR och push som kör `go test -race -tags testing ./...` (med en stub för `dist`, se P2), `golangci-lint` och `bun run build`/`tsc` + `bun test`.

### P2. `make test` refererar till en build-tag som inte finns - faktiskt problem, medel till hög säkerhet
- **Vad:** [Makefile:54](Makefile:54) kör `go test -tags='testing no_ui' ./...`, men `no_ui` används ingenstans i koden. [internal/site/embed.go:9](internal/site/embed.go:9) har `//go:embed all:dist` utan tagg, och `internal/site/dist` finns inte i en ren checkout.
- **Konsekvens:** **Misstanke** (ej körd): på en ny klon misslyckas kompileringen av paket som importerar `internal/site` (bland annat `internal/hub`) tills UI:t har byggts eller `dist/` skapats. `dev-hub` och `build-hub-dev` gör `mkdir -p dist && touch index.html` som en workaround, men det gör inte `test`.
- **Åtgärd:** låt `test`-målet skapa stubben, eller lägg till en `//go:build !no_ui`-variant av `embed.go` med en tom FS.

### P3. Osynkad delad state på `System` (`WsConn`, `data`) - risk, medel säkerhet
- **Vad:** `System.WsConn` är en vanlig pekare utan lås. Den skrivs till `nil` i updater-goroutinen ([system.go:149](internal/hub/systems/system.go:149)) och läses från andra goroutiner: realtime-workern ([system_realtime.go:166](internal/hub/systems/system_realtime.go:166)), `go system.update()` i statushooken ([system_manager.go:233](internal/hub/systems/system_manager.go:233)), API-handlers för loggar/SMART och `onTokenRotated`. `fetchDataFromAgent` gör "kolla `!= nil`, använd sedan" i två steg ([system.go:787](internal/hub/systems/system.go:787) och 822). `sys.data` skrivs i `update` och kan köras från två goroutiner samtidigt.
- **Konsekvens:** data race. I värsta fall en nil-dereferens (panik) om WS stängs mellan kontroll och användning, och larm som utvärderas på fel snapshot. Fönstret är litet. Jag har inte kunnat köra `-race`, så det är **inte bekräftat** att det faktiskt händer.
- **Åtgärd:** kör testsviten med `-race`. Läs `WsConn` en gång till en lokal variabel, eller skydda den med `atomic.Pointer`/mutex som redan görs för `agentVersion`.

### P4. Wire-protokollet bygger på `iota`-ordning och manuella nyckelnummer - risk, hög säkerhet
- **Vad:** `WebSocketAction` är `iota` ([common-ws.go](internal/common/common-ws.go)). Om någon infogar en action mitt i listan ändras numren för alla efterföljande. Kommentaren "Add new actions here..." är det enda skyddet. Samma sak gäller CBOR-heltalsnycklarna i `internal/entities`.
- **Konsekvens:** tyst inkompatibilitet mot agenter i fält, där fel handler körs.
- **Åtgärd:** sätt explicita värden (`GetData WebSocketAction = 0` och så vidare) och lägg till ett test som låser numren.

### P5. Nya mätfält måste läggas till på flera ställen för hand - faktiskt problem, medel säkerhet
- **Vad:** ett nytt fält i `system.Stats` måste in i insamlingen på agenten, i `AverageSystemStatsSlice` ([records.go:263](internal/records/records.go:263), cirka 370 rader med manuell summering), eventuellt i `migrateDeprecatedFields`, i larmlogiken och i TypeScript-typerna ([internal/site/src/types.d.ts](internal/site/src/types.d.ts)) med samma kortnamn.
- **Konsekvens:** lätt att glömma ett ställe. Då försvinner fältet i 10m och längre intervall, eller visas fel i UI:t. Det finns omfattande averaging-tester, vilket minskar risken.
- **Åtgärd:** en checklista i en CONTRIBUTING-fil. Eventuellt generera TS-typer från Go-structarna.

### P6. Utgångna deprecations och dubbla fält - faktiskt problem, hög säkerhet
- **Vad:** `TODO(0.19+): stop populating NetworkSent/NetworkRecv` i [agent/docker.go:383](agent/docker.go:383) och 565, trots version 0.21.0. Legacy-fält finns i `AgentResponse` (`<= 0.17`), `DiskReadPs`/`DiskWritePs` och gamla load-fält i [internal/entities/system/system.go](internal/entities/system/system.go) med TODO om borttagning.
- **Konsekvens:** större payloads och fler kodvägar att testa och förstå. Svårt att veta vilka äldre agentversioner som faktiskt stöds.
- **Åtgärd:** bestäm en lägsta agentversion som stöds, höj `MinVersion*` och rensa.

### P7. Logik som bieffekt av DB-hooks - risk/designskuld, medel säkerhet
- **Vad:** att spara `systems` triggar larm, att `status = pending` startar om övervakning och att `fingerprints` uppdateras stänger WS ([system_manager.go:136](internal/hub/systems/system_manager.go:136)). Det gäller även sparningar från PocketBase-adminpanelen eller REST-API:t.
- **Konsekvens:** svårt att följa flödet. En ändring av status via API:t ger oväntade bieffekter, och ordningen i `createRecords` blir en implicit invariant.
- **Åtgärd:** ingen akut åtgärd, men dokumentera statusmaskinen. Överväg att anropa larmen explicit från `update()`.

### P8. `GetSSHKey` cachar aldrig nyckeln - faktiskt problem (litet), hög säkerhet
- **Vad:** [hub.go:152](internal/hub/hub.go:152) kollar `h.signer != nil`, men fältet tilldelas aldrig (grep visar ingen tilldelning). Nyckelfilen läses och parsas vid varje WS-anslutning ([agent_connect.go:120](internal/hub/agent_connect.go:120)).
- **Konsekvens:** onödig disk-I/O vid många återanslutningar. Det kan också bli ett race om två goroutiner genererar nyckeln samtidigt vid första start, men den är normalt redan skapad i `createSSHClientConfig` vid uppstart.
- **Åtgärd:** sätt `h.signer` (under `sync.Once`).

### P9. Säkerhetskänsliga konfigurationslägen - risk, hög säkerhet om felkonfigurerat
- `TRUSTED_AUTH_HEADER` utan `TRUSTED_PROXY_IPS` accepterar headern från **vilken klient som helst** ([api.go:88-95](internal/hub/api.go:88), avsiktligt enligt kommentaren). Om hubben går att nå förbi proxyn kan vem som helst logga in som vilken användare som helst.
- `AUTO_LOGIN` loggar in alla anrop som en given användare.
- `SHARE_ALL_SYSTEMS=true` ger alla inloggade läsrätt till alla system ([collections.go:54](internal/hub/collections.go:54)).
- `config.yml` **raderar** system som inte finns i filen när filen innehåller minst ett system ([config.go:152](internal/hub/config/config.go:152)). Det är dokumenterat beteende men lätt att råka ut för.
- **Åtgärd:** logga en tydlig varning vid start när trusted header används utan proxy-lista.

### P10. Självuppdatering litar på kontrollsumma från samma källa - risk, medel säkerhet
- **Vad:** `verifyAssetChecksum` jämför mot `asset.Digest` från release-API:t ([ghupdate.go:162](internal/ghupdate/ghupdate.go:162)). Med `--china-mirrors` kommer både binär och digest från `gh.beszel.dev`. Det finns ingen signaturverifiering.
- **Konsekvens:** kontrollsumman skyddar mot korrupta nedladdningar, inte mot en komprometterad spegel eller ett komprometterat release-konto.
- **Åtgärd:** signerade releaser (cosign/minisign) och verifiering mot en inbäddad publik nyckel.

### P11. Plattformsbredd och komplicerad utvecklingsmiljö - faktiskt problem, hög säkerhet
- Agenten stöder Linux (glibc/musl), Windows (med .NET-hjälpprogram och nedladdad `smartctl.exe`), macOS och FreeBSD, plus många GPU-varianter. Mycket kod går bara att testa på rätt OS eller hårdvara, och fixtures täcker bara en del.
- Hub-utveckling kräver Go 1.27.2, Bun eller npm och för Windows-agenten .NET SDK. Makefile förutsätter POSIX-skal (`entr`, `find`, `command -v`) och fungerar inte i ren Windows-cmd/PowerShell.
- **Åtgärd:** en `CONTRIBUTING.md` med setup per OS. Eventuellt en devcontainer.

### P12. Bristfällig utvecklardokumentation i repot - faktiskt problem, hög säkerhet
- README:n är användarorienterad och hänvisar till beszel.dev. Det finns ingen arkitektur- eller protokollbeskrivning, ingen förteckning över miljövariabler och ingen beskrivning av statusmaskinen i repot. Kodkommentarerna är däremot generellt bra.

### P13. Tunn frontend-testning - faktiskt problem, hög säkerhet
- Ungefär 6 testfiler för cirka 24 000 rader TSX/TS, inget testskript och inga komponent- eller E2E-tester. Komplexa delar som `systemsManager.ts`, chart-datahantering och realtime-prenumerationer saknar tester.

### Saker som *inte* är problem

- Bakåtkompatibilitet hanteras medvetet (versionsgrindar, legacy-fält, tester för det).
- Ömsesidig autentisering hub-agent är genomtänkt: signerat token, fingerprint-bindning och kontroll av att hubben är verifierad innan handlers körs.
- SSRF-skydd för webhooks från icke-admins finns.
- API-handlers som hämtar loggar eller kör SMART-refresh kontrollerar `system.HasUser` ([api.go:399](internal/hub/api.go:399) med flera).
- Testsviten på Go-sidan är stor och verkar fokuserad på regressioner. Många tester refererar till issue-nummer.

---

## 7. Att lära sig först

1. **PocketBase.** Läs dess dokumentation om collections, regler, hooks (`OnRecord*`, `OnServe`), realtime och migreringar. Hubben är "PocketBase plus hooks". Starta med `make dev` och titta på datamodellen i adminpanelen (`/_/`).
2. **Hub-agent-protokollet**: [internal/common/common-ws.go](internal/common/common-ws.go), [agent/client.go](agent/client.go), [internal/hub/agent_connect.go](internal/hub/agent_connect.go), [internal/hub/transport/](internal/hub/transport/). Förstå token, signatur, fingerprint och varför gamla agenter måste fortsätta fungera.
3. **Livscykeln för ett system** i [system_manager.go](internal/hub/systems/system_manager.go) och [system.go](internal/hub/systems/system.go): statusar, updater-goroutinen, WS/SSH-fallback, `createRecords` och hooken som triggar larm.
4. **Datamodellens kortnamn**: JSON-taggar som `cpu`, `mp`, `dp` i [internal/entities/system/system.go](internal/entities/system/system.go) och motsvarande i [internal/site/src/types.d.ts](internal/site/src/types.d.ts), samt hur [records.go](internal/records/records.go) bildar medelvärden av dem.
5. **Agentens insamling och cache**: [agent/agent.go](agent/agent.go) `gatherStats`, cache per intervall (60 s och 1 s realtime) och build tags per plattform.
6. **Hur man kör tester lokalt**: `go test -tags testing ./...` efter att ha skapat `internal/site/dist/index.html` (se P2). Kör med `-race`.

---

## 8. Osäkerheter

- **Inget har körts.** Go och Bun saknas på analysmaskinen. Att testerna passerar, att `make test` faktiskt misslyckas utan `dist/` (P2) och att det finns data races (P3) behöver bekräftas genom att köra `go test -race -tags testing ./...`.
- **Skillnader mot upstream** (`henrygd/beszel`) har inte undersökts. Det är okänt vad forken ändrat, och om den tänker följa upstream eller divergera.
- **Ej granskat i detalj:** GPU-insamlarna (`agent/gpu_*.go`), SMART-parsning ([agent/smart.go](agent/smart.go)), ZFS/btrfs, paketuppdateringar, WiFi, sensorer per OS, .NET-hjälpprogrammet ([agent/lhm/](agent/lhm/)), de flesta frontend-komponenter, Helm-chartet, Debian-paketeringen och [.goreleaser.yml](.goreleaser.yml). Jag har bara skummat dem efter integrationspunkter.
- **Nedsampling när system går ner:** `CreateLongerRecords` behandlar bara system med `status='up'` ([records.go](internal/records/records.go)), och 1m-poster raderas efter 1 h. Jag har inte verifierat om det ger luckor i historiken för system som går ner mitt i ett fönster. Det kan vara avsiktligt.
- **PocketBase-reglerna i praktiken:** jag har läst hur reglerna sätts, men inte testat dem mot alla collections och roller. Det finns `alerts_access_test.go` och `collections_test.go` som verkar täcka det.
- **Prestanda och skalning:** en goroutine och en DB-transaktion per system och minut, plus SQLite. Det är okänt var gränsen går (hundratals eller tusentals system). Det kräver lasttest.
- **Beroendenas sårbarhetsstatus:** `govulncheck` körs i CI på push till `main`, men resultatet har jag inte sett. Frontend-beroendena granskas inte automatiskt alls.
- **Säkerheten i `config.yml`-tokens och `id_ed25519`** i datakatalogen: filrättigheterna sätts till 0600 för nyckeln, men hur datakatalogen skyddas i Docker/Helm-uppsättningen har jag inte granskat.

---

## De fem viktigaste sakerna att förstå innan du börjar

1. **Hubben är en PocketBase-app.** Databas, auth, behörigheter (regler i [collections.go](internal/hub/collections.go)), REST och realtime kommer från PocketBase. Mycket logik körs som hooks när poster sparas, inte som explicita anrop.
2. **Protokollet mellan hub och agent är ett publikt kontrakt.** Action-nummer, CBOR-nycklar och JSON-kortnamn får aldrig ändras eller omordnas. Gamla agenter i fält måste fortsätta fungera, därav `MinVersion*` och legacy-fälten.
3. **Ett systems liv styrs av statusmaskinen** (`pending`, `up`, `down`, `paused`) i [system_manager.go:208](internal/hub/systems/system_manager.go:208). Larm, återställningsnotiser och pausning hänger på exakta övergångar, och `createRecords` måste spara system-posten sist.
4. **Varje nytt mätvärde berör flera lager**: insamling i `agent/`, struct i `internal/entities/`, medelvärdesbildning i [records.go](internal/records/records.go), eventuellt larm i `internal/alerts/`, och TS-typer och grafer i `internal/site/`.
5. **Testerna finns men körs inte automatiskt.** Kör `go test -race -tags testing ./...` lokalt (med en stub för `internal/site/dist`) före varje ändring, och prioritera att få in ett CI-steg för tester.
