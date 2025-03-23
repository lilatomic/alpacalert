# Alpacalert CMD

The Alpacalert CLI provides tools to have Alpacalert look at your system and tell you what's wrong. The included tools are:

- Grafana: Turn your Grafana alerts into a hierarchy and see which systems are down and for what reasons.
- Kubernetes: Scan a Kubernetes cluster for objects in a failed state
- Prometheus: Like the Kubernetes tool, but includes several Prometheus queries too.

Alpacalert CMD is also an example of how to use the alpacalert library to create applications.

## Installation

Use pipx to install alpacalert-cmd in its own venv

`pipx install alpacalert-cmd`
