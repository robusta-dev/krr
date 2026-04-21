# 📊 Report Completo — KRR (Kubernetes Resource Recommender)

> **Progetto**: krr-fork  
> **Tipo**: CLI Tool per ottimizzazione risorse Kubernetes  
> **Basato su**: [Robusta KRR](https://github.com/robusta-dev/krr) (fork con estensioni custom)  
> **Linguaggio**: Python 3.9+  
> **Licenza**: MIT  
> **Data report**: Marzo 2025

---

## Indice

1. [Panoramica Generale](#1-panoramica-generale)
2. [Architettura del Progetto](#2-architettura-del-progetto)
3. [Flusso di Esecuzione](#3-flusso-di-esecuzione)
4. [Strategie di Raccomandazione](#4-strategie-di-raccomandazione)
5. [Tipi di Workload Supportati](#5-tipi-di-workload-supportati)
6. [Backend Metriche Supportati](#6-backend-metriche-supportati)
7. [Formati di Output e Canali di Distribuzione](#7-formati-di-output-e-canali-di-distribuzione)
8. [Sistema di Severity](#8-sistema-di-severity)
9. [Integrazione AI (LLM)](#9-integrazione-ai-llm)
10. [Componente Enforcer (Auto-Apply)](#10-componente-enforcer-auto-apply)
11. [Infrastruttura Docker e Deployment](#11-infrastruttura-docker-e-deployment)
12. [Personalizzazioni del Fork](#12-personalizzazioni-del-fork)
13. [Analisi Output CSV di Produzione](#13-analisi-output-csv-di-produzione)
14. [Configurazione Corrente (.env)](#14-configurazione-corrente-env)
15. [Riepilogo Capacità](#15-riepilogo-capacità)

---

## 1. Panoramica Generale

**KRR (Kubernetes Resource Recommender)** è un tool CLI per l'**ottimizzazione delle risorse** (CPU e Memory) nei cluster Kubernetes. Analizza i dati storici di utilizzo raccolti da **Prometheus** (e sistemi compatibili) e genera **raccomandazioni** su requests e limits per ogni container di ogni workload nel cluster.

### Cosa fa in pratica

KRR risponde alla domanda: **"Quanto CPU e RAM dovrebbe avere ogni container?"**

- Se un container ha `500m` CPU allocati ma ne usa solo `65m` → KRR raccomanda di ridurre a `65m`
- Se un container ha `2000Mi` RAM allocati ma ne usa `2662Mi` → KRR raccomanda di aumentare a `2662Mi`

### Perché è utile

Secondo uno [studio Sysdig](https://sysdig.com/blog/millions-wasted-kubernetes/), in media i cluster Kubernetes hanno:

- **69% di CPU inutilizzata**
- **18% di memoria inutilizzata**

KRR permette di identificare e correggere queste inefficienze, riducendo i costi cloud e migliorando le performance.

### Vantaggi rispetto a Kubernetes VPA

| Caratteristica | KRR | Kubernetes VPA |
|---|---|---|
| Installazione nel cluster | ❌ Non richiesta | ✅ Obbligatoria |
| Configurazione per workload | ❌ Non necessaria | ✅ Richiede oggetto VPA per ogni workload |
| Risultati immediati | ✅ Sì (con Prometheus attivo) | ❌ Richiede tempo per raccogliere dati |
| Formati di reporting | ✅ JSON, CSV, HTML, YAML, Web UI | ❌ Non supportato |
| Estensibilità | ✅ Strategie custom in Python | ⚠️ Limitata |
| Supporto HPA | ✅ Con flag `--allow-hpa` | ❌ Non supportato |

---

## 2. Architettura del Progetto

### 2.1 Struttura delle Directory

```
krr-fork/
├── krr.py                              # Entry point principale
├── robusta_krr/                         # Package principale
│   ├── __init__.py                      # Espone run() e __version__
│   ├── main.py                          # CLI Typer, caricamento comandi dinamici
│   ├── core/                            # Core del sistema
│   │   ├── runner.py                    # Orchestratore principale (Runner)
│   │   ├── abstract/                    # Classi base astratte
│   │   │   ├── strategies.py            # BaseStrategy, StrategySettings
│   │   │   ├── formatters.py            # Registry dei formatter
│   │   │   └── metrics.py              # BaseMetric
│   │   ├── integrations/                # Integrazioni esterne
│   │   │   ├── kubernetes/              # Loader Kubernetes (discovery workload)
│   │   │   │   ├── __init__.py          # KubernetesLoader, ClusterLoader
│   │   │   │   └── config_patch.py      # Patch configurazione K8s
│   │   │   ├── prometheus/              # Loader Prometheus (metriche storiche)
│   │   │   │   ├── loader.py            # PrometheusMetricsLoader
│   │   │   │   ├── metrics/             # Query PromQL
│   │   │   │   │   ├── base.py          # PrometheusMetric base
│   │   │   │   │   ├── cpu.py           # CPULoader, PercentileCPULoader, CPUAmountLoader
│   │   │   │   │   ├── memory.py        # MemoryLoader, MaxMemoryLoader, MaxOOMKilledMemoryLoader
│   │   │   │   │   └── gcp/             # Metriche GCP-specifiche
│   │   │   │   │       ├── cpu.py       # GcpCPULoader, GcpPercentileCPULoader
│   │   │   │   │       ├── memory.py    # GcpMaxMemoryLoader, GcpMemoryAmountLoader
│   │   │   │   │       └── anthos/      # Metriche Anthos on-prem
│   │   │   │   └── metrics_service/     # Service layer per diversi backend
│   │   │   │       ├── base_metric_service.py
│   │   │   │       ├── prometheus_metrics_service.py
│   │   │   │       ├── thanos_metrics_service.py
│   │   │   │       ├── victoria_metrics_service.py
│   │   │   │       ├── mimir_metrics_service.py
│   │   │   │       ├── gcp_metrics_service.py
│   │   │   │       └── anthos_metrics_service.py
│   │   │   └── ai/                      # Provider AI per strategia ai-assisted
│   │   │       ├── base.py              # AIProvider (classe astratta)
│   │   │       ├── openai_provider.py   # OpenAI GPT
│   │   │       ├── gemini_provider.py   # Google Gemini
│   │   │       ├── anthropic_provider.py # Anthropic Claude
│   │   │       └── ollama_provider.py   # Ollama (locale)
│   │   └── models/                      # Modelli dati
│   │       ├── config.py                # Config, Settings (Pydantic)
│   │       ├── objects.py               # K8sObjectData, PodData, HPAData
│   │       ├── result.py                # Result, ResourceScan, Severity
│   │       ├── allocations.py           # ResourceType, ResourceAllocations
│   │       └── severity.py              # Calcolo severity (GOOD/OK/WARNING/CRITICAL)
│   ├── strategies/                      # Strategie di raccomandazione
│   │   ├── __init__.py                  # Registra tutte le strategie
│   │   ├── simple.py                    # Strategia "simple" (default)
│   │   ├── simple_limit.py             # Strategia "simple_limit"
│   │   ├── ai_assisted.py              # Strategia "ai-assisted" (LLM)
│   │   └── ai_prompts.py               # Generazione prompt e estrazione statistiche
│   ├── formatters/                      # Output formatters
│   │   ├── csv.py                       # CSV formattato
│   │   ├── csv_raw.py                   # CSV dati grezzi
│   │   ├── json.py                      # JSON
│   │   ├── yaml.py                      # YAML
│   │   ├── html.py                      # HTML
│   │   ├── table.py                     # Tabella CLI (Rich)
│   │   └── pprint.py                    # Python pprint
│   └── utils/                           # Utility
│       ├── resource_units.py            # Parsing unità K8s (500m, 2Gi, etc.)
│       ├── service_discovery.py         # Auto-discovery servizi metriche
│       ├── progress_bar.py              # Barra di progresso
│       ├── version.py                   # Gestione versione
│       └── ...
├── enforcer/                            # Webhook mutante per auto-apply
│   ├── enforcer_main.py                 # FastAPI webhook server
│   ├── patch_manager.py                 # Logica di patching risorse
│   ├── model.py                         # Modelli (PodOwner, WorkloadRecommendation)
│   ├── dal/                             # Data Access Layer
│   │   └── supabase_dal.py              # Connessione Supabase
│   └── resources/                       # Store per owner e raccomandazioni
├── docker-entrypoint.sh                 # Entrypoint Docker parametrizzato
├── run_krr_docker.sh                    # Script runner per GCP
├── Dockerfile.gcloud                    # Dockerfile con gcloud SDK
├── .env                                 # Configurazione ambiente
└── tests/                               # Test suite
```

### 2.2 Dipendenze Principali

| Dipendenza | Ruolo |
|---|---|
| `typer` | Framework CLI |
| `pydantic` | Validazione dati e modelli |
| `kubernetes` | Client API Kubernetes |
| `prometrix` | Client Prometheus |
| `numpy` | Calcoli statistici (percentili, trend) |
| `rich` | Output formattato in console |
| `requests` | Chiamate HTTP (AI providers, Azure, Teams) |
| `tenacity` | Retry logic |
| `slack_sdk` | Integrazione Slack |
| `fastapi` | Server webhook (Enforcer) |

---

## 3. Flusso di Esecuzione

### 3.1 Pipeline Principale

```
1. krr.py
   └── robusta_krr.run()

2. main.py → load_commands()
   └── Registra ogni strategia come comando Typer (simple, simple_limit, ai-assisted)

3. Utente esegue: `krr simple -n icaro -p <prometheus_url>`

4. Config viene creata e validata (Pydantic BaseSettings)
   └── Tutti i parametri CLI → Config object → settings globale

5. Runner.run()
   ├── _greet()              → Mostra versione, strategia, formatter
   ├── load_kubeconfig()     → Carica kubeconfig (in-cluster o locale)
   └── _collect_result()     → Pipeline principale:
       │
       ├── KubernetesLoader.list_clusters()
       │   └── Determina cluster da analizzare
       │
       ├── KubernetesLoader.list_scannable_objects()
       │   └── Per ogni cluster:
       │       ├── _list_deployments()
       │       ├── _list_all_statefulsets()
       │       ├── _list_all_daemon_set()
       │       ├── _list_all_jobs()          (batched, 5000/batch)
       │       ├── _list_all_cronjobs()
       │       ├── _list_rollouts()          (Argo CRD)
       │       ├── _list_strimzipodsets()    (Strimzi CRD)
       │       ├── _list_deploymentconfig()  (OpenShift CRD)
       │       └── _list_all_groupedjobs()   (custom grouping)
       │
       ├── Per ogni workload → _calculate_object_recommendations():
       │   ├── PrometheusMetricsLoader.load_pods()
       │   │   └── Scopre pod storici via kube_pod_owner, kube_replicaset_owner
       │   ├── PrometheusMetricsLoader.gather_data()
       │   │   └── Esegue query PromQL per ogni metrica della strategia
       │   └── Strategy.run(metrics, object)
       │       └── Calcola raccomandazione CPU/Memory
       │
       └── ResourceScan.calculate()
           └── Calcola severity confrontando allocazione corrente vs raccomandata

6. _process_result()
   ├── Formatter.format(result)     → Genera output nel formato scelto
   ├── File output                  → Scrive su file (se configurato)
   ├── Slack output                 → Upload + messaggio Slack
   ├── Azure Blob output            → Upload su Azure Blob Storage
   ├── Teams notification           → Adaptive Card su Teams
   └── Publish scan                 → Invio a Robusta runner
```

### 3.2 Diagramma del Flusso Dati

```
Kubernetes API                    Prometheus / GMP / Thanos / VM
     │                                        │
     ▼                                        ▼
┌─────────────────┐              ┌──────────────────────────┐
│  K8s Loader     │              │  Prometheus Loader       │
│  (Workloads)    │              │  (Metriche storiche)     │
│                 │              │                          │
│  Deployment     │              │  container_cpu_usage_*   │
│  StatefulSet    │              │  container_memory_*      │
│  DaemonSet      │              │  kube_pod_owner          │
│  Job/CronJob    │              │  kube_replicaset_owner   │
│  Rollout        │              │  kube_pod_status_phase   │
│  GroupedJob     │              │                          │
└────────┬────────┘              └────────────┬─────────────┘
         │                                    │
         │  K8sObjectData                     │  MetricsPodData
         │  (nome, namespace, HPA,            │  (CPU usage, Memory usage,
         │   allocazioni correnti, labels)    │   data points, OOMKills)
         ▼                                    ▼
      ┌────────────────────────────────��─────────┐
      │           Strategy Engine                │
      │                                          │
      │  ┌─────────┐ ┌──────────────┐ ┌───────┐ │
      │  │ simple  │ │ simple_limit │ │  AI   │ │
      │  └─────────┘ └──────────────┘ └───────┘ │
      │                                          │
      │  Input:  metriche storiche + metadata    │
      │  Output: CPU req/lim, Memory req/lim     │
      └──────────────────┬───────────────────────┘
                         │
                         ▼  RunResult
      ┌──────────────────────────────────────────┐
      │         Severity Calculator              │
      │                                          │
      │  Confronta: allocazione corrente         │
      │         vs. raccomandazione              │
      │                                          │
      │  → GOOD / OK / WARNING / CRITICAL        │
      └──────────────────┬───────────────────────┘
                         │
                         ▼  Result (con score A-F)
      ┌──────────────────────────────────────────┐
      │           Formatter                      │
      │  CSV / JSON / YAML / HTML / Table        │
      └──────────────────┬───────────────────────┘
                         │
                         ▼
      ┌──────────────────────────────────────────┐
      │           Output Channels                │
      │                                          │
      │  Console │ File │ Slack │ Azure │ Teams  │
      └────────────────────────────���─────────────┘
```

---

## 4. Strategie di Raccomandazione

KRR supporta **3 strategie** per calcolare le raccomandazioni. Ogni strategia è una sottoclasse di `BaseStrategy` e viene automaticamente registrata come comando CLI.

### 4.1 Strategia `simple` (Default)

**File**: `robusta_krr/strategies/simple.py`

| Risorsa | Request | Limit |
|---|---|---|
| **CPU** | 95° percentile dell'utilizzo storico | `None` (unset → burst illimitato) |
| **Memory** | max(utilizzo storico) + 15% buffer | max(utilizzo storico) + 15% buffer |

**Metriche Prometheus utilizzate**:

| Metrica | Query PromQL | Scopo |
|---|---|---|
| `PercentileCPULoader` | `quantile_over_time(0.95, max(rate(container_cpu_usage_seconds_total[step])) by (...) [duration:step])` | Percentile CPU |
| `MaxMemoryLoader` | `max_over_time(max(container_memory_working_set_bytes) by (...) [duration:step])` | Picco memoria |
| `CPUAmountLoader` | `count_over_time(...)` | Conteggio data points CPU |
| `MemoryAmountLoader` | `count_over_time(...)` | Conteggio data points Memory |
| `MaxOOMKilledMemoryLoader` | Join tra `kube_pod_container_resource_limits` e `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}` | Rilevamento OOMKill |

**Parametri configurabili**:

```bash
--cpu-percentile       # Default: 95 (percentile CPU)
--memory-buffer-percentage  # Default: 15 (% buffer sulla memoria)
--points-required      # Default: 100 (data points minimi)
--allow-hpa            # Default: false (analizza anche con HPA)
--use-oomkill-data     # Default: false (considera OOMKill)
--oom-memory-buffer-percentage  # Default: 25 (% buffer su OOMKill)
--history-duration     # Default: 336 ore (14 giorni)
--timeframe-duration   # Default: 1.25 minuti (step)
```

**Logica decisionale**:

1. Se ci sono meno di `points_required` data points → `"Not enough data"` (valore `?`)
2. Se c'è HPA configurato e `--allow-hpa` non è attivo → `"HPA detected"` (valore `?`)
3. Altrimenti → calcola percentile CPU e max+buffer Memory

### 4.2 Strategia `simple_limit`

**File**: `robusta_krr/strategies/simple_limit.py`

| Risorsa | Request | Limit |
|---|---|---|
| **CPU** | 66° percentile | 96° percentile |
| **Memory** | max + 15% buffer | max + 15% buffer |

**Differenza chiave**: A differenza di `simple`, questa strategia **imposta anche un CPU limit** basato su un percentile più alto (96°). Usa `CPULoader` (raw rate data) invece di `PercentileCPULoader` per calcolare i percentili lato client.

**Parametri aggiuntivi**:

```bash
--cpu-request   # Default: 66 (percentile per request)
--cpu-limit     # Default: 96 (percentile per limit)
```

### 4.3 Strategia `ai-assisted` (LLM-Powered)

**File**: `robusta_krr/strategies/ai_assisted.py` + `robusta_krr/strategies/ai_prompts.py`

Questa strategia utilizza **Large Language Models** per analizzare le metriche storiche e fornire raccomandazioni intelligenti basate su pattern, trend e anomalie.

**Funzionamento**:

1. **Estrazione statistiche** (`extract_comprehensive_stats`):
   - CPU: percentili (P50, P75, P90, P95, P99), media, deviazione standard, trend (regressione lineare), conteggio spike
   - Memory: max, media, deviazione standard, OOMKill
   - Contesto: pod count, HPA, allocazioni correnti, warning

2. **Generazione prompt** (`format_messages`):
   - System prompt con istruzioni dettagliate per l'AI
   - User prompt con tutte le statistiche del workload
   - Formato output JSON richiesto con 6 campi obbligatori

3. **Chiamata AI** (`provider.analyze_metrics`):
   - Retry automatico (3 tentativi con backoff esponenziale)
   - Parsing JSON dalla risposta
   - Validazione campi obbligatori

4. **Validazione e clamping**:
   - CPU: min 10m, max 16 cores
   - Memory: min 100Mi, max 64Gi
   - Sanity check vs strategia Simple (warning se >5x CPU o >3x Memory)

**Provider supportati**:

| Provider | Modello Default | Autenticazione | Endpoint |
|---|---|---|---|
| **OpenAI** | `gpt-4o-mini` | `OPENAI_API_KEY` | `api.openai.com/v1/chat/completions` |
| **Gemini** | `gemini-2.0-flash-exp` | `GEMINI_API_KEY` | `generativelanguage.googleapis.com/v1beta/models/` |
| **Anthropic** | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` | `api.anthropic.com/v1/messages` |
| **Ollama** | `llama3.2` | Nessuna (locale) | `localhost:11434/api/generate` |

**Parametri specifici**:

```bash
--ai-provider          # openai/gemini/anthropic/ollama (auto-detect da env)
--ai-model             # Nome modello specifico
--ai-api-key           # API key (override env var)
--ai-temperature       # Default: 0.3 (0=deterministico, 2=creativo)
--ai-max-tokens        # Default: 3000
--ai-compact-mode      # Riduce token usage ~60%
--ai-exclude-simple-reference  # Esclude baseline Simple dal prompt
--ai-timeout           # Default: 60 secondi
```

---

## 5. Tipi di Workload Supportati

KRR supporta **9 tipi di workload Kubernetes**:

| Tipo | API | Note |
|---|---|---|
| **Deployment** | `apps/v1` | Standard, il più comune |
| **StatefulSet** | `apps/v1` | Workload stateful |
| **DaemonSet** | `apps/v1` | Pod su ogni nodo |
| **Job** | `batch/v1` | Job singoli (esclusi quelli di CronJob e GroupedJob) |
| **CronJob** | `batch/v1` | Job schedulati periodicamente |
| **Rollout** | `argoproj.io/v1alpha1` | Argo Rollouts (CRD) |
| **DeploymentConfig** | `apps.openshift.io/v1` | OpenShift (CRD) |
| **StrimziPodSet** | `core.strimzi.io/v1beta2` | Strimzi Kafka (CRD) |
| **GroupedJob** | Virtuale | Raggruppamento custom di Job per label |

### GroupedJob (Feature Custom del Fork)

I **GroupedJob** permettono di raggruppare Job che condividono determinate label per ottenere raccomandazioni aggregate. Utile per batch jobs, pipeline di data processing, o qualsiasi workload dove si vuole analizzare l'utilizzo risorse su più job correlati.

```bash
# Raggruppa job per label "app" e "team"
krr simple --job-grouping-labels app,team

# Limita a 3 job per gruppo
krr simple --job-grouping-labels app,team --job-grouping-limit 3
```

**Implementazione**: Il `ClusterLoader` esegue una discovery batch dei Job, li raggruppa per label, e crea oggetti `K8sObjectData` virtuali con `kind="GroupedJob"`. I pod vengono poi scoperti usando il label selector del gruppo.

---

## 6. Backend Metriche Supportati

### 6.1 Tabella Riepilogativa

| Backend | Auto-Discovery | Metriche | Note |
|---|---|---|---|
| **Prometheus** | ✅ Via label selector | Standard (`container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`) | Default |
| **Thanos** | ✅ Via label selector | Standard | Query frontend |
| **Victoria Metrics** | ✅ Via label selector | Standard | vmselect/vmsingle |
| **Grafana Mimir** | ✅ Via label selector | Standard | Query frontend |
| **GCP Managed Prometheus** | ❌ URL esplicito | GCP (`kubernetes.io/container/cpu/core_usage_time`, `kubernetes.io/container/memory/used_bytes`) | UTF-8 PromQL |
| **GCP Anthos** | ❌ URL esplicito | Anthos (`kubernetes.io/anthos/*`) | Per cluster on-prem |
| **AWS Managed Prometheus** | ❌ URL + SigV4 | Standard | Autenticazione AWS |
| **Azure Managed Prometheus** | ❌ URL + Bearer | Standard | Token Azure |
| **Coralogix** | ❌ URL + token | Standard | Managed Prometheus |
| **Grafana Cloud** | ❌ URL + auth | Standard | Managed Prometheus |

### 6.2 Auto-Discovery

Per **Prometheus**, KRR cerca servizi Kubernetes con queste label:

```python
"app=kube-prometheus-stack-prometheus"
"app=prometheus,component=server"
"app=prometheus-server"
"app=prometheus-operator-prometheus"
"app=rancher-monitoring-prometheus"
"app=prometheus-prometheus"
```

Per **Thanos**:

```python
"app.kubernetes.io/component=query,app.kubernetes.io/name=thanos"
"app.kubernetes.io/name=thanos-query"
"app=thanos-query"
"app=thanos-querier"
```

Per **Victoria Metrics**:

```python
"app.kubernetes.io/name=vmsingle"
"app.kubernetes.io/name=victoria-metrics-single"
"app.kubernetes.io/name=vmselect"
"app=vmselect"
```

### 6.3 GCP Managed Prometheus (Dettaglio)

Il servizio GCP utilizza metriche con naming convention diversa e richiede **UTF-8 PromQL**:

```promql
-- Standard Prometheus
container_cpu_usage_seconds_total{namespace="...", pod="...", container="..."}

-- GCP Managed Prometheus
{"__name__"="kubernetes.io/container/cpu/core_usage_time",
 "monitored_resource"="k8s_container",
 "namespace_name"="...",
 "pod_name"="...",
 "container_name"="..."}
```

Il `GcpManagedPrometheusMetricsService` intercetta automaticamente i loader standard e li sostituisce con equivalenti GCP tramite un mapping:

```python
LOADER_MAPPING = {
    "CPULoader": GcpCPULoader,
    "PercentileCPULoader": GcpPercentileCPULoader,
    "CPUAmountLoader": GcpCPUAmountLoader,
    "MaxMemoryLoader": GcpMaxMemoryLoader,
    "MemoryAmountLoader": GcpMemoryAmountLoader,
    "MaxOOMKilledMemoryLoader": GcpMaxOOMKilledMemoryLoader,
}
```

---

## 7. Formati di Output e Canali di Distribuzione

### 7.1 Formati di Output

| Formato | Flag | Descrizione | File |
|---|---|---|---|
| `table` | `-f table` (default) | Tabella CLI colorata con Rich | `formatters/table.py` |
| `csv` | `-f csv` | CSV con diff, requests, limits formattati | `formatters/csv.py` |
| `csv-raw` | `-f csv-raw` | CSV con dati grezzi per calcoli | `formatters/csv_raw.py` |
| `json` | `-f json` | JSON strutturato completo | `formatters/json.py` |
| `yaml` | `-f yaml` | YAML strutturato | `formatters/yaml.py` |
| `html` | `-f html` | Report HTML | `formatters/html.py` |
| `pprint` | `-f pprint` | Python pprint | `formatters/pprint.py` |

### 7.2 Canali di Distribuzione

| Canale | Flag CLI | Descrizione |
|---|---|---|
| **Console** | (default) | Output diretto su stdout |
| **File statico** | `--fileoutput <nome>` | Scrive su file con nome specificato |
| **File dinamico** | `--fileoutput-dynamic` | File con timestamp: `krr-20240518223924.csv` |
| **Slack** | `--slackoutput <canale>` | Upload file + messaggio su canale Slack (richiede `SLACK_BOT_TOKEN`) |
| **Azure Blob Storage** | `--azurebloboutput <SAS_URL>` | Upload su Azure Blob via SAS URL |
| **Microsoft Teams** | `--teams-webhook <URL>` | Notifica Adaptive Card su Teams (con link Azure Portal) |
| **Robusta SaaS** | `--publish_scan_url <URL>` | Invio risultati a Robusta runner per UI web |

### 7.3 Formato CSV (Dettaglio)

Il CSV generato ha questa struttura:

```csv
Namespace,Name,Pods,Old Pods,Type,Container,Severity,CPU Diff,CPU Requests,CPU Limits,Memory Diff,Memory Requests,Memory Limits
```

Dove:
- **CPU Diff**: Differenza totale (per tutti i pod) tra allocato e raccomandato
- **CPU Requests**: `(diff_per_pod) allocato -> raccomandato`
- **CPU Limits**: `allocato -> raccomandato`
- **Severity**: GOOD / OK / WARNING / CRITICAL

---

## 8. Sistema di Severity

La severity viene calcolata confrontando l'**allocazione corrente** con la **raccomandazione** per ogni risorsa.

### 8.1 CPU Severity

| Differenza (|corrente - raccomandato|) | Severity | Colore |
|---|---|---|
| < 100m | **GOOD** | 🟢 Verde |
| 100m – 250m | **OK** | ⚪ Grigio |
| 250m – 500m | **WARNING** | 🟡 Giallo |
| ≥ 500m | **CRITICAL** | 🔴 Rosso |

### 8.2 Memory Severity

| Differenza (|corrente - raccomandato|) | Severity | Colore |
|---|---|---|
| < 100Mi | **GOOD** | 🟢 Verde |
| 100Mi – 250Mi | **OK** | ⚪ Grigio |
| 250Mi – 500Mi | **WARNING** | 🟡 Giallo |
| ≥ 500Mi | **CRITICAL** | 🔴 Rosso |

### 8.3 Casi Speciali

- Se corrente è `None` e raccomandato è `None` → **GOOD**
- Se uno dei due è `None` e l'altro no → **WARNING**
- Se il valore raccomandato è `"?"` (dati insufficienti) → **UNKNOWN**

### 8.4 Score Globale

Il risultato complessivo include uno **score** da 0 a 100 con lettera (A-F):

| Score | Lettera |
|---|---|
| ≥ 90 | **A** |
| 70 – 89 | **B** |
| 55 – 69 | **C** |
| 30 – 54 | **D** |
| < 30 | **F** |

Formula: `score = (total_scans - weighted_issues) / total_scans * 100`  
Dove CRITICAL conta 1.0 e WARNING conta 0.7.

---

## 9. Integrazione AI (LLM)

### 9.1 Architettura AI Provider

Tutti i provider AI implementano la classe astratta `AIProvider` con il pattern **Template Method**:

```python
class AIProvider(abc.ABC):
    def analyze_metrics(self, messages, temperature, max_tokens) -> dict:
        # Metodo concreto con retry logic (3 tentativi)
        payload = self._format_request_body(messages, temperature, max_tokens)
        response = requests.post(self._get_endpoint(), headers=self._get_headers(), json=payload)
        text = self._parse_response(response.json())
        return self._extract_json(text)

    @abc.abstractmethod
    def _get_endpoint(self) -> str: ...
    @abc.abstractmethod
    def _get_headers(self) -> dict: ...
    @abc.abstractmethod
    def _format_request_body(self, messages, temperature, max_tokens) -> dict: ...
    @abc.abstractmethod
    def _parse_response(self, response_json) -> str: ...
```

### 9.2 Dettaglio Provider

| Provider | Endpoint | Auth | Formato Request | JSON Mode |
|---|---|---|---|---|
| **OpenAI** | `api.openai.com/v1/chat/completions` | Bearer token | Messages array | `response_format: {"type": "json_object"}` |
| **Gemini** | `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | API key in URL | Contents/Parts | `responseMimeType: "application/json"` |
| **Anthropic** | `api.anthropic.com/v1/messages` | `x-api-key` header | Messages + system separato | Nessuno (istruzioni nel prompt) |
| **Ollama** | `{host}/api/generate` | Nessuna | Prompt singolo | `format: "json"` |

### 9.3 Statistiche Estratte per l'AI

La funzione `extract_comprehensive_stats` prepara un dizionario completo:

```python
{
    "workload": {"namespace", "name", "kind", "container"},
    "pods": {"current_count", "deleted_count", "total_count", "names"},
    "cpu": {
        "percentiles": {"p50", "p75", "p90", "p95", "p99"},
        "max", "mean", "std",
        "trend_slope",      # Regressione lineare (positivo = crescente)
        "spike_count",      # Valori > 2x media
        "per_pod": {...}
    },
    "memory": {
        "max", "mean", "std",
        "oomkill_detected", "oomkill_max_value",
        "per_pod": {...}
    },
    "allocations": {"cpu": {"request", "limit"}, "memory": {"request", "limit"}},
    "hpa": {"min_replicas", "max_replicas", "target_cpu_utilization", ...},
    "temporal": {"cpu_data_points", "memory_data_points", "total_data_points"}
}
```

### 9.4 Formato Risposta AI Atteso

```json
{
    "cpu_request": 0.25,
    "cpu_limit": null,
    "memory_request": 536870912,
    "memory_limit": 536870912,
    "reasoning": "P95 CPU at 0.18 cores, setting 0.25 for headroom. Memory stable at 480Mi.",
    "confidence": 85
}
```

---

## 10. Componente Enforcer (Auto-Apply)

### 10.1 Panoramica

L'**Enforcer** è un componente separato che implementa un **Kubernetes Mutating Admission Webhook**. Intercetta la creazione di Pod e applica automaticamente le raccomandazioni KRR.

**File principale**: `enforcer/enforcer_main.py`

### 10.2 Architettura

```
Kubernetes API Server
        │
        ▼ (Admission Webhook)
┌───────────────────────┐
│   Enforcer (FastAPI)  │
│   Port 8443 (HTTPS)   │
│                       │
│   /mutate             │ ← Intercetta creazione Pod/ReplicaSet
│   /health             │ ← Health check
│   /recommendations    │ ← API per consultare raccomandazioni
│   /metrics            │ ← Metriche Prometheus
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│   Supabase DAL        │ ← Database raccomandazioni
└─────────���─────────────┘
```

### 10.3 Flusso di Mutazione

1. Un Pod viene creato nel cluster
2. Kubernetes invia una `AdmissionReview` all'Enforcer
3. L'Enforcer:
   - Identifica il **proprietario** del Pod (Deployment, StatefulSet, etc.) tramite `OwnerStore`
   - Cerca le **raccomandazioni** per quel workload in `RecommendationStore` (Supabase)
   - Se trovate, genera **JSON Patch** per modificare le risorse dei container
4. Il Pod viene creato con le risorse ottimizzate

### 10.4 Controllo Opt-in/Opt-out

L'Enforcer supporta annotazioni per controllare il comportamento:

```yaml
metadata:
  annotations:
    admission.robusta.dev/krr-mutation-mode: "enforce"  # Applica raccomandazioni
    admission.robusta.dev/krr-mutation-mode: "ignore"   # Ignora questo pod
```

### 10.5 Metriche Esposte

| Metrica | Tipo | Descrizione |
|---|---|---|
| `pod_admission_mutations` | Counter | Mutazioni pod (labels: mutated, reason) |
| `replicaset_admissions` | Counter | Admission ReplicaSet (labels: operation) |
| `rs_owners_size` | Gauge | Dimensione store owner ReplicaSet |
| `admission_duration` | Histogram | Durata elaborazione admission (labels: kind) |

---

## 11. Infrastruttura Docker e Deployment

### 11.1 Dockerfile.gcloud

Immagine Docker basata su `google-cloud-cli:slim` con:

- **gcloud CLI** + `gke-gcloud-auth-plugin` + `kubectl`
- **Python venv** con tutte le dipendenze KRR
- **Entrypoint** parametrizzato via variabili d'ambiente

```dockerfile
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim
# ... installazione dipendenze ...
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["simple"]
```

### 11.2 docker-entrypoint.sh

Script bash che costruisce il comando KRR da **variabili d'ambiente**. Supporta tutte le opzioni CLI:

| Variabile | Flag CLI | Esempio |
|---|---|---|
| `KRR_STRATEGY` | (primo argomento) | `simple` |
| `KRR_PROMETHEUS_URL` | `--prometheus-url` | `https://monitoring.googleapis.com/...` |
| `KRR_NAMESPACE` | `--namespace` | `icaro` |
| `KRR_FORMATTER` | `--formatter` | `csv` |
| `KRR_HISTORY_DURATION` | `--history-duration` | `230` |
| `KRR_GCP_ANTHOS` | `--gcp-anthos` | `true` |
| `KRR_AI_PROVIDER` | `--ai-provider` | `gemini` |
| ... | ... | ... |

### 11.3 run_krr_docker.sh

Script wrapper che:

1. Carica configurazione da `.env`
2. Ottiene automaticamente il token GCP (`gcloud auth print-access-token`)
3. Costruisce e lancia il container Docker con tutti i parametri
4. Monta `~/.kube/config` e directory `./output`
5. Supporta switch automatico tra strategia `simple` e `ai-assisted`

---

## 12. Personalizzazioni del Fork

Questo fork include diverse **estensioni significative** rispetto all'upstream Robusta KRR:

### 12.1 Nuove Funzionalità

| Feature | Descrizione | File Principali |
|---|---|---|
| **GCP Managed Prometheus** | Supporto nativo per metriche `kubernetes.io/*` con UTF-8 PromQL | `metrics/gcp/`, `gcp_metrics_service.py` |
| **GCP Anthos** | Supporto per cluster on-prem gestiti da Google | `metrics/gcp/anthos/`, `anthos_metrics_service.py` |
| **AI-Assisted Strategy** | Strategia basata su LLM con 4 provider | `strategies/ai_assisted.py`, `ai_prompts.py`, `integrations/ai/` |
| **GroupedJob** | Raggruppamento Job per label | `kubernetes/__init__.py` (sezione GroupedJob) |
| **Azure Blob + Teams** | Upload report su Azure e notifiche Teams | `runner.py` (metodi `_upload_to_azure_blob`, `_notify_teams`) |
| **Batched Job Discovery** | Caricamento job in batch con paginazione | `kubernetes/__init__.py` (`_list_all_jobs`) |
| **Docker GCloud Image** | Immagine Docker con gcloud SDK integrato | `Dockerfile.gcloud`, `docker-entrypoint.sh` |
| **Enforcer Webhook** | Auto-apply raccomandazioni via admission webhook | `enforcer/` |

### 12.2 Miglioramenti

- **Batched job loading** con `discovery_job_batch_size` (default 5000) e `discovery_job_max_batches` (default 100) per gestire cluster con migliaia di job
- **Continue token handling** per paginazione API Kubernetes con gestione token scaduti (HTTP 410)
- **Parametrizzazione completa via env vars** nel docker-entrypoint.sh
- **Script runner** (`run_krr_docker.sh`) per deployment GCP semplificato

---

## 13. Analisi Output CSV di Produzione

### 13.1 Contesto

Il file `output/krr-20260311103848.csv` contiene i risultati di una scansione reale eseguita con:

- **Cluster**: `cluster-icaro-prod` (GKE, europe-west8)
- **Namespace**: `icaro`
- **Strategia**: `simple` con CPU percentile 90°
- **History**: 230 ore (~9.6 giorni)
- **Step**: 2 minuti

### 13.2 Risultati Chiave

| Metrica | Valore |
|---|---|
| **Deployment analizzati** | 35 |
| **CRITICAL** | 28 (80%) |
| **WARNING** | 7 (20%) |
| **GOOD/OK** | 0 (0%) |

### 13.3 Analisi CPU

La stragrande maggioranza dei deployment è **massivamente over-provisioned** in CPU:

| Deployment | CPU Allocata | CPU Raccomandata | Utilizzo Effettivo |
|---|---|---|---|
| `config-server` (2 pod) | 500m × 2 | 11m × 2 | **2.2%** |
| `batch` | 500m | 45m | **9%** |
| `gestoreprocessi` | 500m | 10m | **2%** |
| `camunda` | 500m | 13m | **2.6%** |
| `gateway` | 500m | 185m | **37%** |
| `autorizzazioni` (3 pod) | 500m × 3 | 425m × 3 | **85%** |

**Risparmio CPU stimato**: Da ~17.5 cores allocati a ~3.5 cores raccomandati → **~80% di riduzione**.

### 13.4 Analisi Memory

La situazione memoria è **mista** — alcuni deployment sono over-provisioned, altri sono **sotto-dimensionati**:

#### ⚠️ Deployment SOTTO-DIMENSIONATI (rischio OOMKill)

| Deployment | Memory Allocata | Memory Raccomandata | Differenza |
|---|---|---|---|
| `documenti` | 2000Mi | **11Gi** | +9250Mi ⚠️ |
| `estrazioni` | 2000Mi | **7500Mi** | +5500Mi ⚠️ |
| `interventi` (4 pod) | 2000Mi/pod | **2930Mi/pod** | +930Mi/pod |
| `domande` (3 pod) | 2000Mi/pod | **2927Mi/pod** | +927Mi/pod |
| `agenda` (2 pod) | 2000Mi/pod | **2662Mi/pod** | +662Mi/pod |

#### ✅ Deployment SOVRA-DIMENSIONATI

| Deployment | Memory Allocata | Memory Raccomandata | Risparmio |
|---|---|---|---|
| `affidiadozioni` | 2000Mi | 699Mi | -1301Mi |
| `soggettiesterni` | 2000Mi | 801Mi | -1199Mi |
| `valutazioni` | 2000Mi | 875Mi | -1125Mi |
| `config-server` (2 pod) | 2000Mi/pod | 886Mi/pod | -1114Mi/pod |
| `batch` | 2000Mi | 924Mi | -1076Mi |

### 13.5 Raccomandazioni Operative

1. **URGENTE**: Aumentare la memoria di `documenti` (11Gi necessari vs 2Gi allocati) e `estrazioni` (7.5Gi necessari vs 2Gi allocati) — rischio OOMKill attivo
2. **ALTA PRIORITÀ**: Ridurre CPU requests su tutti i deployment — risparmio ~80%
3. **MEDIA PRIORITÀ**: Ribilanciare memoria sui deployment over-provisioned
4. **NOTA**: I CPU limits sono stati tutti impostati a `unset` dalla strategia `simple` (best practice per permettere burst)

---

## 14. Configurazione Corrente (.env)

```bash
# Cluster Target
PROJECT_ID="icarocloud-prod"
CLUSTER_NAME="cluster-icaro-prod"
USE_ANTHOS=""                    # Non Anthos (GKE standard)
CONTEXT="gke_icarocloud-prod_europe-west8_cluster-icaro-prod"
NAMESPACE="icaro"
RESOURCE="Deployment"            # Solo Deployment

# Parametri Strategia
CPU_PERCENTILE="90"              # 90° percentile (più aggressivo del default 95°)
TIMEFRAME_DURATION="2.0"         # Step 2 minuti
HISTORY_DURATION="230"           # ~9.6 giorni di storia
FORMATTER="csv"                  # Output CSV

# Docker
KRR_DOCKER_IMAGE="europe-west12-docker.pkg.dev/formazione-ion-boleac/tools/holo-krr:latest"

# AI (disabilitato)
AI_MODE="false"
AI_MODEL="gemini-3-flash-preview"

# HPA
HPA_MODE="true"                  # Analizza anche workload con HPA
```

---

## 15. Riepilogo Capacità

### Matrice Funzionalità Completa

| Capacità | Dettaglio | Status |
|---|---|---|
| **Analisi risorse** | CPU requests/limits, Memory requests/limits per container | ✅ |
| **Fonti dati** | 10+ backend Prometheus-compatibili | ✅ |
| **Workload K8s** | 9 tipi (Deployment, StatefulSet, DaemonSet, Job, CronJob, Rollout, DeploymentConfig, StrimziPodSet, GroupedJob) | ✅ |
| **Strategie** | 3 built-in (simple, simple_limit, ai-assisted) + custom | ✅ |
| **Provider AI** | 4 (OpenAI, Gemini, Anthropic, Ollama) | ✅ |
| **Formati output** | 7 (table, csv, csv-raw, json, yaml, html, pprint) | ✅ |
| **Canali distribuzione** | 5 (console, file, Slack, Azure Blob, Teams) | ✅ |
| **Multi-cluster** | Sì, con supporto centralized Prometheus | ✅ |
| **HPA-aware** | Sì, con flag `--allow-hpa` | ✅ |
| **OOMKill-aware** | Sì, con flag `--use-oomkill-data` | ✅ |
| **Auto-apply** | Sì, tramite Enforcer webhook + Supabase | ✅ |
| **GCP Native** | GKE + Managed Prometheus + Anthos | ✅ |
| **Containerizzato** | Docker con gcloud SDK integrato | ✅ |
| **Estensibile** | Strategie e formatter custom via plugin Python | ✅ |
| **Namespace regex** | Supporto regex per filtro namespace | ✅ |
| **Label selector** | Filtro workload per label | ✅ |
| **Batch discovery** | Paginazione API per cluster grandi | ✅ |
| **Retry logic** | Tenacity con backoff esponenziale | ✅ |
| **Custom CA certs** | Supporto certificati custom via env var | ✅ |

### Comandi Principali

```bash
# Scansione base
krr simple

# Scansione namespace specifico con Prometheus esplicito
krr simple -n icaro -p http://prometheus:9090

# Scansione con output CSV su file
krr simple -f csv --fileoutput-dynamic

# Scansione con strategia AI
krr ai-assisted --ai-provider gemini --ai-model gemini-2.0-flash-exp

# Scansione con CPU limit
krr simple_limit --cpu-request 66 --cpu-limit 96

# Scansione multi-cluster
krr simple --all-clusters

# Scansione con job grouping
krr simple --job-grouping-labels app,team --job-grouping-limit 100

# Scansione GCP Managed Prometheus
krr simple -p "https://monitoring.googleapis.com/v1/projects/PROJECT/location/global/prometheus" \
    --prometheus-auth-header "Bearer TOKEN" \
    --prometheus-cluster-label "cluster-name" \
    --prometheus-label "cluster_name"

# Scansione con output Azure + Teams
krr simple -f html \
    --azurebloboutput "https://storage.blob.core.windows.net/container?sv=..." \
    --teams-webhook "https://outlook.office.com/webhook/..."
```

---

> **Conclusione**: KRR è un tool **maturo, estensibile e potente** per il right-sizing delle risorse Kubernetes. Questo fork aggiunge supporto nativo per GCP (Managed Prometheus + Anthos), analisi AI-assisted con 4 provider LLM, raggruppamento custom di Job, integrazione Azure/Teams, e un sistema di auto-apply tramite webhook. L'analisi del cluster `icaro-prod` mostra un potenziale di risparmio CPU dell'80% e identifica deployment criticamente sotto-dimensionati in memoria.
