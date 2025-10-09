# Vision Dataset Curation Helm Chart

This chart deploys Vision Dataset Curation application to a Kubernetes cluster.

> The implementation of the Helm chart is right now the bare minimum to get it to work.
> The purpouse of the chart is not to be infinitely configurable, but to provide a limited set of configuration options that make sense for the Teknoir platform.

# For Chip

## Build the VDC Docker image

```bash
./build.sh
```
Follow instructions...

## Deploy the VDC application

```bash
./deploy.sh
```

## Browse

https://teknoir.cloud/victra-poc/vision-dataset-curation


# Regular Helm usage

## Usage in Teknoir platform
Use the HelmChart to deploy the Vision Dataset Curation application to a Namespace.

```yaml
---
apiVersion: helm.cattle.io/v1
kind: HelmChart
metadata:
  name: vision-dataset-curation
  namespace: demonstrations # or any other namespace
spec:
  repo: https://teknoir.github.io/vision-dataset-curation-helm
  chart: vision-dataset-curation
  targetNamespace: demonstrations # or any other namespace
  valuesContent: |-
    # Example for minimal configuration
    
```

## Adding the repository

```bash
helm repo add teknoir-vision-dataset-curation https://teknoir.github.io/vision-dataset-curation-helm/
```

## Installing the chart

```bash
helm install teknoir-vision-dataset-curation teknoir-vision-dataset-curation/vision-dataset-curation -f values.yaml
```
