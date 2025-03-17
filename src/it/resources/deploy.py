"""Deploy test resources"""
import asyncio
import functools
import os
import subprocess


async def retry(f, attempts=3, delay=5):
	"""Run a function with retries"""
	i = 0
	while True:
		try:
			i += 1
			return await f()
		except Exception:
			if i > attempts:
				raise
			else:
				await asyncio.sleep(delay)


def with_retry(f):
	"""Add retries to a function"""
	@functools.wraps(f)
	async def wrapper(*args, **kwargs):
		await retry(lambda: f(*args, **kwargs))

	return wrapper


async def raw_shell(cmd: str):
	"""Run a shell command. Retries are not provided, allowing customisation by the caller"""
	proc = await asyncio.create_subprocess_shell(
		cmd,
		shell=True,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.PIPE,
	)
	stdout, stderr = await proc.communicate()
	if stdout:
		print(f'[stdout]\n{stdout.decode()}')
	if stderr:
		print(f'[stderr]\n{stderr.decode()}')
	if proc.returncode != 0:
		raise subprocess.CalledProcessError(proc.returncode if proc.returncode is not None else 0, cmd, stdout, stderr)


@with_retry
async def shell(cmd: str):
	"""Run a shell command with retries"""
	await raw_shell(cmd)


@with_retry
async def k8sfile(path: str):
	"""Deploy a kubernetes manifest"""
	await shell(f"kubectl apply -f {filepath(path)}")


def filepath(relative_path: str) -> str:
	"""Resolve a relative filepath to its test resource"""
	return os.path.join("src/it/resources/", relative_path)


async def wait_for_job(ns: str, name: str):
	"""Wait for a job to complete"""

	await retry(lambda: raw_shell(f"kubectl wait --for=condition=complete --namespace {ns} jobs/{name}"), attempts=100, delay=1)


async def wait_for_deployment(ns: str, name: str):
	"""Wait for a deployment to have a ready pod"""
	await retry(lambda: raw_shell(f"kubectl wait --for=jsonpath='{{.status.readyReplicas}}'=1 deployment/{name} -n {ns}"))


async def wait_for_cronjob(ns: str, name: str):
	"""Wait for a cron job to have at least 1 execution"""
	await retry(lambda: raw_shell(f"kubectl wait --for=jsonpath='{{.status.lastScheduleTime}}' cronjob/{name} -n {ns}"), attempts=100, delay=1)


async def prom():
	"""Deploy kube-prometheus"""
	await shell("helm repo add prometheus-community https://prometheus-community.github.io/helm-charts")
	await shell("helm repo update")

	await shell(f"helm upgrade --install --namespace prom prom prometheus-community/kube-prometheus-stack -f {filepath('prometheus.yml')}")


async def nginx():
	"""Deploy ingress-nginx"""
	await shell("kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml --namespace ingress-nginx")
	await wait_for_job("ingress-nginx", "ingress-nginx-admission-create")
	await wait_for_deployment("ingress-nginx", "ingress-nginx-controller")
	await k8sfile("ingress_test.yml")


async def deploy_all():
	"""Deploy all resources"""
	# deploy ingress-nginx first so that we can wait for its validating webhook to come online
	await asyncio.gather(
		nginx(),
	)
	await asyncio.gather(
		k8sfile("names.yml"),
		prom(),
		k8sfile("k8s_objects.yml"),
	)
	await asyncio.gather(
		wait_for_cronjob("aa-cronjob", "hello")
	)


if __name__ == "__main__":
	asyncio.run(deploy_all())
