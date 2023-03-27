<a name="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/robusta/robusta-krr">
    <img src="images/logo.png" alt="Logo" width="320" height="320">
  </a>
  <h3 align="center">Robusta's KubeKraken</h3>
  <p align="center">
    Prometheus-based Kubernetes Resource Recommendations
    <br />
    <a href="https://github.com/robusta/robusta-krr"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/robusta/robusta-krr">View Demo</a>
    ·
    <a href="https://github.com/robusta/robusta-krr/issues">Report Bug</a>
    ·
    <a href="https://github.com/robusta/robusta-krr/issues">Request Feature</a>
  </p>
</div>
<!-- TABLE OF CONTENTS -->
<details>
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
</details>
<!-- ABOUT THE PROJECT -->

## About The Project

[![Product Name Screen Shot][product-screenshot]](https://example.com)

Robusta's Kubernetes Resource Recommender (KRR) is a tool that helps users to optimize the resource usage of their Kubernetes clusters. It is based on the Prometheus monitoring system and the Kubernetes API. It is designed to be used both as a CLI tool or as a Kubernetes operator. It is also designed to be easily integrated into Robusta UI, so if you are already using it you can easily start using KRR.

This tool is also designed to be easily extensible. It is possible to add additional calculation strategies yourself, if you want to use a different strategy than the ones provided by default.

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

1. Make sure you have [Python 3.11](https://www.python.org/downloads/) installed.
2.

```sh
git clone https://github.com/robusta-dev/robusta-krr
```

3. Install poetry (the package manager):

```sh
pip install poetry
```

4. Install the dependencies:

```sh
poetry install
```

5. Run the tool:

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
[product-screenshot]: images/screenshot.png
