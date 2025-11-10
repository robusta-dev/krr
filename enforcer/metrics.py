from prometheus_client import Counter, Histogram, Gauge

# Prometheus metrics
pod_admission_mutations = Counter(
    'krr_pod_admission_mutations_total',
    'Total pod admission mutations',
    ['mutated', 'reason']  # labels: 'true' or 'false', reason for success/failure
)

replicaset_admissions = Counter(
    'krr_replicaset_admissions_total', 
    'Total replicaset admissions',
    ['operation']  # labels: CREATE, DELETE, etc.
)

rs_owners_size = Gauge(
    'krr_rs_owners_map_size',
    'Current size of the rs_owners map'
)

admission_duration = Histogram(
    'krr_admission_duration_seconds',
    'Duration of admission operations',
    ['kind']  # labels: Pod, ReplicaSet
)