# KRR - Kubernetes Resource Recommender

KRR (Kubernetes Resource Recommender) è un potente strumento a riga di comando (CLI) per ottimizzare l'allocazione delle risorse (CPU e Memoria) all'interno dei tuoi cluster Kubernetes.

Analizza i dati storici di utilizzo dal tuo sistema di monitoraggio e raccomanda valori di `requests` e `limits` più efficienti, aiutandoti a **ridurre i costi** e **aumentare la stabilità** dei tuoi carichi di lavoro.

## Caratteristiche Principali

- **Analisi Basata su Dati Storici**: Fornisce raccomandazioni basate sull'uso reale delle risorse.
- **Molteplici Strategie**: Scegli tra diversi algoritmi di calcolo, inclusa una strategia assistita da AI.
- **Supporto Multi-Piattaforma**: Compatibile con numerosi servizi di monitoraggio basati su Prometheus.
- **Output Flessibile**: Esporta i risultati in formati multipli per analisi o integrazioni.
- **Automazione (Enforcer)**: Può applicare automaticamente le raccomandazioni al tuo cluster.

---

## Setup e Installazione

Per eseguire KRR, è necessario avere un ambiente Python configurato. Si consiglia di utilizzare un ambiente virtuale per gestire le dipendenze in modo isolato.

**1. Creare un Ambiente Virtuale**

Esegui questo comando nella root del progetto per creare una cartella `venv` con l'ambiente virtuale:
```bash
python3 -m venv venv
```

**2. Attivare l'Ambiente Virtuale**

Per attivare l'ambiente, esegui:
```bash
source venv/bin/activate
```
Una volta attivato, il tuo prompt della shell mostrerà `(venv)`.

**3. Installare le Dipendenze**

Con l'ambiente attivo, installa tutte le librerie Python necessarie con un singolo comando:
```bash
pip install -r requirements.txt
```

Ora sei pronto per usare lo strumento!

---

## Come Usarlo

Il comando base per eseguire KRR è `python krr.py`. Dovrai specificare una strategia e le opzioni necessarie per connetterti al tuo data source.

**Sintassi di base:**
```bash
python krr.py <strategia> [opzioni]
```

**Esempio (strategia `simple`):**
```bash
python krr.py simple --namespace my-namespace
```

### Sorgenti Dati Supportate

KRR è progettato per funzionare con qualsiasi endpoint compatibile con le API di Prometheus. Ha un supporto specializzato per:

-   **Prometheus** (standard)
-   **Google Cloud Managed Service for Prometheus**
-   **Thanos**
-   **VictoriaMetrics**
-   **Mimir**

### Formati di Output

Puoi formattare l'output delle raccomandazioni in diversi modi, usando il flag `-f` o `--format`:

-   `table` (default): Una tabella leggibile da console.
-   `json`: Utile per integrazioni programmatiche.
-   `yaml`: Facilmente leggibile e parsabile.
-   `csv`: Per importare i dati in fogli di calcolo.
-   `html`: Per generare report web.

**Esempio:**
```bash
python krr.py simple -f json > recommendations.json
```

---

## 🚀 Guida Pratica e Proof of Concept per Google Cloud (GKE e Anthos)

Questa guida ti mostrerà come eseguire KRR da zero per analizzare un cluster GKE o Anthos, utilizzando lo script di avvio rapido `test_gcp_quick.sh`. Questo script è il modo più semplice per iniziare, in quanto automatizza l'autenticazione e la configurazione.

### Prerequisiti

1.  **Google Cloud SDK (`gcloud`)**: Installato e configurato sul tuo sistema.
2.  **Autenticazione**: Devi essere autenticato con un account che abbia accesso al progetto e al cluster da analizzare. Esegui `gcloud auth login`.
3.  **Ambiente KRR**: Assicurati di aver seguito i passaggi nella sezione `Setup e Installazione` (creazione del `venv` e installazione delle dipendenze).

### Step 1: Configura il tuo Ambiente

Lo script `test_gcp_quick.sh` utilizza un file `.env` per caricare le configurazioni necessarie.

Crea un file chiamato `.env` nella directory principale del progetto e inserisci i dettagli del tuo cluster:

