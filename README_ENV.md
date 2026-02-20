# Variabili d'Ambiente KRR - Guida Completa

Questo documento descrive tutte le variabili d'ambiente utilizzabili per configurare KRR quando eseguito tramite Docker.

## Indice

- [Docker Image](#docker-image)
- [Strategy Selection](#strategy-selection)
- [Kubernetes Settings](#kubernetes-settings)
- [Prometheus Settings](#prometheus-settings)
- [Prometheus EKS Settings](#prometheus-eks-settings)
- [Prometheus Coralogix Settings](#prometheus-coralogix-settings)
- [Prometheus Openshift Settings](#prometheus-openshift-settings)
- [Prometheus GCP Settings](#prometheus-gcp-settings)
- [Recommendation Settings](#recommendation-settings)
- [Threading Settings](#threading-settings)
- [Job Grouping Settings](#job-grouping-settings)
- [Job Discovery Settings](#job-discovery-settings)
- [Logging Settings](#logging-settings)
- [Output Settings](#output-settings)
- [Publish Scan Settings](#publish-scan-settings)
- [Strategy Settings (Common)](#strategy-settings-common)
- [Strategy: simple](#strategy-simple)
- [Strategy: simple-limit](#strategy-simple-limit)
- [Strategy: ai-assisted](#strategy-ai-assisted)
- [External API Keys](#external-api-keys)

---

## Docker Image

### `KRR_DOCKER_IMAGE`
**Scopo**: Specifica l'immagine Docker da utilizzare per eseguire KRR.

**Default**: `krr:latest`

**Esempi**:
```bash
# Immagine locale
KRR_DOCKER_IMAGE=krr:latest

# Immagine da Artifact Registry
KRR_DOCKER_IMAGE=europe-west12-docker.pkg.dev/formazione-ion-boleac/tools/holo-krr:latest
```

---

## Strategy Selection

### `KRR_STRATEGY`
**Scopo**: Seleziona la strategia di raccomandazione da utilizzare.

**Default**: `simple`

**Opzioni**: `simple`, `simple-limit`, `ai-assisted`

**Descrizione**:
- `simple`: Strategia basata su percentili per CPU e buffer percentuale per memoria
- `simple-limit`: Simile a simple, ma calcola anche i limiti (CPU limit basato su percentile diverso)
- `ai-assisted`: Utilizza AI (OpenAI, Gemini, Anthropic, Ollama) per raccomandazioni più sofisticate

---

## Kubernetes Settings

### `KRR_KUBECONFIG`
**Scopo**: Percorso al file kubeconfig. Se non fornito, KRR tenterà di trovarlo automaticamente.

**Default**: Nessuno (auto-discovery)

**Esempio**: `KRR_KUBECONFIG=/path/to/kubeconfig`

### `KRR_AS`
**Scopo**: Impersona un utente, come `kubectl --as`. Utile per testare permessi RBAC.

**Default**: Nessuno

**Esempio**: `KRR_AS=system:serviceaccount:default:krr-account`

### `KRR_AS_GROUP`
**Scopo**: Impersona un utente all'interno di un gruppo, come `kubectl --as-group`.

**Default**: Nessuno

**Esempio**: `KRR_AS_GROUP=system:authenticated`

### `KRR_CONTEXT`
**Scopo**: Lista di cluster su cui eseguire. Per default, usa il cluster corrente. Usa `--all-clusters` per tutti i cluster.

**Default**: Cluster corrente

**Esempio**: `KRR_CONTEXT=my-cluster-context`

### `KRR_ALL_CLUSTERS`
**Scopo**: Esegui su tutti i cluster disponibili nel kubeconfig. Sovrascrive `KRR_CONTEXT`.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_NAMESPACE`
**Scopo**: Lista di namespace su cui eseguire l'analisi. Per default, esegue su tutti i namespace eccetto 'kube-system'.

**Default**: Tutti (eccetto kube-system)

**Esempio**: `KRR_NAMESPACE=default,production`

### `KRR_RESOURCE`
**Scopo**: Lista di tipi di risorse da analizzare (Deployment, StatefulSet, DaemonSet, Job, Rollout, StrimziPodSet). Per default, analizza tutte le risorse. Case insensitive.

**Default**: Tutte le risorse supportate

**Esempio**: `KRR_RESOURCE=Deployment,StatefulSet`

### `KRR_SELECTOR`
**Scopo**: Selector (label query) per filtrare i workload. Applicato alle label del workload (es. deployment) non sui singoli pod! Supporta '=', '==', e '!='. Gli oggetti devono soddisfare tutti i vincoli label specificati.

**Default**: Nessuno

**Esempio**: `KRR_SELECTOR=app=myapp,env=prod`

---

## Prometheus Settings

### `KRR_PROMETHEUS_URL`
**Scopo**: URL di Prometheus. Se non fornito, KRR tenterà di trovarlo automaticamente nel cluster Kubernetes.

**Default**: Nessuno (auto-discovery nel cluster)

**Esempio**: `KRR_PROMETHEUS_URL=https://monitoring.googleapis.com/v1/projects/my-project/location/global/prometheus`

### `KRR_PROMETHEUS_AUTH_HEADER`
**Scopo**: Header di autenticazione per Prometheus.

**Default**: Nessuno

**Esempio**: `KRR_PROMETHEUS_AUTH_HEADER=Bearer YOUR_TOKEN_HERE`

### `KRR_PROMETHEUS_HEADERS`
**Scopo**: Header aggiuntivi da aggiungere alle richieste Prometheus. Formato 'key: value'. Gli spazi finali verranno rimossi.

**Default**: Nessuno

**Esempio**: `KRR_PROMETHEUS_HEADERS=X-Custom-Header: value`

### `KRR_PROMETHEUS_SSL_ENABLED`
**Scopo**: Abilita SSL per le richieste a Prometheus.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_PROMETHEUS_CLUSTER_LABEL`
**Scopo**: La label in Prometheus che identifica il tuo cluster. Rilevante solo per Prometheus centralizzato.

**Default**: Nessuno

**Esempio**: `KRR_PROMETHEUS_CLUSTER_LABEL=my-cluster-name`

### `KRR_PROMETHEUS_LABEL`
**Scopo**: La label in Prometheus usata per differenziare i cluster. Rilevante solo per Prometheus centralizzato.

**Default**: Nessuno

**Esempio**: `KRR_PROMETHEUS_LABEL=cluster_name`

---

## Prometheus EKS Settings

### `KRR_EKS_MANAGED_PROM`
**Scopo**: Aggiunge signature aggiuntive per la connessione a Prometheus EKS.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_EKS_PROFILE_NAME`
**Scopo**: Imposta il nome del profilo per la connessione a Prometheus EKS.

**Default**: Nessuno

**Esempio**: `KRR_EKS_PROFILE_NAME=default`

### `KRR_EKS_ACCESS_KEY`
**Scopo**: Imposta l'access key per la connessione a Prometheus EKS.

**Default**: Nessuno

**Esempio**: `KRR_EKS_ACCESS_KEY=YOUR_ACCESS_KEY`

### `KRR_EKS_SECRET_KEY`
**Scopo**: Imposta la secret key per la connessione a Prometheus EKS.

**Default**: Nessuno

**Esempio**: `KRR_EKS_SECRET_KEY=YOUR_SECRET_KEY`

### `KRR_EKS_SERVICE_NAME`
**Scopo**: Imposta il nome del servizio per la connessione a Prometheus EKS.

**Default**: `aps`

**Esempio**: `KRR_EKS_SERVICE_NAME=aps`

### `KRR_EKS_MANAGED_PROM_REGION`
**Scopo**: Imposta la region per la connessione a Prometheus EKS.

**Default**: Nessuno

**Esempio**: `KRR_EKS_MANAGED_PROM_REGION=us-east-1`

### `KRR_EKS_ASSUME_ROLE`
**Scopo**: Imposta il ruolo assunto per la connessione a Prometheus EKS (per assunzione di ruoli cross-account).

**Default**: Nessuno

**Esempio**: `KRR_EKS_ASSUME_ROLE=arn:aws:iam::123456789012:role/MyRole`

---

## Prometheus Coralogix Settings

### `KRR_CORALOGIX_TOKEN`
**Scopo**: Aggiunge il token necessario per interrogare Prometheus gestito da Coralogix.

**Default**: Nessuno

**Esempio**: `KRR_CORALOGIX_TOKEN=YOUR_CORALOGIX_TOKEN`

---

## Prometheus Openshift Settings

### `KRR_OPENSHIFT`
**Scopo**: Connetti a Prometheus con un token letto da `/var/run/secrets/kubernetes.io/serviceaccount/token` - raccomandato quando si esegue KRR all'interno di un cluster OpenShift.

**Default**: `false`

**Valori**: `true` | `false`

---

## Prometheus GCP Settings

### `KRR_GCP_ANTHOS`
**Scopo**: Usa metriche GCP Anthos (kubernetes.io/anthos/*) per Kubernetes on-prem gestito da Google.

**Default**: `false`

**Valori**: `true` | `false`

---

## Recommendation Settings

### `KRR_CPU_MIN`
**Scopo**: Imposta il valore minimo raccomandato per la CPU in millicores.

**Default**: `10`

**Esempio**: `KRR_CPU_MIN=10`

### `KRR_MEM_MIN`
**Scopo**: Imposta il valore minimo raccomandato per la memoria in MB.

**Default**: `100`

**Esempio**: `KRR_MEM_MIN=100`

---

## Threading Settings

### `KRR_MAX_WORKERS`
**Scopo**: Numero massimo di worker da usare per richieste asincrone.

**Default**: `10`

**Esempio**: `KRR_MAX_WORKERS=1`

---

## Job Grouping Settings

### `KRR_JOB_GROUPING_LABELS`
**Scopo**: Nome/i delle label da usare per raggruppare i job nel tipo di workload GroupedJob. Può essere una singola label o label separate da virgola.

**Default**: Nessuno

**Esempio**: `KRR_JOB_GROUPING_LABELS=app,team`

### `KRR_JOB_GROUPING_LIMIT`
**Scopo**: Numero massimo di job/pod da interrogare per gruppo GroupedJob.

**Default**: `500`

**Esempio**: `KRR_JOB_GROUPING_LIMIT=500`

---

## Job Discovery Settings

### `KRR_DISCOVERY_JOB_BATCH_SIZE`
**Scopo**: Dimensione del batch per le chiamate API Kubernetes ai job.

**Default**: `5000`

**Esempio**: `KRR_DISCOVERY_JOB_BATCH_SIZE=5000`

### `KRR_DISCOVERY_JOB_MAX_BATCHES`
**Scopo**: Numero massimo di batch di job da processare per prevenire loop infiniti.

**Default**: `100`

**Esempio**: `KRR_DISCOVERY_JOB_MAX_BATCHES=100`

---

## Logging Settings

### `KRR_FORMATTER`
**Scopo**: Formato dell'output.

**Default**: `table`

**Opzioni**: `json`, `pprint`, `table`, `yaml`, `csv`, `csv-raw`, `html`

**Esempio**: `KRR_FORMATTER=table`

### `KRR_VERBOSE`
**Scopo**: Abilita la modalità verbose (output dettagliato).

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_QUIET`
**Scopo**: Abilita la modalità quiet (output ridotto).

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_LOGTOSTDERR`
**Scopo**: Passa i log a stderr invece di stdout.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_WIDTH`
**Scopo**: Larghezza dell'output. Per default, usa la larghezza della console.

**Default**: Larghezza console

**Esempio**: `KRR_WIDTH=120`

---

## Output Settings

### `KRR_SHOW_CLUSTER_NAME`
**Scopo**: Nell'output tabellare, mostra sempre il nome del cluster anche per un singolo cluster.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_EXCLUDE_SEVERITY`
**Scopo**: Se includere o meno la severity nell'output.

**Default**: `true` (la severity è inclusa)

**Valori**: `true` | `false`

**Nota**: Impostare a `false` per escludere la severity dall'output.

### `KRR_FILEOUTPUT`
**Scopo**: Nome del file in cui scrivere l'output. Se non specificato, l'output su file è disabilitato.

**Default**: Nessuno (output su file disabilitato)

**Esempio**: `KRR_FILEOUTPUT=/output/report.csv`

### `KRR_FILEOUTPUT_DYNAMIC`
**Scopo**: Ignora `KRR_FILEOUTPUT` e scrive i file nella directory corrente nel formato `krr-{datetime}.{format}` (es. krr-20240518223924.csv).

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_SLACKOUTPUT`
**Scopo**: Invia l'output a Slack. Valori che iniziano con # saranno interpretati come nomi di canale, ma altri valori possono riferirsi a ID di canale. La variabile d'ambiente `SLACK_BOT_TOKEN` deve esistere con permessi: `chat:write`, `files:write`, `chat:write.public`. Il bot deve essere aggiunto al canale.

**Default**: Nessuno

**Esempio**: `KRR_SLACKOUTPUT=#my-channel`

### `KRR_SLACKTITLE`
**Scopo**: Titolo del messaggio Slack. Se non fornito, userà il default 'Kubernetes Resource Report for <environment>'.

**Default**: `Kubernetes Resource Report for <environment>`

**Esempio**: `KRR_SLACKTITLE=KRR Report`

### `KRR_AZUREBLOBOUTPUT`
**Scopo**: Fornisci l'URL SAS di Azure Blob Storage (con il container) per caricare il file di output (es. https://mystorageaccount.blob.core.windows.net/container?sv=...). Il nome del file verrà aggiunto automaticamente.

**Default**: Nessuno

**Esempio**: `KRR_AZUREBLOBOUTPUT=https://mystorageaccount.blob.core.windows.net/container?sv=...`

### `KRR_TEAMS_WEBHOOK`
**Scopo**: URL del webhook Microsoft Teams per inviare notifiche quando i file vengono caricati su Azure Blob Storage.

**Default**: Nessuno

**Esempio**: `KRR_TEAMS_WEBHOOK=https://outlook.office.com/webhook/...`

### `KRR_AZURE_SUBSCRIPTION_ID`
**Scopo**: ID della Subscription Azure per i link al portale Azure nelle notifiche Teams.

**Default**: Nessuno

**Esempio**: `KRR_AZURE_SUBSCRIPTION_ID=your-subscription-id`

### `KRR_AZURE_RESOURCE_GROUP`
**Scopo**: Resource Group Azure per i link al portale Azure nelle notifiche Teams.

**Default**: Nessuno

**Esempio**: `KRR_AZURE_RESOURCE_GROUP=your-resource-group`

---

## Publish Scan Settings

### `KRR_PUBLISH_SCAN_URL`
**Scopo**: Invia l'output a un'istanza di robusta_runner.

**Default**: Nessuno

**Esempio**: `KRR_PUBLISH_SCAN_URL=https://api.example.com/scans`

### `KRR_START_TIME`
**Scopo**: Tempo di inizio della scansione.

**Default**: Nessuno

**Esempio**: `KRR_START_TIME=2024-01-01T00:00:00Z`

### `KRR_SCAN_ID`
**Scopo**: Identificatore UUID della scansione.

**Default**: Nessuno

**Esempio**: `KRR_SCAN_ID=uuid-here`

### `KRR_NAMED_SINKS`
**Scopo**: Lista di sink a cui inviare la scansione.

**Default**: Nessuno

**Esempio**: `KRR_NAMED_SINKS=sink1,sink2`

---

## Strategy Settings (Common)

Queste impostazioni sono comuni a tutte le strategie.

### `KRR_HISTORY_DURATION`
**Scopo**: Durata dei dati storici da utilizzare (in ore).

**Default**: `336` (14 giorni)

**Esempio**: `KRR_HISTORY_DURATION=48`

### `KRR_TIMEFRAME_DURATION`
**Scopo**: Il passo per i dati storici (in minuti). Determina la granularità dei dati raccolti.

**Default**: `1.25`

**Esempio**: `KRR_TIMEFRAME_DURATION=5.0`

### `KRR_POINTS_REQUIRED`
**Scopo**: Numero di punti dati richiesti per fare una raccomandazione per una risorsa.

**Default**: `100`

**Esempio**: `KRR_POINTS_REQUIRED=100`

### `KRR_ALLOW_HPA`
**Scopo**: Se calcolare raccomandazioni anche quando c'è un HPA scaler definito su quella risorsa.

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_USE_OOMKILL_DATA`
**Scopo**: Se aumentare la memoria quando vengono rilevati eventi OOMKill (sperimentale).

**Default**: `true`

**Valori**: `true` | `false`

---

## Strategy: simple

Impostazioni specifiche per la strategia `simple`.

### `KRR_CPU_PERCENTILE`
**Scopo**: Il percentile da usare per la raccomandazione CPU.

**Default**: `95`

**Esempio**: `KRR_CPU_PERCENTILE=95`

### `KRR_MEMORY_BUFFER_PERCENTAGE`
**Scopo**: La percentuale di buffer aggiunta al picco di utilizzo della memoria per la raccomandazione memoria.

**Default**: `15`

**Esempio**: `KRR_MEMORY_BUFFER_PERCENTAGE=15`

### `KRR_OOM_MEMORY_BUFFER_PERCENTAGE`
**Scopo**: Quale percentuale aumentare la memoria quando ci sono eventi OOMKill.

**Default**: `25`

**Esempio**: `KRR_OOM_MEMORY_BUFFER_PERCENTAGE=25`

---

## Strategy: simple-limit

Impostazioni specifiche per la strategia `simple-limit`.

### `KRR_CPU_REQUEST`
**Scopo**: Il percentile da usare per la CPU request.

**Default**: `66`

**Esempio**: `KRR_CPU_REQUEST=66`

### `KRR_CPU_LIMIT`
**Scopo**: Il percentile da usare per la CPU limit.

**Default**: `96`

**Esempio**: `KRR_CPU_LIMIT=96`

### `KRR_MEMORY_BUFFER_PERCENTAGE`
**Scopo**: La percentuale di buffer aggiunta al picco di utilizzo della memoria per la raccomandazione memoria.

**Default**: `15`

**Esempio**: `KRR_MEMORY_BUFFER_PERCENTAGE=15`

### `KRR_OOM_MEMORY_BUFFER_PERCENTAGE`
**Scopo**: Quale percentuale aumentare la memoria quando ci sono eventi OOMKill.

**Default**: `25`

**Esempio**: `KRR_OOM_MEMORY_BUFFER_PERCENTAGE=25`

---

## Strategy: ai-assisted

Impostazioni specifiche per la strategia `ai-assisted`.

### `KRR_AI_PROVIDER`
**Scopo**: Provider AI da utilizzare. Auto-rilevato dalle variabili d'ambiente se non specificato.

**Default**: Nessuno (auto-rilevato)

**Opzioni**: `openai`, `gemini`, `anthropic`, `ollama`

**Esempio**: `KRR_AI_PROVIDER=gemini`

### `KRR_AI_MODEL`
**Scopo**: Nome del modello AI. Usa il default del provider se non specificato.

**Default**: Default del provider

**Esempi**:
- OpenAI: `gpt-4`, `gpt-3.5-turbo`
- Gemini: `gemini-3-flash-preview`, `gemini-pro`
- Anthropic: `claude-3-sonnet`, `claude-3-opus`

**Esempio**: `KRR_AI_MODEL=gemini-3-flash-preview`

### `KRR_AI_API_KEY`
**Scopo**: Chiave API AI. Fallback alle variabili d'ambiente: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.

**Default**: Nessuno (usa le variabili d'ambiente)

**Esempio**: `KRR_AI_API_KEY=YOUR_AI_API_KEY`

### `KRR_AI_TEMPERATURE`
**Scopo**: Temperatura AI per la casualità della risposta (0=deterministico, 2=creativo).

**Default**: `0.3`

**Esempio**: `KRR_AI_TEMPERATURE=0.3`

### `KRR_AI_MAX_TOKENS`
**Scopo**: Numero massimo di token nella risposta AI. Un default più alto assicura risposte JSON complete.

**Default**: `3000`

**Esempio**: `KRR_AI_MAX_TOKENS=5000`

### `KRR_AI_COMPACT_MODE`
**Scopo**: Comprimi le statistiche nel prompt per ridurre l'uso di token (~60% di riduzione).

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_AI_EXCLUDE_SIMPLE_REFERENCE`
**Scopo**: Escludi il baseline della strategia Simple dal prompt AI (per default è incluso).

**Default**: `false`

**Valori**: `true` | `false`

### `KRR_AI_TIMEOUT`
**Scopo**: Timeout per le chiamate API AI in secondi.

**Default**: `60`

**Esempio**: `KRR_AI_TIMEOUT=60`

### `KRR_CPU_PERCENTILE`
**Scopo**: Percentile CPU per il confronto di riferimento con la strategia Simple.

**Default**: `95`

**Esempio**: `KRR_CPU_PERCENTILE=95`

### `KRR_MEMORY_BUFFER_PERCENTAGE`
**Scopo**: Percentuale di buffer memoria per il confronto di riferimento con la strategia Simple.

**Default**: `15`

**Esempio**: `KRR_MEMORY_BUFFER_PERCENTAGE=15`

---

## External API Keys

Queste variabili d'ambiente sono alternative ai flag specifici e vengono utilizzate automaticamente se non vengono fornite chiavi API tramite le variabili specifiche.

### `OPENAI_API_KEY`
**Scopo**: Chiave API per OpenAI. Utilizzata automaticamente quando `KRR_AI_PROVIDER=openai` e `KRR_AI_API_KEY` non è impostato.

**Default**: Nessuno

**Esempio**: `OPENAI_API_KEY=your-openai-key`

### `GEMINI_API_KEY`
**Scopo**: Chiave API per Google Gemini. Utilizzata automaticamente quando `KRR_AI_PROVIDER=gemini` e `KRR_AI_API_KEY` non è impostato.

**Default**: Nessuno

**Esempio**: `GEMINI_API_KEY=your-gemini-key`

### `ANTHROPIC_API_KEY`
**Scopo**: Chiave API per Anthropic Claude. Utilizzata automaticamente quando `KRR_AI_PROVIDER=anthropic` e `KRR_AI_API_KEY` non è impostato.

**Default**: Nessuno

**Esempio**: `ANTHROPIC_API_KEY=your-anthropic-key`

### `SLACK_BOT_TOKEN`
**Scopo**: Token del bot Slack. Richiesto per inviare output a Slack tramite `KRR_SLACKOUTPUT`. Il bot deve avere i permessi: `chat:write`, `files:write`, `chat:write.public`.

**Default**: Nessuno

**Esempio**: `SLACK_BOT_TOKEN=xoxb-your-slack-token`

---

## Note Importanti

### Precedenza delle Variabili
Le variabili d'ambiente hanno la precedenza sui valori di default ma possono essere sovrascritte da argomenti della linea di comando.

### File .env
Per facilità d'uso con Docker, puoi copiare il file `.env.docker.example` in `.env` e personalizzare i valori:

```bash
cp .env.docker.example .env
# Modifica .env con i tuoi valori
```

### Valori Booleani
Per le variabili booleane, usa:
- `true` per attivare
- `false` (o ometti la variabile) per disattivare

### Strategie
Ricorda di selezionare la strategia appropriata tramite `KRR_STRATEGY` e configurare solo le variabili rilevanti per quella strategia.

### Docker Compose
Quando si usa Docker Compose, assicurati che il file `.env` sia nella stessa directory del `docker-compose.yml`.
