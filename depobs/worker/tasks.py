import asyncio
import concurrent.futures
import copy
import functools
import json
import logging
import requests
from random import randrange
from typing import (
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
)

import flask
from flask import current_app
import kubernetes

import depobs.database.models as models
from depobs.database.models import (
    get_NPMRegistryEntry,
    store_package_reports,
    get_most_recently_inserted_package_from_name_and_version,
    get_latest_graph_including_package_as_parent,
    save_json_results,
)
import depobs.worker.scoring as scoring
import depobs.worker.serializers as serializers
import depobs.worker.validators as validators

from depobs.database.models import (
    PackageGraph,
    PackageVersion,
)
from depobs.util.traceback_util import exc_to_str
from depobs.worker import k8s
from depobs.worker.tasks.package_data import (
    fetch_missing_npm_data,
    fetch_and_save_npmsio_scores,
    fetch_and_save_registry_entries,
)


log = logging.getLogger(__name__)


class RunRepoTasksConfig(k8s.KubeJobConfig, total=True):
    # Language to run commands for
    language: str

    # Package manager to run commands for
    package_manager: str

    # Run install, list_metadata, or audit tasks in the order
    # provided
    repo_tasks: List[str]


async def run_job_to_completion(
    job_config: k8s.KubeJobConfig,
    scan_id: int,
) -> kubernetes.client.models.v1_job.V1Job:
    job_name = job_config["name"]
    log.info(f"scan {scan_id} starting job {job_name} with config {job_config}")
    with k8s.run_job(job_config) as job:
        log.info(f"scan {scan_id} started job {job}")
        await asyncio.sleep(1)
        job = k8s.read_job(
            job_config["namespace"], job_name, context_name=job_config["context_name"]
        )
        log.info(f"scan {scan_id} got initial job status {job.status}")
        while True:
            if job.status.failed:
                log.error(f"scan {scan_id} k8s job {job_name} failed")
                return job
            if job.status.succeeded:
                log.info(f"scan {scan_id} k8s job {job_name} succeeded")
                return job
            if not job.status.active:
                log.error(
                    f"scan {scan_id} k8s job {job_name} stopped/not active (did not fail or succeed)"
                )
                return job

            await asyncio.sleep(5)
            job = k8s.read_job(
                job_config["namespace"],
                job_name,
                context_name=job_config["context_name"],
            )
            log.info(f"scan {scan_id} got job status {job.status}")


