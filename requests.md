# Prometheus requests usage reference

## Pod data gathering
First we gather pods of the object. If this step fails, we will try to query that data from kube API, but that only returns current pods.

Deployment and Rollout owned replicasets:
```promql
kube_replicaset_owner{
    owner_name="TestDeployment",
    owner_kind="Deployment",
    namespace="default"
}[14d]
```

DeploymentConfig owned replicationcontrollers:
```promql
kube_replicationcontroller_owner{
    owner_name="TestDeploymentConfig",
    owner_kind="DeploymentConfig",
    namespace="default"
}[14d]
```

CronJob owned jobs:
```promql
kube_job_owner{
    owner_name="TestCronjob",
    owner_kind="CronJob",
    namespace="default"
}[14d]
```

Pods owned by ReplicaSet, ReplicationController, Job, StatefulSet, DaemonSet:
```promql
last_over_time(
    kube_pod_owner{
        owner_name=~"robusta-runner-bf8cb4db7|robusta-runner-5bc458c7b4|robusta-runner-5bc458c7b4",
        owner_kind="ReplicaSet",
        namespace="default"
    }[14d]
)
```

Check if pods are running:
```promql
kube_pod_status_phase{
    phase="Running",
    pod=~"robusta-runner-5bc458c7b4-pwpkl|robusta-runner-5bc458c7b4-cnd49",
    namespace="default"
} == 1
```

## CPU Usage

Percentile CPU usage per pod:
```promql
quantile_over_time(
    0.99,
    max(
        rate(
            container_cpu_usage_seconds_total{
                namespace="default",
                pod=~"robusta-runner-5bc458c7b4-pwpkl|robusta-runner-5bc458c7b4-cnd49",
                container="robusta"
            }[75s]
        )
    ) by (container, pod, job)
    [14d:75s]
)
```

CPU usage data count per pod:
```promql
count_over_time(
    max(
        container_cpu_usage_seconds_total{
            namespace="default",
            pod=~"robusta-runner-5bc458c7b4-pwpkl|robusta-runner-5bc458c7b4-cnd49",
            container="robusta"
        }
    ) by (container, pod, job)
    [14d:75s]
)
```


## Memory Usage

Max memory usage per pod:
```
max_over_time(
    max(
        container_memory_working_set_bytes{
            namespace="default",
            pod=~"robusta-runner-5bc458c7b4-pwpkl|robusta-runner-5bc458c7b4-cnd49",
            container="robusta"
        }
    ) by (container, pod, job)
    [14d:75s]
)
```

Memory usage data count per pod:
```promql
count_over_time(
    max(
        container_memory_working_set_bytes{
            namespace="default",
            pod=~"robusta-runner-5bc458c7b4-pwpkl|robusta-runner-5bc458c7b4-cnd49",
            container="robusta"
        }
    ) by (container, pod, job)
    [14d:75s]
)
```