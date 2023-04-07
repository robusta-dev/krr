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
  <a href="https://github.com/robusta/robusta-krr">
    <img src="images/logo.png" alt="Logo" width="320" height="320">
  </a>
  <h3 align="center">Robusta's KRR</h3>
  <p align="center">
    Prometheus-based Kubernetes Resource Recommendations
    <br />
    <a href="#getting-started"><strong>Usage docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/robusta/robusta-krr/issues">Report Bug</a>
    ·
    <a href="https://github.com/robusta/robusta-krr/issues">Request Feature</a>
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

Robusta KRR (Kubernetes Resource Recommender) is an extensible CLI tool designed to help optimize resource allocation in Kubernetes clusters. It gathers pod usage data from Prometheus, and applies customizable strategies to calculate CPU and memory requests and limits recommendations. This helps you get the most out of your cluster resources and improve overall efficiency.

### Features

-   Extensible Strategies: Easily create and use your own strategies for calculating resource recommendations.
-   Custom Formatters: Write custom formatters to present the results in your preferred format.
-   Prometheus Integration: Gather resource usage data using built-in Prometheus queries, with support for custom queries coming soon.
-   Future Support: Upcoming versions will support custom resources (e.g. GPUs) and custom metrics.

### Resource Allocation Statistics

On average, Kubernetes clusters have:

-   69% unused CPU
-   18% unused memory
-   59% of containers with no CPU limits
-   49% of containers with no memory limits
    By utilizing Robusta KRR's recommendations, you can significantly reduce these inefficiencies.

### Metrics Gathering

Robusta KRR uses the following Prometheus queries to gather usage data:

-   CPU Usage:

    ```
    sum(node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate{namespace="{object.namespace}", pod="{pod}", container="{object.container}"})
    ```

-   Memory Usage:

    ```
    sum(container_memory_working_set_bytes{job="kubelet", metrics_path="/metrics/cadvisor", image!="", namespace="{object.namespace}", pod="{pod}", container="{object.container}"})
    ```

_These queries can be customized to suit your specific needs in the future versions, allowing for even more accurate recommendations._

By using Robusta KRR, you can optimize your Kubernetes cluster resource allocation, ensuring better performance and efficiency. Get started with Robusta KRR today, and unlock the full potential of your cluster.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

### Installation

_Depending on your operating system, select the appropriate installation method._

<!-- #### Linux

```sh
sudo apt install robusta-krr
```

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

```sh
docker pull robusta/krr
```` -->

#### Manual

1. Make sure you have [Python 3.11](https://www.python.org/downloads/) installed
2. Clone the repo:

```sh
git clone https://github.com/robusta-dev/robusta-krr
```

3. Navigate to the project root directory (`cd ./robusta-krr`)
4. Install poetry (the package manager):

```sh
pip install poetry
```

5. Install the dependencies:

```sh
poetry install
```

6. Run the tool:

```sh
poetry run krr --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->

## Usage

Straightforward usage, to run the simple strategy:

```sh
poetry run krr simple
```

If you want only specific namespaces (default and ingress-nginx):

```sh
poetry run krr simple -n default -n ingress-nginx
```

By default krr will run in the current context. If you want to run it in a different context:

```sh
poetry run krr simple -c my-cluster-1 -c my-cluster-2
```

If you want to get the output in JSON format (-q is for quiet mode):

```sh
poetry run krr simple -q -f json > result.json
```

If you want to get the output in YAML format:

```sh
poetry run krr simple -q -f yaml > result.yaml
```

If you want to see additional debug logs:

```sh
poetry run krr simple -v
```

More specific information on Strategy Settings can be found using

```sh
poetry run krr simple --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- BUILDING -->

## Building

_We are using pyinstaller to build the binary._

1. Install the project manually (see above)
2. Navigate to the project root directory
3. Install dev dependencies:

```sh
poetry install --group dev
```

4. Build the binary:

```sh
poetry run pyinstaller krr.py
```

5. The binary will be located in the `dist` directory. Test that it works:

```sh
cd ./dist/krr
./krr --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- TESTING -->

## Testing

_We are using pytest to run the tests._

1. Install the project manually (see above)
2. Navigate to the project root directory
3. Install dev dependencies:

```sh
poetry install --group dev
```

4. Install robusta_krr as editable dependency:

```sh
pip install -e .
```

5. Run the tests:

```sh
poetry run pytest
```

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

Project Link: [https://github.com/robusta-dev/robusta-krr](https://github.com/robusta-dev/robusta-krr)

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