```ini
# File: .env
# Dettagli del tuo cluster GCP
PROJECT_ID=il-tuo-project-id-gcp
CLUSTER_NAME=il-tuo-cluster-gke-name

# (Opzionale) Namespace di default da analizzare se non specificato da riga di comando
NAMESPACE=default

# (Opzionale) Abilita l'analisi anche per workload con HPA
# Imposta a "true" per passare il flag --allow-hpa a KRR
HPA_MODE=false

# (Opzionale) Abilita la strategia AI-Assisted con Gemini
# Imposta a "true" per usare "krr.py ai-assisted"
AI_MODE=false
```

### Step 2: Rendi lo Script Eseguibile

Per sicurezza, il file potrebbe non avere i permessi di esecuzione. Assegnali con:

```bash
chmod +x test_gcp_quick.sh
```

### Step 3: Esegui l'Analisi

Ora puoi lanciare lo script. Puoi specificare un namespace, altrimenti userà quello definito nel file `.env` o `default`.

```bash
./test_gcp_quick.sh my-production-namespace
```

Lo script stamperà le raccomandazioni in una tabella direttamente sul terminale.

### Cosa Fa lo Script? (Analisi dei Parametri)

Lo script `test_gcp_quick.sh` è un wrapper che costruisce ed esegue il comando `python krr.py` con i parametri corretti per un ambiente GCP. Vediamo i più importanti:

#### **--prometheus-url**
Per connettersi al servizio gestito di Prometheus su GCP, KRR ha bisogno dell'URL corretto. Lo script lo costruisce dinamicamente per te in questo formato:
```
https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/${LOCATION}/prometheus
```
Questo è il parametro fondamentale per dire a KRR dove trovare le metriche.

#### **--prometheus-auth-header**
L'accesso all'API di monitoring di GCP richiede un token di autenticazione. Lo script lo ottiene eseguendo `gcloud auth print-access-token` e lo passa a KRR tramite questo flag, gestendo l'autenticazione in modo trasparente.

#### **--allow-hpa**
Di default, KRR salta i workload che hanno un HorizontalPodAutoscaler (HPA) associato, per evitare conflitti.
-   **Come abilitarlo**: Impostando `HPA_MODE=true` nel tuo file `.env`.
-   **Cosa fa**: Lo script aggiungerà il flag `--allow-hpa` al comando, forzando KRR a calcolare le raccomandazioni anche per questi workload. È utile per avere una visione completa, ma le raccomandazioni vanno valutate con attenzione in contesti di autoscaling.

#### **--gcp-anthos**
Questo flag istruisce KRR a usare le metriche specifiche di Anthos (`kubernetes.io/anthos/*`) per cluster on-premise gestiti da Google.
-   **Come abilitarlo**: Puoi passare `anthos` come terzo parametro allo script:
    ```bash
    # ./test_gcp_quick.sh <namespace> <context> <anthos_mode>
    ./test_gcp_quick.sh my-onprem-ns my-anthos-context anthos
    ```
-   **Cosa fa**: Lo script aggiungerà il flag `--gcp-anthos` al comando `krr.py`.

### Esempio di Output

Dopo aver eseguito lo script, vedrai un output simile a questo:

```
 Namespace        | Workload                | Container | Old Requests | New Requests | Old Limits | New Limits
------------------|-------------------------|-----------|--------------|--------------|------------|-----------
 my-prod-ns       | my-app-deployment       | my-app    | cpu: 500m    | cpu: 128m    | cpu: 1000m | cpu: 256m
                  |                         |           | memory: 1Gi  | memory: 256Mi| memory: 2Gi| memory: 512Mi
...
```

Con questa guida, sei in grado di lanciare KRR in modo rapido e corretto sul tuo ambiente GCP, sfruttando lo script `test_gcp_quick.sh` per semplificare l'intero processo.

---

## Applicazione Automatica (Enforcer)

KRR non è solo uno strumento di analisi. Include un componente chiamato **Enforcer** che può **applicare automaticamente le raccomandazioni** direttamente sui workload nel tuo cluster Kubernetes.

-   **Come funziona**: L'Enforcer viene distribuito nel cluster (tipicamente tramite il suo Helm Chart che trovi in `helm/krr-enforcer`).
-   **Cosa fa**: Legge le raccomandazioni generate da KRR e "patcha" le risorse (es. Deployments, StatefulSets) per aggiornare i valori di `requests` e `limits`.

⚠️ **Attenzione**: Questa è una funzionalità potente che modifica attivamente il tuo cluster. Si consiglia di testarla prima in un ambiente di staging o di sviluppo e di usarla con cautela.
