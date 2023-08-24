<!-- @format -->

<a name="readme-top"></a>

<!-- [![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url] -->

![Product Name Screen Shot][product-screenshot]

<div align="center">
  <h1 align="center">Robusta KRR</h1>
  <p align="center">
    Prometheus-based Kubernetes Resource Recommendations
    <br />
    <a href="#installation"><strong>Installation</strong></a>
    .
    <a href="#usage"><strong>Usage</strong></a>
    ·
    <a href="#how-it-works"><strong>How it works</strong></a>
    .
    <a href="#slack-integration"><strong>Slack Integration</strong></a>
    <br />
    <a href="https://github.com/robusta-dev/krr/issues">Report Bug</a>
    ·
    <a href="https://github.com/robusta-dev/krr/issues">Request Feature</a>
    ·
    <a href="#support">Support</a>
  </p>
</div>
<!-- TABLE OF CONTENTS -->
<!-- <details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details> -->
<!-- ABOUT THE PROJECT -->

## About The Project

Robusta KRR (Kubernetes Resource Recommender) is a CLI tool for optimizing resource allocation in Kubernetes clusters. It gathers pod usage data from Prometheus and recommends requests and limits for CPU and memory. This reduces costs and improves performance.

_Supports: [Prometheus](#prometheus-victoria-metrics-and-thanos-auto-discovery), [Thanos](#prometheus-victoria-metrics-and-thanos-auto-discovery), [Victoria Metrics](#prometheus-victoria-metrics-and-thanos-auto-discovery), [EKS](#eks-managed-prometheus), [Azure](#azure-managed-prometheus) and [Coralogix](#coralogix-managed-prometheus)_

### Features

- **No Agent Required**: Robusta KRR is a CLI tool that runs on your local machine. It does not require running Pods in your cluster. (But it can optionally be run in-cluster for weekly [Slack reports](#slack-integration).)
- **Prometheus Integration**: Gather resource usage data using built-in Prometheus queries, with support for custom queries coming soon.
- **Extensible Strategies**: Easily create and use your own strategies for calculating resource recommendations.
- **Future Support**: Upcoming versions will support custom resources (e.g. GPUs) and custom metrics.

### Resource Allocation Statistics

According to a recent [Sysdig study](https://sysdig.com/blog/millions-wasted-kubernetes/), on average, Kubernetes clusters have:

- 69% unused CPU
- 18% unused memory

By right-sizing your containers with KRR, you can save an average of 69% on cloud costs.

Read more about [how KRR works](#how-it-works) and [KRR vs Kubernetes VPA](#difference-with-kubernetes-vpa)

<!-- GETTING STARTED -->

## Installation

### With brew (MacOS/Linux):

1. Add our tap:

```sh
brew tap robusta-dev/homebrew-krr
```

2. Install KRR:

```sh
brew install krr
```

3. Check that installation was successfull (First launch might take a little longer):

```sh
krr --help
```

### On Windows:

You can install using brew (see above) on [WSL2](https://docs.brew.sh/Homebrew-on-Linux), or install manually.

### Manual Installation

1. Make sure you have [Python 3.9](https://www.python.org/downloads/) (or greater) installed
2. Clone the repo:

```sh
git clone https://github.com/robusta-dev/krr
```

3. Navigate to the project root directory (`cd ./krr`)
4. Install requirements:

```sh
pip install -r requirements.txt
```

5. Run the tool:

```sh
python krr.py --help
```

Notice that using source code requires you to run as a python script, when installing with brew allows to run `krr`.
All above examples show running command as `krr ...`, replace it with `python krr.py ...` if you are using a manual installation.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Other Configuration Methods

- [View KRR Reports in a Web UI](#robusta-ui-integration)
- [Get a Weekly Message in Slack with KRR Recommendations](#slack-integration)
- Setup KRR on [Google Cloud Managed Prometheus
  ](./docs/google-cloud-managed-service-for-prometheus.md)
- Setup KRR for [Azure managed Prometheus](#azure-managed-prometheus)

<!-- USAGE EXAMPLES -->

## Usage

Straightforward usage, to run the simple strategy:

```sh
krr simple
```

If you want only specific namespaces (default and ingress-nginx):

```sh
krr simple -n default -n ingress-nginx
```

Filtering by labels (more info [here](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#api)):

```sh
python krr.py simple --selector 'app.kubernetes.io/instance in (robusta, ingress-nginx)'
```

By default krr will run in the current context. If you want to run it in a different context:

```sh
krr simple -c my-cluster-1 -c my-cluster-2
```

If you want to get the output in JSON format (--logtostderr is required so no logs go to the result file):

```sh
krr simple --logtostderr -f json > result.json
```

If you want to get the output in YAML format:

```sh
krr simple --logtostderr -f yaml > result.yaml
```

If you want to see additional debug logs:

```sh
krr simple -v
```

Other helpful flags:
* `--cpu-min` Sets the minimum recommended cpu value in millicores
* `--mem-min` Sets the minimum recommended memory value in MB
* `--history_duration` The duration of the prometheus history data to use (in hours)

More specific information on Strategy Settings can be found using

```sh
krr simple --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## How it works

### Metrics Gathering

Robusta KRR uses the following Prometheus queries to gather usage data:

- CPU Usage:

  ```
  sum(irate(container_cpu_usage_seconds_total{{namespace="{object.namespace}", pod="{pod}", container="{object.container}"}}[{step}]))
  ```

- Memory Usage:

  ```
  sum(container_memory_working_set_bytes{job="kubelet", metrics_path="/metrics/cadvisor", image!="", namespace="{object.namespace}", pod="{pod}", container="{object.container}"})
  ```

[_Need to customize the metrics? Tell us and we'll add support._](https://github.com/robusta-dev/krr/issues/new)

### Algorithm

By default, we use a _simple_ strategy to calculate resource recommendations. It is calculated as follows (_The exact numbers can be customized in CLI arguments_):

- For CPU, we set a request at the 99th percentile with no limit. Meaning, in 99% of the cases, your CPU request will be sufficient. For the remaining 1%, we set no limit. This means your pod can burst and use any CPU available on the node - e.g. CPU that other pods requested but aren’t using right now.

- For memory, we take the maximum value over the past week and add a 5% buffer.

### Prometheus connection

Find about how KRR tries to find the default prometheus to connect <a href="#prometheus-victoria-metrics-and-thanos-auto-discovery">here</a>.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Difference with Kubernetes VPA

| Feature 🛠️                  | Robusta KRR 🚀                                                                                             | Kubernetes VPA 🌐                                           |
| --------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Resource Recommendations 💡 | ✅ CPU/Memory requests and limits                                                                          | ✅ CPU/Memory requests and limits                           |
| Installation Location 🌍    | ✅ Not required to be installed inside the cluster, can be used on your own device, connected to a cluster | ❌ Must be installed inside the cluster                     |
| Workload Configuration 🔧   | ✅ No need to configure a VPA object for each workload                                                     | ❌ Requires VPA object configuration for each workload      |
| Immediate Results ⚡        | ✅ Gets results immediately (given Prometheus is running)                                                  | ❌ Requires time to gather data and provide recommendations |
| Reporting 📊                | ✅ Detailed CLI Report, web UI in [Robusta.dev](https://home.robusta.dev/)                                 | ❌ Not supported                                            |
| Extensibility 🔧            | ✅ Add your own strategies with few lines of Python                                                        | :warning: Limited extensibility                             |
| Custom Metrics 📏           | 🔄 Support in future versions                                                                              | ❌ Not supported                                            |
| Custom Resources 🎛️         | 🔄 Support in future versions (e.g., GPU)                                                                  | ❌ Not supported                                            |
| Explainability 📖           | 🔄 Support in future versions (Robusta will send you additional graphs)                                    | ❌ Not supported                                            |
| Autoscaling 🔀              | 🔄 Support in future versions                                                                              | ✅ Automatic application of recommendations                 |

## Robusta UI integration

If you are using [Robusta SaaS](https://platform.robusta.dev/), then KRR is integrated starting from [v0.10.15](https://github.com/robusta-dev/robusta/releases/tag/0.10.15). You can view all your recommendations (previous ones also), filter and sort them by either cluster, namespace or name.

More features (like seeing graphs, based on which recommendations were made) coming soon. [Tell us what you need the most!](https://github.com/robusta-dev/krr/issues/new)

![Robusta UI Screen Shot][ui-screenshot]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ADVANCED USAGE EXAMPLES -->

## Slack integration

Put cost savings on autopilot. Get notified in Slack about recommendations above X%. Send a weekly global report, or one report per team.

![Slack Screen Shot][slack-screenshot]

### Prerequisites

- A Slack workspace

### Setup

1. [Install Robusta with Helm to your cluster and configure slack](https://docs.robusta.dev/master/installation.html)
2. Create your KRR slack playbook by adding the following to `generated_values.yaml`:

```
customPlaybooks:
# Runs a weekly krr scan on the namespace devs-namespace and sends it to the configured slack channel
customPlaybooks:
- triggers:
  - on_schedule:
      fixed_delay_repeat:
        repeat: -1 # number of times to run or -1 to run forever
        seconds_delay: 604800 # 1 week
  actions:
  - krr_scan:
      args: "--namespace devs-namespace" ## KRR args here
  sinks:
      - "main_slack_sink" # slack sink you want to send the report to here
```

3. Do a Helm upgrade to apply the new values: `helm upgrade robusta robusta/robusta --values=generated_values.yaml --set clusterName=<YOUR_CLUSTER_NAME>`

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- Port-forwarding -->

## Prometheus, Victoria Metrics and Thanos auto-discovery

By default, KRR will try to auto-discover the running Prometheus Victoria Metrics and Thanos.
For discovering prometheus it scan services for those labels:

```python
"app=kube-prometheus-stack-prometheus"
"app=prometheus,component=server"
"app=prometheus-server"
"app=prometheus-operator-prometheus"
"app=prometheus-msteams"
"app=rancher-monitoring-prometheus"
"app=prometheus-prometheus"
```

For Thanos its these labels:

```python
"app.kubernetes.io/component=query,app.kubernetes.io/name=thanos",
"app.kubernetes.io/name=thanos-query",
"app=thanos-query",
"app=thanos-querier",
```

And for Victoria Metrics its the following labels:

```python
"app.kubernetes.io/name=vmsingle",
"app.kubernetes.io/name=victoria-metrics-single",
"app.kubernetes.io/name=vmselect",
"app=vmselect",
```

If none of those labels result in finding Prometheus, Victoria Metrics or Thanos, you will get an error and will have to pass the working url explicitly (using the `-p` flag).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Example of using port-forward for Prometheus

If your prometheus is not auto-connecting, you can use `kubectl port-forward` for manually forwarding Prometheus.

For example, if you have a Prometheus Pod called `kube-prometheus-st-prometheus-0`, then run this command to port-forward it:

```sh
kubectl port-forward pod/kube-prometheus-st-prometheus-0 9090
```

Then, open another terminal and run krr in it, giving an explicit prometheus url:

```sh
krr simple -p http://127.0.0.1:9090
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Scanning with a centralized Prometheus

If your Prometheus monitors multiple clusters we require the label you defined for your cluster in Prometheus.

For example, if your cluster has the Prometheus label `cluster: "my-cluster-name"` and your prometheus is at url `http://my-centralized-prometheus:9090`, then run this command:

```sh
krr.py simple -p http://my-centralized-prometheus:9090 --prometheus-label cluster -l my-cluster-name
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Azure managed Prometheus

For Azure managed Prometheus you need to generate an access token, which can be done by running the following command:

```sh
# If you are not logged in to Azure, uncomment out the following line
# az login
AZURE_BEARER=$(az account get-access-token --resource=https://prometheus.monitor.azure.com  --query accessToken --output tsv); echo $AZURE_BEARER
```

Than run the following command with PROMETHEUS_URL substituted for your Azure Managed Prometheus URL:

```sh
python krr.py simple --namespace default -p PROMETHEUS_URL --prometheus-auth-header "Bearer $AZURE_BEARER"
```

<p ><a href="#scanning-with-a-centralized-prometheus">See here about configuring labels for centralized prometheus</a></p>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## EKS managed Prometheus

For EKS managed Prometheus you need to add your prometheus link and the flag --eks-managed-prom and krr will automatically use your aws credentials

```sh
python krr.py simple -p "https://aps-workspaces.REGION.amazonaws.com/workspaces/..." --eks-managed-prom
```

Additional optional parameters are:

```sh
--eks-profile-name PROFILE_NAME_HERE # to specify the profile to use from your config
--eks-access-key ACCESS_KEY # to specify your access key
--eks-secret-key SECRET_KEY # to specify your secret key
--eks-service-name SERVICE_NAME # to use a specific service name in the signature
--eks-managed-prom-region REGION_NAME # to specify the region the prometheus is in
```

<p ><a href="#scanning-with-a-centralized-prometheus">See here about configuring labels for centralized prometheus</a></p>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Coralogix managed Prometheus

For Coralogix managed Prometheus you need to specify your prometheus link and add the flag coralogix_token with your Logs Query Key

```sh
python krr.py simple -p "https://prom-api.coralogix..." --coralogix_token
```

<p ><a href="#scanning-with-a-centralized-prometheus">See here about configuring labels for centralized prometheus</a></p>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- Formatters -->

## Available formatters

Currently KRR ships with a few formatters to represent the scan data:

- `table` - a pretty CLI table used by default, powered by [Rich](https://github.com/Textualize/rich) library
- `json`
- `yaml`
- `pprint` - data representation from python's pprint library

To run a strategy with a selected formatter, add a `-f` flag:

```sh
krr simple -f json
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CUSTOM -->

## Creating a Custom Strategy/Formatter

Look into the [examples](https://github.com/robusta-dev/krr/tree/main/examples) directory for examples on how to create a custom strategy/formatter.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- TESTING -->

## Testing

_We use pytest to run tests._

1. Install the project manually (see above)
2. Navigate to the project root directory
3. Install poetry (https://python-poetry.org/docs/#installing-with-the-official-installer)
4. Install dev dependencies:

```sh
poetry install --group dev
```

5. Install robusta_krr as editable dependency:

```sh
pip install -e .
```

6. Run the tests:

```sh
poetry run pytest
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->

## License

Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/krr/blob/main/LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->

## Support

If you have any questions, feel free to contact **support@robusta.dev** or message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->

[contributors-shield]: https://img.shields.io/github/contributors/othneildrew/Best-README-Template.svg?style=for-the-badge
[contributors-url]: https://github.com/othneildrew/Best-README-Template/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/othneildrew/Best-README-Template.svg?style=for-the-badge
[forks-url]: https://github.com/othneildrew/Best-README-Template/network/members
[stars-shield]: https://img.shields.io/github/stars/othneildrew/Best-README-Template.svg?style=for-the-badge
[stars-url]: https://github.com/othneildrew/Best-README-Template/stargazers
[issues-shield]: https://img.shields.io/github/issues/othneildrew/Best-README-Template.svg?style=for-the-badge
[issues-url]: https://github.com/othneildrew/Best-README-Template/issues
[license-shield]: https://img.shields.io/github/license/othneildrew/Best-README-Template.svg?style=for-the-badge
[license-url]: https://github.com/othneildrew/Best-README-Template/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/othneildrew
[product-screenshot]: images/screenshot.jpeg
[slack-screenshot]: images/krr_slack_example.png
[ui-screenshot]: images/ui_screenshot.jpeg
