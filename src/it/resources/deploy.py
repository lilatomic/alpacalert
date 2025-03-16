"""Deploy test resources"""
import functools
import os
import subprocess
import time


def retry(f):
	@functools.wraps(f)
	def wrapper(*args, **kwargs):
		i = 0
		while True:
			try:
				i += 1
				return f(*args, **kwargs)
			except Exception:
				if i > 3:
					raise
				else:
					time.sleep(5)
	return wrapper


@retry
def shell(cmd: str):
	"""Run a shell command"""
	subprocess.run(cmd, shell=True, check=True)


def k8sfile(path: str):
	"""Deploy a kubernetes manifest"""
	shell(f"kubectl apply -f {filepath(path)}")


def filepath(relative_path: str) -> str:
	"""Resolve a relative filepath to its test resource"""
	return os.path.join("src/it/resources/", relative_path)


def prom():
	"""Deploy kube-prometheus"""
	shell("helm repo add prometheus-community https://prometheus-community.github.io/helm-charts")
	shell("helm repo update")

	shell(f"helm upgrade --install --namespace prom prom prometheus-community/kube-prometheus-stack -f {filepath('prometheus.yml')}")


def nginx():
	"""Deploy ingress-nginx"""
	shell("kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml --namespace ingress-nginx")
	k8sfile("ingress_test.yml")


if __name__ == "__main__":
	k8sfile("names.yml")
	prom()
	nginx()
	k8sfile("k8s_objects.yml")
