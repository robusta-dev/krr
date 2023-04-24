<a name="readme-top"></a>

<!-- [![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url] -->

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/robusta-dev/krr">
    <img src="images/logo.png" alt="Logo" width="320" height="320">
  </a>
  <h3 align="center">Robusta KRR</h3>
  <p align="center">
    Prometheus-based Kubernetes Resource Recommendations
    <br />
    <a href="#getting-started"><strong>Usage docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/robusta-dev/krr/issues">Report Bug</a>
    ·
    <a href="https://github.com/robusta-dev/krr/issues">Request Feature</a>
    ·
    <a href="https://robustacommunity.slack.com/archives/C054QUA4NHE">Slack Channel</a>
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

![Product Name Screen Shot][product-screenshot]

Robusta KRR (Kubernetes Resource Recommender) is a CLI tool for optimizing resource allocation in Kubernetes clusters. It gathers pod usage data from Prometheus and recommends requests and limits for CPU and memory. This reduces costs and improves performance.

### Features

-   No Agent Required: Robusta KRR is a CLI tool that runs on your local machine. It does not require running Pods in your cluster.
-   Prometheus Integration: Gather resource usage data using built-in Prometheus queries, with support for custom queries coming soon.
-   Extensible Strategies: Easily create and use your own strategies for calculating resource recommendations.
-   Future Support: Upcoming versions will support custom resources (e.g. GPUs) and custom metrics.

### Resource Allocation Statistics

According to a recent [Sysdig study](https://sysdig.com/blog/millions-wasted-kubernetes/), on average, Kubernetes clusters have:

-   69% unused CPU
-   18% unused memory

By right-sizing your containers with KRR, you can save an average of 69% on cloud costs.

### How it works

#### Metrics Gathering

Robusta KRR uses the following Prometheus queries to gather usage data:

-   CPU Usage:

    ```
    sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{namespace="{object.namespace}", pod="{pod}", container="{object.container}"})
    ```

-   Memory Usage:

    ```
    sum(container_memory_working_set_bytes{job="kubelet", metrics_path="/metrics/cadvisor", image!="", namespace="{object.namespace}", pod="{pod}", container="{object.container}"})
    ```

[_Need to customize the metrics? Tell us and we'll add support._](https://github.com/robusta-dev/krr/issues/new)

#### Algorithm

By default, we use a _simple_ strategy to calculate resource recommendations. It is calculated as follows (_The exact numbers can be customized in CLI arguments_):

-   For CPU, we set a request at the 99th percentile with no limit. Meaning, in 99% of the cases, your CPU request will be sufficient. For the remaining 1%, we set no limit. This means your pod can burst and use any CPU available on the node - e.g. CPU that other pods requested but aren’t using right now.

-   For memory, we take the maximum value over the past week and add a 5% buffer.

### Difference with Kubernetes VPA

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

### Robusta UI integration

If you are using [Robusta SaaS](https://platform.robusta.dev/), then KRR is integrated starting from [v0.10.15](https://github.com/robusta-dev/robusta/releases/tag/0.10.15). You can view all your recommendations (previous ones also), filter and sort them by either cluster, namespace or name.

More features (like seeing graphs, based on which recommendations were made) coming soon. [Tell us what you need the most!](https://github.com/robusta-dev/krr/issues/new)

![Robusta UI Screen Shot][ui-screenshot]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

### Installation

<!-- _Depending on your operating system, select the appropriate installation method._

#### Linux

```sh
sudo apt install robusta-krr
````

#### MacOS

```sh
brew install robusta-krr
```

#### Windows

```sh
choco install robusta-krr
```

#### Debian

```sh
sudo apt install robusta-krr
```

#### Docker

`````sh
docker pull robusta/krr
````

#### Manual

-->

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->

## Usage

Straightforward usage, to run the simple strategy:

```sh
python krr.py simple
```

If you want only specific namespaces (default and ingress-nginx):

```sh
python krr.py simple -n default -n ingress-nginx
```

By default krr will run in the current context. If you want to run it in a different context:

```sh
python krr.py simple -c my-cluster-1 -c my-cluster-2
```

If you want to get the output in JSON format (--logtostderr is required so no logs go to the result file):

```sh
python krr.py simple --logtostderr -f json > result.json
```

If you want to get the output in YAML format:

```sh
python krr.py simple --logtostderr -f yaml > result.yaml
```

If you want to see additional debug logs:

```sh
python krr.py simple -v
```

More specific information on Strategy Settings can be found using

```sh
python krr.py simple --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- Port-forwarding -->

## Example of using port-forward for Prometheus

If your prometheus is not auto-connecting, you can use `kubectl port-forward` for manually forwarding Prometheus.

For example, if you have a Prometheus Pod called `kube-prometheus-st-prometheus-0`, then run this command to port-forward it:

```sh
kubectl port-forward pod/kube-prometheus-st-prometheus-0 9090
```

Then, open another terminal and run krr in it, giving an explicit prometheus url:

```sh
python krr.py simple -p http://127.0.0.1:9090
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CUSTOM -->

## Creating a Custom Strategy/Formatter

Look into the `examples` directory for examples on how to create a custom strategy/formatter.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- BUILDING -->

## Building

_We are planning to use pyinstaller to build binaries for distribution. Right now you can build the binaries yourself, but we're not distributing them yet._

1. Install the project manually (see above)
2. Navigate to the project root directory
3. Install poetry (https://python-poetry.org/docs/#installing-with-the-official-installer)
4. Install requirements with dev dependencies:

```sh
poetry install --group dev
```

5. Build the binary:

```sh
poetry run pyinstaller krr.py
```

6. The binary will be located in the `dist` directory. Test that it works:

```sh
cd ./dist/krr
./krr --help
```

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

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->

## Contact

If you have any questions, feel free to contact support@robusta.dev

Project Link: [https://github.com/robusta-dev/krr](https://github.com/robusta-dev/krr)

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
[ui-screenshot]: images/ui_screenshot.jpeg
