import contextlib
import logging
from typing import Dict, Generator, List, Optional, TypedDict

import kubernetes


log = logging.getLogger(__name__)


class KubeSecretVolume(TypedDict):

    secret_name: str

    name: str


class KubeVolumeMount(TypedDict):

    mount_path: str

    name: str


class KubeJobConfig(TypedDict):
    """
    A subset of options to run a k8s Job:

    V1Job
    V1JobSpec
    V1PodTemplateSpec
    V1Container
    """

    # k8s config context name to use (to access other clusters)
    context_name: str

    # k8s namespace to create pods e.g. "default"
    namespace: str

    # k8s container and Job name should be unique per run
    name: str

    # number of retries before marking this job failed
    backoff_limit: int

    # container image to run
    image_name: str

    # container args to pass to the image entrypoint
    args: List[str]

    # env vars
    env: Dict[str, str]

    # service account name to run the job pod with
    service_account_name: str

    # container volume_mounts
    volume_mounts: List[KubeVolumeMount]

    # volumes with secret sources
    secrets: List[KubeSecretVolume]


def get_api_client(context_name: Optional[str] = None) -> kubernetes.client.ApiClient:
    """
    Returns the k8s ApiClient using the provided context name

    Defaults to the in cluster config when context_name is None.
    """
    if context_name is None:
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config(context=context_name)
    return kubernetes.client.ApiClient(configuration=kubernetes.client.Configuration())


def create_job(
    job_config: KubeJobConfig,
) -> kubernetes.client.V1Job:
    api_client = get_api_client(job_config["context_name"])
    # Configureate Pod template container
    container = kubernetes.client.V1Container(
        name=job_config["name"],
        image=job_config["image_name"],
        image_pull_policy="IfNotPresent",
        args=job_config["args"],
        env=[dict(name=k, value=v) for (k, v) in job_config["env"].items()],
        volume_mounts=[
            kubernetes.client.V1VolumeMount(
                mount_path=volume_mount["mount_path"], name=volume_mount["name"]
            )
            for volume_mount in job_config["volume_mounts"]
        ],
    )

    pod_spec_kwargs = dict(
        restart_policy="Never",
        containers=[container],
        service_account_name=job_config["service_account_name"],
        security_context=kubernetes.client.V1PodSecurityContext(
            run_as_user=10001, run_as_group=10001
        ),
        volumes=[
            kubernetes.client.V1Volume(
                name=secret["name"],
                secret=kubernetes.client.V1SecretVolumeSource(
                    secret_name=secret["secret_name"],
                ),
            )
            for secret in job_config["secrets"]
        ],
    )

    # Create and configurate a spec section
    template = kubernetes.client.V1PodTemplateSpec(
        metadata=kubernetes.client.V1ObjectMeta(labels={}),
        spec=kubernetes.client.V1PodSpec(**pod_spec_kwargs),
    )

    # Create the specification of deployment
    spec = kubernetes.client.V1JobSpec(
        template=template,
        backoff_limit=job_config["backoff_limit"],
    )

    # Instantiate the job object
    job_obj = kubernetes.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=kubernetes.client.V1ObjectMeta(name=job_config["name"]),
        spec=spec,
    )
    job = kubernetes.client.BatchV1Api(api_client=api_client).create_namespaced_job(
        namespace=job_config["namespace"],
        body=job_obj,
    )
    return job


def read_job(
    namespace: str, name: str, context_name: Optional[str] = None
) -> kubernetes.client.models.v1_job.V1Job:
    api_client = get_api_client(context_name)
    return (
        kubernetes.client.BatchV1Api(api_client=api_client)
        .list_namespaced_job(
            namespace=namespace,
            label_selector=f"job-name={name}",
        )
        .items[0]
    )


def get_job_env_var(
    job: kubernetes.client.models.v1_job.V1Job, env_var_name: str
) -> str:
    for env_var in job.spec.template.spec.containers[0].env:
        if env_var.name == env_var_name:
            return env_var.value
    raise ValueError(f"env var {env_var_name} not found in k8s job config")


def read_job_status(
    namespace: str, name: str, context_name: Optional[str] = None
) -> kubernetes.client.models.v1_job_status.V1JobStatus:
    # TODO: figure out status only perms for:
    # .read_namespaced_job_status(name=job_name, namespace=job_config["namespace"])
    return read_job(namespace, name, context_name).status


def get_job_pod(
    namespace: str, name: str, context_name: Optional[str] = None
) -> kubernetes.client.V1Pod:
    api_client = get_api_client(context_name)
    return (
        kubernetes.client.CoreV1Api(api_client=api_client)
        .list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={name}",
        )
        .items[0]
    )


def get_pod_container_name(pod: kubernetes.client.V1Pod) -> Optional[str]:
    """
    Returns the pod container name if the pod phase is Running with
    all containers running or pod phase is Succeeded or Failed with
    all containers terminated and otherwise None.

    Raises for pod phase Unknown.
    """
    pod_phase = pod.status.phase
    if pod_phase == "Running" and all(
        container_status.state.running is not None
        for container_status in pod.status.container_statuses
    ):
        log.info(f"pod {pod.metadata.name} running container")
        return pod.metadata.name
    elif pod_phase in {"Succeeded", "Failed"} and all(
        container_status.state.terminated is not None
        for container_status in pod.status.container_statuses
    ):
        log.info(f"pod {pod.metadata.name} container terminated")
        return pod.metadata.name
    elif pod_phase == "Unknown":
        log.error(f"job pod lifecycle phase is Unknown")
        raise Exception("Unable to fetch pod status for job")
    return None


def watch_job(
    namespace: str,
    name: str,
    timeout_seconds: Optional[int] = 30,
    context_name: Optional[str] = None,
) -> Generator[kubernetes.client.V1WatchEvent, None, None]:
    api_client = get_api_client(context_name)
    log.info(f"watching job for job {namespace} {name}")
    for event in kubernetes.watch.Watch().stream(
        kubernetes.client.BatchV1Api(api_client=api_client).list_namespaced_job,
        namespace=namespace,
        label_selector=f"job-name={name}",
        timeout_seconds=timeout_seconds,
    ):
        yield event


def watch_job_pods(
    namespace: str,
    name: str,
    timeout_seconds: Optional[int] = 30,
    context_name: Optional[str] = None,
) -> Generator[kubernetes.client.V1WatchEvent, None, None]:
    api_client = get_api_client(context_name)
    log.info(f"watching job pod for job {namespace} {name}")
    for event in kubernetes.watch.Watch().stream(
        kubernetes.client.CoreV1Api(api_client=api_client).list_namespaced_pod,
        namespace=namespace,
        label_selector=f"job-name={name}",
        timeout_seconds=timeout_seconds,
    ):
        yield event


@contextlib.contextmanager
def run_job(
    job_config: KubeJobConfig,
) -> Generator[kubernetes.client.V1Job, None, None]:
    """
    Creates and runs a k8s job with provided config and yields the job api response

    Deletes the job when then context manager exits
    """
    get_api_client(job_config["context_name"])
    job = create_job(job_config)
    yield job