async def scan_tarball_url(
    config: RunRepoTasksConfig,
    tarball_url: str,
    scan_id: int,
    package_name: str,
    package_version: Optional[str] = None,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a run_repo_tasks config, tarball url, and optional package
    name and version.

    Returns the k8s job when it finishes
    """
    job_config: k8s.KubeJobConfig = {
        "backoff_limit": config["backoff_limit"],
        "context_name": config["context_name"],
        "name": config["name"],
        "namespace": config["namespace"],
        "image_name": config["image_name"],
        "args": config["repo_tasks"],
        "env": {
            **config["env"],
            "LANGUAGE": config["language"],
            "PACKAGE_MANAGER": config["package_manager"],
            "PACKAGE_NAME": package_name,
            "PACKAGE_VERSION": package_version or "unknown-package-version",
            # see: https://github.com/mozilla-services/dependency-observatory/issues/280#issuecomment-641588717
            "INSTALL_TARGET": ".",
            "JOB_NAME": config["name"],
            "SCAN_ID": str(scan_id),
        },
        "secrets": config["secrets"],
        "service_account_name": config["service_account_name"],
        "volume_mounts": config["volume_mounts"],
    }
    return await run_job_to_completion(job_config, scan_id)


async def scan_npm_dep_files(
    config: RunRepoTasksConfig,
    scan: models.Scan,
) -> kubernetes.client.models.v1_job.V1Job:
    """
    Takes a run_repo_tasks config and scan_id.

    Returns the k8s job when it finishes
    """
    log.info(f"scan: {scan.id} scanning dep files with config {config}")
    job_config: k8s.KubeJobConfig = {
        "backoff_limit": config["backoff_limit"],
        "context_name": config["context_name"],
        "name": config["name"],
        "namespace": config["namespace"],
        "image_name": config["image_name"],
        "args": config["repo_tasks"],
        "env": {
            **config["env"],
            "LANGUAGE": config["language"],
            "PACKAGE_MANAGER": config["package_manager"],
            "INSTALL_TARGET": ".",
            "JOB_NAME": config["name"],
            "SCAN_ID": str(scan.id),
            "DEP_FILE_URLS_JSON": json.dumps(list(scan.dep_file_urls())),
        },
        "secrets": config["secrets"],
        "service_account_name": config["service_account_name"],
        "volume_mounts": config["volume_mounts"],
    }
    return await run_job_to_completion(job_config, scan.id)


def scan_package_tarballs(scan: models.Scan) -> Generator[asyncio.Task, None, None]:
    """Given a scan, uses its package name and optional version params, checks for matching npm
    registry entries and start k8s jobs to scan the tarball url for
    each version.

    Generates scan jobs with format asyncio.Task that terminate when
    the k8s finishes.

    When the version is 'latest' only scans the most recently published version of the package.
    """
    package_name: str = scan.package_name
    scan_package_version: Optional[str] = scan.package_version

    # fetch npm registry entries from DB
    for entry in scan.get_npm_registry_entries():
        if entry.package_version is None:
            log.warn(
                f"scan: {scan.id} skipping npm registry entry with null version {package_name}"
            )
            continue
        elif not validators.is_npm_release_package_version(entry.package_version):
            log.warn(
                f"scan: {scan.id} {package_name} skipping npm registry entry with pre-release version {entry.package_version!r}"
            )
            continue

        log.info(f"scan: {scan.id} scanning {package_name}@{entry.package_version}")
        # we need a source_url and git_head or a tarball url to install
        if entry.tarball:
            job_name = f"scan-{scan.id}-pkg-{hex(randrange(1 << 32))[2:]}"
            config: RunRepoTasksConfig = copy.deepcopy(
                current_app.config["SCAN_NPM_TARBALL_ARGS"]
            )
            config["name"] = job_name

            log.info(
                f"scan: {scan.id} scanning {package_name}@{entry.package_version} with {entry.tarball} with config {config}"
            )
            # start an npm container, install the tarball, run list and audit
            # assert entry.tarball == f"https://registry.npmjs.org/{package_name}/-/{package_name}-{entry.package_version}.tgz
            yield asyncio.create_task(
                scan_tarball_url(
                    config,
                    entry.tarball,
                    scan.id,
                    package_name,
                    entry.package_version,
                ),
                name=job_name,
            )
        elif entry.source_url and entry.git_head:
            # TODO: port scanner find_dep_files and run_repo_tasks pipelines as used in analyze_package.sh
            log.info(
                f"scan: {scan.id} scanning {package_name}@{entry.package_version} from {entry.source_url}#{entry.git_head} not implemented"
            )
            log.error(
                f"scan: {scan.id} Installing from VCS source and ref not implemented to scan {package_name}@{entry.package_version}"
            )

        if scan_package_version == "latest":
            log.info(
                "scan: {scan.id} latest version of package requested. Stopping after first release version"
            )
            break


async def scan_score_npm_dep_files(
    scan: models.Scan,
) -> None:
    """
    Scan and score dependencies from a manifest file and one or more optional lockfiles
    """
    log.info(f"scan: {scan.id} {scan.name} starting")
    config: RunRepoTasksConfig = copy.deepcopy(
        current_app.config["SCAN_NPM_DEP_FILES_ARGS"]
    )
    job_name = config["name"] = f"scan-{scan.id}-depfiles-{hex(randrange(1 << 32))[2:]}"
    task: asyncio.Task = asyncio.create_task(
        scan_npm_dep_files(
            config,
            scan,
        ),
        name=job_name,
    )
    job: kubernetes.client.models.v1_job.V1Job = await task
    log.info(f"scan: {scan.id} {job_name} k8s job finished with status {job.status}")
    if not job.status.succeeded:
        raise Exception(f"scan: {scan.id} {job_name} did not succeed")

    # wait for logs to show up from pubsub
    while True:
        log.info(f"scan: {scan.id} {job_name} succeeded; waiting for pubsub logs")
        if any(
            result.data["data"][-1]["type"] == "task_complete"
            for result in models.get_scan_job_results(job_name)
        ):
            break
        await asyncio.sleep(5)

    db_graph: models.PackageGraph
    log.info(f"scan: {scan.id} {job_name} saving job results")
    for deserialized in serializers.deserialize_scan_job_results(
        models.get_scan_job_results(k8s.get_job_env_var(job, "JOB_NAME"))
    ):
        models.save_deserialized(deserialized)
        if isinstance(deserialized, tuple) and isinstance(
            deserialized[0], models.PackageGraph
        ):
            log.info(
                f"scan: {scan.id} saving job results for {list(scan.dep_file_urls())}"
            )
            db_graph = deserialized[0]
            assert db_graph.id
            models.save_scan_with_graph_id(scan, db_graph.id)

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    # TODO: handle non-lib package; list all top level packages and score them on the graph?
    # TODO: handle a library package score as usual (make sure we don't pollute the package version entry)
    # TODO: score the graph without a root package_version
    assert db_graph
    store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def scan_score_npm_package(scan: models.Scan) -> None:
    """
    Scan and score an npm package using params from the provided Scan model
    """
    package_name: str = scan.package_name
    package_version: Optional[str] = scan.package_version
    log.info(
        f"scan: {scan.id} fetching npms.io score and npm registry entry for {package_name}"
    )
    await asyncio.gather(
        fetch_and_save_registry_entries([package_name]),
        fetch_and_save_npmsio_scores([package_name]),
    )

    tarball_scans: List[asyncio.Task] = list(scan_package_tarballs(scan))
    log.info(f"scan: {scan.id} scanning {package_name} {len(tarball_scans)} versions")
    k8s_jobs: List[kubernetes.client.models.v1_job.V1Job] = await asyncio.gather(
        *tarball_scans
    )
    successful_jobs = [job for job in k8s_jobs if job.status.succeeded]
    log.info(
        f"scan: {scan.id} {len(k8s_jobs)} k8s jobs finished, {len(successful_jobs)}) succeeded"
    )

    # wait for logs to show up from pubsub
    successful_job_names = {
        k8s.get_job_env_var(job, "JOB_NAME") for job in successful_jobs
    }
    while True:
        jobs_completed = {
            job_name: any(
                result.data["data"][-1]["type"] == "task_complete"
                for result in models.get_scan_job_results(job_name)
            )
            for job_name in successful_job_names
        }
        log.info(
            f"scan: {scan.id} {jobs_completed.keys()} finished; waiting for pubsub logs from {successful_job_names - set(jobs_completed.keys())}"
        )
        if set(jobs_completed.keys()) == successful_job_names:
            break
        await asyncio.sleep(5)

    log.info(f"scan: {scan.id} saving logs from {len(successful_jobs)} successful jobs")
    for job in successful_jobs:
        log.info(
            f"scan: {scan.id} saving job results for {k8s.get_job_env_var(job, 'PACKAGE_NAME')}@{k8s.get_job_env_var(job, 'PACKAGE_VERSION')}"
        )
        for deserialized in serializers.deserialize_scan_job_results(
            models.get_scan_job_results(k8s.get_job_env_var(job, "JOB_NAME"))
        ):
            models.save_deserialized(deserialized)

    log.info(
        f"scan: {scan.id} fetching missing npms.io scores and npm registry entries for scoring"
    )
    await fetch_missing_npm_data()

    log.info(f"scan: {scan.id} scoring {len(successful_jobs)} package versions")
    for job in successful_jobs:
        package_name, package_version = (
            k8s.get_job_env_var(job, "PACKAGE_NAME"),
            k8s.get_job_env_var(job, "PACKAGE_VERSION"),
        )
        log.info(
            f"scan: {scan.id} scoring package version {package_name}@{package_version}"
        )

        package: Optional[
            PackageVersion
        ] = get_most_recently_inserted_package_from_name_and_version(
            package_name, package_version
        )
        if package is None:
            log.error(
                f"scan: {scan.id} PackageVersion not found for {package_name} {package_version}. Skipping scoring."
            )
            continue

        db_graph: Optional[PackageGraph] = get_latest_graph_including_package_as_parent(
            package
        )
        if db_graph is None:
            log.info(
                f"scan: {scan.id} {package.name} {package.version} has no children"
            )
            db_graph = PackageGraph(id=None, link_ids=[])
            db_graph.distinct_package_ids = set([package.id])

        store_package_reports(list(scoring.score_package_graph(db_graph).values()))


async def run_next_scan(app: flask.Flask) -> Optional[models.Scan]:
    """
    Async task that:

    * fetches the next scan job (returns None when one isn't found)

    Returns the updated scan or None (when one isn't found to run).
    """
    # try to read the next queued scan from the scans table if we weren't given one
    log.debug("checking for a scan in the DB to run")
    maybe_next_scan: Optional[models.Scan] = (
        models.get_next_scans().filter_by(status="queued").limit(1).one_or_none()
    )
    if maybe_next_scan is None:
        log.debug("could not find a scan in the DB to run")
        await asyncio.sleep(5)
        return None
    return await run_scan(app, maybe_next_scan)


async def run_scan(
    app: flask.Flask,
    scan: models.Scan,
) -> models.Scan:
    """
    Async task that:

    * takes a scan job
    * starts a k8s job in the untrusted jobs cluster
    * updates the scan status from 'queued' to 'started'
    * watches the k8s job and sets the scan status to 'failed' or 'succeeded' when the k8s job finishes

    Returns the updated scan.
    """
    if not (
        isinstance(scan.params, dict)
        and all(k in scan.params.keys() for k in {"name", "args", "kwargs"})
    ):
        log.info(f"ignoring pending scan {scan.id} with params {scan.params}")
        return scan

    if scan.name == "scan_score_npm_package":
        scan_fn = scan_score_npm_package
    elif scan.name == "scan_score_npm_dep_files":
        scan_fn = scan_score_npm_dep_files
    else:
        log.info(f"ignoring pending scan {scan.id} with type {scan.name}")
        return scan

    log.info(
        f"starting a k8s job for {scan.name} scan {scan.id} with params {scan.params}"
    )
    with app.app_context():
        scan = models.save_scan_with_status(scan, "started")
        # scan fails if any of its tarball scan jobs, data fetching, or scoring steps fail
        try:
            await scan_fn(scan)
            new_scan_status = "succeeded"
        except Exception as err:
            log.error(f"{scan.id} error scanning and scoring: {err}\n{exc_to_str()}")
            new_scan_status = "failed"
        return models.save_scan_with_status(scan, new_scan_status)


async def run_background_tasks(app: flask.Flask, task_fns: Iterable[Callable]) -> None:
    """
    Repeatedly runs one or more tasks with the param task_name until
    the shutdown event fires.
    """
    shutdown = asyncio.Event()

    task_fns_by_name = {
        task_fn.__name__: functools.partial(task_fn, app) for task_fn in task_fns
    }
    tasks: Set[asyncio.Task] = {
        asyncio.create_task(fn(), name=name) for name, fn in task_fns_by_name.items()
    }
    log.info(f"starting initial background tasks {tasks}")
    while True:
        done, pending = await asyncio.wait(
            tasks, timeout=5, return_when=asyncio.FIRST_COMPLETED
        )
        assert all(isinstance(task, asyncio.Task) for task in pending)
        log.debug(
            f"background task {done} completed, running: {[task.get_name() for task in pending]}"  # type: ignore
        )
        if shutdown.is_set():
            # wait for everything to finish
            await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            log.info("all background tasks finished exiting")
            break

        for task in tasks:
            if task.done():
                if task.cancelled():
                    log.warn(f"task {task.get_name()} was cancelled")
                elif task.exception():
                    log.error(f"task {task.get_name()} errored")
                    task.print_stack()
                elif task.result() is None:
                    log.debug(f"task {task.get_name()} finished with result: None")
                else:
                    log.info(
                        f"task {task.get_name()} finished with result: {task.result()}"
                    )
                log.debug(f"queuing a new {task.get_name()} task")
                tasks.remove(task)
                tasks.add(
                    asyncio.create_task(
                        task_fns_by_name[task.get_name()](), name=task.get_name()
                    )
                )
